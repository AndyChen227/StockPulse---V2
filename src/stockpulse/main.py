"""Command-line entry point for StockPulse."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from stockpulse import __version__
from stockpulse.collector.apify_client import (
    CollectionError,
    collect_messages,
    retrieve_run_messages,
)
from stockpulse.config import load_settings
from stockpulse.repository import SQLiteRepository, StockPulseRepository
from stockpulse.sentiment import (
    SentimentAnalyzer,
    SentimentModelError,
    build_analysis_version,
)
from stockpulse.storage import (
    MessageAnalysis,
    RunResult,
    save_raw_messages,
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
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    repository: StockPulseRepository | None = None,
) -> int:
    """Preview configuration or explicitly run the Phase 2 collector."""

    args = build_parser().parse_args(argv)
    storage = repository or SQLiteRepository(args.database)
    application_run_id: str | None = None

    try:
        settings = load_settings(require_token=bool(args.collect or args.resume_run))
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
        print(f"SQLite database: {args.database.resolve()}")
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



if __name__ == "__main__":
    raise SystemExit(main())
