"""Command-line entry point for StockPulse."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from stockpulse import __version__
from stockpulse.anomaly import DETECTOR_VERSION, evaluate_anomaly, replay_anomalies
from stockpulse.collector.apify_client import (
    CollectionError,
    collect_messages,
    retrieve_run_messages,
)
from stockpulse.config import load_settings
from stockpulse.postgres import apply_postgres_migrations, create_postgres_pool
from stockpulse.postgres_repository import PostgresRepository
from stockpulse.repository import SQLiteRepository, StockPulseRepository
from stockpulse.sentiment import (
    SentimentAnalyzer,
    SentimentModelError,
    build_analysis_version,
)
from stockpulse.storage import (
    MessageAnalysis,
    MessageTopic,
    RunResult,
    save_raw_messages,
)
from stockpulse.topics import (
    TOPIC_ANALYSIS_VERSION,
    extract_topics,
    select_representative_messages,
)


def build_startup_message() -> str:
    """Return a safe startup summary without exposing API credentials."""

    settings = load_settings()
    return (
        f"StockPulse v{__version__} is ready. "
        f"Symbol: {settings.symbol}. "
        f"Actor: {settings.actor_id}. "
        f"Maximum messages: {settings.max_messages}. "
        f"Maximum Actor charge: ${settings.max_total_charge_usd}. "
        f"Sentiment confidence threshold: {settings.sentiment_threshold:.2f}. "
        f"API token configured: {'yes' if settings.has_api_token else 'no'}."
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line interface."""

    parser = argparse.ArgumentParser(description="StockPulse TSLA data collector")
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--collect",
        action="store_true",
        help="Run the cost-capped Apify Actor and save its dataset locally.",
    )
    action_group.add_argument(
        "--resume-run",
        metavar="RUN_ID",
        help="Retrieve an existing Apify run without starting a new Actor run.",
    )
    action_group.add_argument(
        "--stats",
        action="store_true",
        help="Show local daily statistics without contacting Apify.",
    )
    action_group.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze stored messages missing the current analysis version.",
    )
    action_group.add_argument(
        "--reanalyze",
        action="store_true",
        help="Force one batch of stored messages through the current version.",
    )
    action_group.add_argument(
        "--ai-stats",
        action="store_true",
        help="Show local AI sentiment statistics without contacting Apify.",
    )
    action_group.add_argument(
        "--runs",
        action="store_true",
        help="Show recent collection and analysis run history.",
    )
    action_group.add_argument(
        "--analyze-topics",
        action="store_true",
        help="Extract missing versioned topics from locally analyzed messages.",
    )
    action_group.add_argument(
        "--reanalyze-topics",
        action="store_true",
        help="Force bounded topic reanalysis using the current topic version.",
    )
    action_group.add_argument(
        "--topic-stats",
        action="store_true",
        help="Show locally stored topic counts without contacting Apify.",
    )
    action_group.add_argument(
        "--topic-history",
        action="store_true",
        help="Show UTC date-bucketed topic metrics for historical charts.",
    )
    action_group.add_argument(
        "--representatives",
        metavar="TOPIC",
        help="Show representative locally stored messages for one exact topic.",
    )
    action_group.add_argument(
        "--detect-anomalies",
        action="store_true",
        help="Evaluate and store the latest daily metric against local history.",
    )
    action_group.add_argument(
        "--replay-anomalies",
        action="store_true",
        help="Replay the versioned anomaly detector across all local daily metrics.",
    )
    action_group.add_argument(
        "--anomalies",
        action="store_true",
        help="Show stored anomaly evaluation history without contacting Apify.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Local directory for raw JSON output (default: data/raw).",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/stockpulse.db"),
        help="SQLite database path (default: data/stockpulse.db).",
    )
    parser.add_argument(
        "--analysis-limit",
        type=int,
        default=100,
        help="Maximum stored messages to analyze in one run (default: 100).",
    )
    parser.add_argument(
        "--topic-limit",
        type=int,
        default=100,
        help="Maximum messages to process in one topic-analysis batch.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    repository: StockPulseRepository | None = None,
) -> int:
    """Preview configuration or explicitly run the Phase 2 collector."""

    args = build_parser().parse_args(argv)
    storage = repository or SQLiteRepository(args.database)
    postgres_pool = None
    application_run_id: str | None = None

    try:
        settings = load_settings(require_token=bool(args.collect or args.resume_run))
        if repository is None and settings.database_backend == "postgresql":
            postgres_pool = create_postgres_pool(
                settings.database_url or "",
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
                open_pool=True,
            )
            with postgres_pool.connection() as connection:
                apply_postgres_migrations(connection)
            storage = PostgresRepository(postgres_pool)
        print(build_startup_message())
        analysis_version = build_analysis_version(
            settings.sentiment_model,
            settings.sentiment_model_revision,
            settings.sentiment_threshold,
        )

        if args.runs:
            runs = storage.get_run_history()
            if not runs:
                print("No collection or analysis runs are stored yet.")
                return 0

            print("Started (UTC)             | Action    | Status    | Msgs | New | Dup | AI")
            print("--------------------------+-----------+-----------+------+-----+-----+----")
            for run in runs:
                print(
                    f"{run['started_at'][:24]:<24} | {run['action']:<9} | "
                    f"{run['status']:<9} | {run['message_count']:>4} | "
                    f"{run['inserted_count']:>3} | {run['duplicate_count']:>3} | "
                    f"{run['analyzed_count']:>2}"
                )
            return 0

        if args.stats:
            daily_stats = storage.get_daily_stats()
            if not daily_stats:
                print("No daily statistics are stored yet.")
                return 0

            print("Date       | Total | Bullish | Bearish | Unlabeled")
            print("-----------+-------+---------+---------+----------")
            for row in daily_stats:
                print(
                    f"{row['stat_date']} | {row['total_messages']:>5} | "
                    f"{row['bullish_count']:>7} | {row['bearish_count']:>7} | "
                    f"{row['unlabeled_count']:>9}"
                )
            return 0

        if args.ai_stats:
            ai_stats = storage.get_ai_daily_stats(analysis_version=analysis_version)
            if not ai_stats:
                print("No AI sentiment statistics are stored yet.")
                return 0

            print(
                "Date       | Total | Bullish | Neutral | Bearish | Avg conf. | Low | Agree"
            )
            print(
                "-----------+-------+---------+---------+---------+-----------+-----+------"
            )
            for row in ai_stats:
                print(
                    f"{row['stat_date']} | {row['analyzed_count']:>5} | "
                    f"{row['bullish_count']:>7} | {row['neutral_count']:>7} | "
                    f"{row['bearish_count']:>7} | "
                    f"{row['average_confidence']:>9.2%} | "
                    f"{row['low_confidence_count']:>3} | "
                    f"{row['agreement_count']}/{row['author_labeled_count']}"
                )
            return 0

        if args.topic_stats:
            topic_stats = storage.get_topic_summary(
                topic_version=TOPIC_ANALYSIS_VERSION
            )
            if not topic_stats:
                print("No topic statistics are stored yet.")
                return 0
            print("Topic                      | Messages | Avg score")
            print("---------------------------+----------+----------")
            for item in topic_stats:
                print(
                    f"{item['topic']:<26} | {item['message_count']:>8} | "
                    f"{item['average_score']:>9.1%}"
                )
            return 0

        if args.topic_history:
            topic_history = storage.get_topic_daily_stats(
                topic_version=TOPIC_ANALYSIS_VERSION
            )
            if not topic_history:
                print("No topic history is stored yet.")
                return 0
            print("Date       | Topic                      | Msgs | Bull | Neut | Bear | Score")
            print("-----------+----------------------------+------+------+------+------+------")
            for item in topic_history:
                print(
                    f"{item['stat_date']} | {item['topic']:<26} | "
                    f"{item['message_count']:>4} | {item['bullish_count']:>4} | "
                    f"{item['neutral_count']:>4} | {item['bearish_count']:>4} | "
                    f"{item['sentiment_score']:>5.2f}"
                )
            return 0

        if args.anomalies:
            history = storage.get_anomaly_history(
                analysis_version=analysis_version,
                detector_version=DETECTOR_VERSION,
            )
            if not history:
                print("No anomaly evaluations are stored yet.")
                return 0
            print("Date       | Status               | Severity | Signals")
            print("-----------+----------------------+----------+--------------------------")
            for item in history:
                signals = ", ".join(item["signals"]) or "-"
                print(
                    f"{item['stat_date']} | {item['status']:<20} | "
                    f"{item['severity']:<8} | {signals}"
                )
                print(f"  {item['explanation']}")
            return 0

        if args.detect_anomalies or args.replay_anomalies:
            application_run_id = storage.start_run(
                "anomalies",
                symbol=settings.symbol,
                analysis_version=analysis_version,
            )
            metrics = storage.get_ai_daily_stats(analysis_version=analysis_version)
            if not metrics:
                storage.finish_run(application_run_id, RunResult(status="succeeded"))
                print("No AI daily metrics are available for anomaly detection.")
                return 0
            topic_metrics = storage.get_topic_daily_stats(
                topic_version=TOPIC_ANALYSIS_VERSION
            )
            results = (
                replay_anomalies(
                    metrics,
                    topic_metrics=topic_metrics,
                    topic_version=TOPIC_ANALYSIS_VERSION,
                )
                if args.replay_anomalies
                else [
                    evaluate_anomaly(
                        metrics,
                        topic_metrics=topic_metrics,
                        topic_version=TOPIC_ANALYSIS_VERSION,
                    )
                ]
            )
            inserted = storage.store_anomaly_results(results)
            storage.finish_run(
                application_run_id,
                RunResult(
                    status="succeeded",
                    message_count=len(results),
                    analyzed_count=len(results),
                ),
            )
            latest = results[-1]
            print(
                f"{latest.stat_date}: {latest.status} ({latest.severity}); "
                f"{latest.explanation}"
            )
            print(
                f"Stored {inserted} new evaluation(s); duplicate versioned "
                "evaluations were skipped."
            )
            print("No Apify request was made and no Apify credits were used.")
            return 0

        if args.representatives:
            candidates = storage.get_representative_candidates(
                topic=args.representatives,
                topic_version=TOPIC_ANALYSIS_VERSION,
            )
            representatives = select_representative_messages(candidates)
            if not representatives:
                print(f"No messages are stored for topic: {args.representatives}")
                return 0
            for message in representatives:
                print(
                    f"{message.message_id}: {message.ai_sentiment} "
                    f"({message.ai_confidence:.1%}) - {message.body}"
                )
                if message.url:
                    print(f"  Source: {message.url}")
            return 0

        if args.analyze_topics or args.reanalyze_topics:
            application_run_id = storage.start_run(
                "topics",
                symbol=settings.symbol,
                analysis_version=TOPIC_ANALYSIS_VERSION,
            )
            candidates = storage.get_topic_candidates(
                topic_version=TOPIC_ANALYSIS_VERSION,
                analysis_version=analysis_version,
                limit=args.topic_limit,
                reanalyze=args.reanalyze_topics,
            )
            if not candidates:
                storage.finish_run(
                    application_run_id, RunResult(status="succeeded")
                )
                print("No eligible messages need topic analysis.")
                return 0
            assignments = [
                MessageTopic(
                    message_id=candidate.message_id,
                    topic=prediction.topic,
                    score=prediction.score,
                    matched_terms=prediction.matched_terms,
                    rank=prediction.rank,
                    topic_version=prediction.topic_version,
                )
                for candidate in candidates
                for prediction in extract_topics(candidate.body)
            ]
            updated = storage.store_message_topics(
                assignments, overwrite=args.reanalyze_topics
            )
            storage.finish_run(
                application_run_id,
                RunResult(
                    status="succeeded",
                    message_count=len(candidates),
                    analyzed_count=len(candidates),
                ),
            )
            print(
                f"Saved {updated} topic assignments for "
                f"{len(candidates)} messages."
            )
            print("No Apify request was made and no Apify credits were used.")
            return 0

        if args.analyze or args.reanalyze:
            action = "reanalyze" if args.reanalyze else "analyze"
            application_run_id = storage.start_run(
                action,
                symbol=settings.symbol,
                analysis_version=analysis_version,
            )
            pending_messages = storage.get_unanalyzed_messages(
                limit=args.analysis_limit,
                analysis_version=analysis_version,
                reanalyze=args.reanalyze,
            )
            if not pending_messages:
                storage.finish_run(
                    application_run_id,
                    RunResult(status="succeeded"),
                )
                print("No unanalyzed messages are stored. Nothing changed.")
                return 0

            print(
                f"Analyzing {len(pending_messages)} stored messages locally with "
                f"{settings.sentiment_model}..."
            )
            analyzer = SentimentAnalyzer(
                model_name=settings.sentiment_model,
                model_revision=settings.sentiment_model_revision,
                confidence_threshold=settings.sentiment_threshold,
            )
            predictions = analyzer.analyze(
                [message.body for message in pending_messages]
            )
            analyses = [
                MessageAnalysis(
                    message_id=message.message_id,
                    sentiment=prediction.sentiment,
                    confidence=prediction.confidence,
                    model_name=prediction.model_name,
                    model_revision=prediction.model_revision,
                    raw_label=prediction.raw_label,
                    low_confidence=prediction.low_confidence,
                    confidence_threshold=prediction.confidence_threshold,
                    analysis_version=prediction.analysis_version,
                )
                for message, prediction in zip(
                    pending_messages, predictions, strict=True
                )
            ]
            updated = storage.store_message_analyses(
                analyses,
                overwrite=args.reanalyze,
            )
            storage.finish_run(
                application_run_id,
                RunResult(
                    status="succeeded",
                    message_count=len(pending_messages),
                    analyzed_count=updated,
                ),
            )
            for message, prediction in zip(
                pending_messages, predictions, strict=True
            ):
                author_label = message.stocktwits_sentiment or "Unlabeled"
                print(
                    f"{message.message_id}: AI={prediction.sentiment} "
                    f"({prediction.confidence:.1%}), "
                    f"low-confidence={'yes' if prediction.low_confidence else 'no'}, "
                    f"Stocktwits={author_label}"
                )
            print(f"Saved AI sentiment for {updated} messages.")
            print("No Apify request was made and no Apify credits were used.")
            return 0

        if not args.collect and not args.resume_run:
            print("Preview only: no Apify request was made.")
            print("Use --collect only when you intend to spend Apify credits.")
            return 0

        if args.resume_run:
            application_run_id = storage.start_run(
                "resume",
                symbol=settings.symbol,
                external_run_id=args.resume_run,
                max_messages=settings.max_messages,
                max_total_charge_usd="0",
            )
            print(
                f"Retrieving existing Apify run {args.resume_run}; "
                "no new Actor run will be started..."
            )
            collection_batch = retrieve_run_messages(settings, args.resume_run)
        else:
            application_run_id = storage.start_run(
                "collect",
                symbol=settings.symbol,
                max_messages=settings.max_messages,
                max_total_charge_usd=str(settings.max_total_charge_usd),
            )
            print(
                f"Starting a cost-capped Apify run for up to "
                f"{settings.max_messages} {settings.symbol} messages..."
            )
            collection_batch = collect_messages(settings)
        messages = collection_batch.messages
        output_path = save_raw_messages(
            messages,
            symbol=settings.symbol,
            output_dir=args.output_dir,
        )
        storage_result = storage.store_messages(messages)
        storage.finish_run(
            application_run_id,
            RunResult(
                status="succeeded",
                message_count=len(messages),
                inserted_count=storage_result.inserted,
                duplicate_count=storage_result.duplicates,
                external_run_id=collection_batch.external_run_id,
                external_dataset_id=collection_batch.external_dataset_id,
            ),
        )

        print(f"Collected {len(messages)} messages.")
        print(f"Raw JSON saved to: {output_path.resolve()}")
        print(f"New database messages: {storage_result.inserted}")
        print(f"Duplicate database messages: {storage_result.duplicates}")
        if settings.database_backend == "sqlite":
            print(f"SQLite database: {args.database.resolve()}")
        else:
            print("PostgreSQL database: configured securely")
        if messages:
            print(f"Returned fields: {', '.join(sorted(messages[0]))}")
        return 0
    except (CollectionError, SentimentModelError, ValueError) as error:
        if application_run_id is not None:
            try:
                storage.finish_run(
                    application_run_id,
                    RunResult(
                        status="failed",
                        error_type=type(error).__name__,
                        error_message=str(error),
                    ),
                )
            except ValueError:
                pass
        print(f"StockPulse stopped safely: {error}")
        return 1
    finally:
        if postgres_pool is not None:
            postgres_pool.close()



if __name__ == "__main__":
    raise SystemExit(main())
