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
from stockpulse.sentiment import (
    SentimentAnalyzer,
    SentimentModelError,
    build_analysis_version,
)
from stockpulse.storage import (
    MessageAnalysis,
    get_ai_daily_stats,
    get_daily_stats,
    get_unanalyzed_messages,
    save_raw_messages,
    store_message_analyses,
    store_messages,
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


def main(argv: Sequence[str] | None = None) -> int:
    """Preview configuration or explicitly run the Phase 2 collector."""

    args = build_parser().parse_args(argv)

    try:
        settings = load_settings(require_token=bool(args.collect or args.resume_run))
        print(build_startup_message())
        analysis_version = build_analysis_version(
            settings.sentiment_model,
            settings.sentiment_model_revision,
            settings.sentiment_threshold,
        )

        if args.stats:
            daily_stats = get_daily_stats(database_path=args.database)
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
            ai_stats = get_ai_daily_stats(
                database_path=args.database,
                analysis_version=analysis_version,
            )
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
            pending_messages = get_unanalyzed_messages(
                database_path=args.database,
                limit=args.analysis_limit,
                analysis_version=analysis_version,
                reanalyze=args.reanalyze,
            )
            if not pending_messages:
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
            updated = store_message_analyses(
                analyses,
                database_path=args.database,
                overwrite=args.reanalyze,
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
            print(
                f"Retrieving existing Apify run {args.resume_run}; "
                "no new Actor run will be started..."
            )
            messages = retrieve_run_messages(settings, args.resume_run)
        else:
            print(
                f"Starting a cost-capped Apify run for up to "
                f"{settings.max_messages} {settings.symbol} messages..."
            )
            messages = collect_messages(settings)
        output_path = save_raw_messages(
            messages,
            symbol=settings.symbol,
            output_dir=args.output_dir,
        )
        storage_result = store_messages(messages, database_path=args.database)

        print(f"Collected {len(messages)} messages.")
        print(f"Raw JSON saved to: {output_path.resolve()}")
        print(f"New database messages: {storage_result.inserted}")
        print(f"Duplicate database messages: {storage_result.duplicates}")
        print(f"SQLite database: {args.database.resolve()}")
        if messages:
            print(f"Returned fields: {', '.join(sorted(messages[0]))}")
        return 0
    except (CollectionError, SentimentModelError, ValueError) as error:
        print(f"StockPulse stopped safely: {error}")
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
