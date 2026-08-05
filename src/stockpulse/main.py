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
from stockpulse.storage import get_daily_stats, save_raw_messages, store_messages


def build_startup_message() -> str:
    """Return a safe startup summary without exposing API credentials."""

    settings = load_settings()
    return (
        f"StockPulse v{__version__} is ready. "
        f"Symbol: {settings.symbol}. "
        f"Actor: {settings.actor_id}. "
        f"Maximum messages: {settings.max_messages}. "
        f"Maximum Actor charge: ${settings.max_total_charge_usd}. "
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Preview configuration or explicitly run the Phase 2 collector."""

    args = build_parser().parse_args(argv)

    try:
        settings = load_settings(require_token=bool(args.collect or args.resume_run))
        print(build_startup_message())

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
    except (CollectionError, ValueError) as error:
        print(f"StockPulse stopped safely: {error}")
        return 1



if __name__ == "__main__":
    raise SystemExit(main())
