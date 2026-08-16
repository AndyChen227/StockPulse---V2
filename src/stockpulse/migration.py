"""Transactional SQLite-to-PostgreSQL history migration."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import UUID

from stockpulse.config import load_settings
from stockpulse.postgres import apply_postgres_migrations, create_postgres_pool


TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "messages": (
        "message_id", "body", "created_at", "stocktwits_sentiment",
        "symbols_json", "username", "user_followers", "url", "raw_json",
        "collected_at", "ai_sentiment", "ai_confidence", "ai_model",
        "ai_model_revision", "ai_raw_label", "ai_low_confidence",
        "ai_confidence_threshold", "analysis_version", "analyzed_at",
    ),
    "daily_stats": (
        "stat_date", "total_messages", "bullish_count", "bearish_count",
        "unlabeled_count", "updated_at",
    ),
    "daily_metrics": (
        "stat_date", "analysis_version", "analyzed_count", "bullish_count",
        "neutral_count", "bearish_count", "average_confidence",
        "low_confidence_count", "author_labeled_count", "agreement_count",
        "sentiment_score", "updated_at",
    ),
    "runs": (
        "run_id", "action", "status", "symbol", "analysis_version",
        "external_run_id", "started_at", "finished_at", "message_count",
        "inserted_count", "duplicate_count", "analyzed_count", "error_type",
        "error_message", "invalid_count", "external_dataset_id", "max_messages",
        "max_total_charge_usd", "retry_of_run_id",
    ),
    "message_topics": (
        "message_id", "topic", "score", "matched_terms_json", "rank",
        "topic_version", "analyzed_at",
    ),
    "anomaly_results": (
        "fingerprint", "stat_date", "analysis_version", "detector_version",
        "status", "severity", "signals_json", "explanation", "history_days",
        "baseline_start_date", "baseline_end_date", "current_messages",
        "baseline_messages", "volume_ratio", "current_sentiment",
        "baseline_sentiment", "sentiment_shift", "created_at", "topic_version",
        "shifted_topic", "current_topic_share", "baseline_topic_share",
        "topic_share_shift",
    ),
}

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "messages": ("message_id",),
    "daily_stats": ("stat_date",),
    "daily_metrics": ("stat_date", "analysis_version"),
    "runs": ("run_id",),
    "message_topics": ("message_id", "topic_version", "topic"),
    "anomaly_results": ("fingerprint",),
}

JSON_COLUMNS = {
    ("messages", "symbols_json"), ("messages", "raw_json"),
    ("message_topics", "matched_terms_json"),
    ("anomaly_results", "signals_json"),
}
UUID_COLUMNS = {("runs", "run_id"), ("runs", "retry_of_run_id")}
BOOLEAN_COLUMNS = {("messages", "ai_low_confidence")}


@dataclass(frozen=True)
class MigrationReport:
    """Counts proving that every source key exists in PostgreSQL."""

    source_counts: dict[str, int]
    inserted_counts: dict[str, int]
    verified_counts: dict[str, int]


def inspect_sqlite(database_path: Path) -> dict[str, int]:
    """Return a deterministic source inventory without changing the database."""

    if not database_path.is_file():
        raise ValueError(f"SQLite database does not exist: {database_path}")
    with closing(sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)) as source:
        _validate_source(source)
        return {
            table: int(source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in TABLE_COLUMNS
        }


def migrate_sqlite_to_postgres(database_path: Path, pool: Any) -> MigrationReport:
    """Idempotently import all history and roll back if key verification fails."""

    source_counts = inspect_sqlite(database_path)
    inserted_counts = {table: 0 for table in TABLE_COLUMNS}
    with closing(sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        with pool.connection() as target, target.transaction():
            for table in TABLE_COLUMNS:
                rows = source.execute(
                    f"SELECT {', '.join(TABLE_COLUMNS[table])} FROM {table}"
                ).fetchall()
                inserted_counts[table] = _insert_rows(target, table, rows)
            _restore_run_retries(source, target)
            verified_counts = _verify_source_keys(source, target)
            if verified_counts != source_counts:
                raise RuntimeError(
                    "PostgreSQL verification failed; the migration was rolled back."
                )
    return MigrationReport(source_counts, inserted_counts, verified_counts)


def _validate_source(source: sqlite3.Connection) -> None:
    tables = {
        str(row[0])
        for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = set(TABLE_COLUMNS) - tables
    if missing:
        raise ValueError(f"SQLite database is missing tables: {', '.join(sorted(missing))}")
    version = source.execute(
        "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
    ).fetchone()[0]
    if int(version) != 6:
        raise ValueError(f"SQLite schema version 6 is required; found {version}.")


def _insert_rows(target: Any, table: str, rows: list[sqlite3.Row]) -> int:
    if not rows:
        return 0
    from psycopg import sql

    columns = TABLE_COLUMNS[table]
    write_columns = tuple(
        column for column in columns if not (table == "runs" and column == "retry_of_run_id")
    )
    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, write_columns)),
        sql.SQL(", ").join(sql.Placeholder() for _ in write_columns),
    )
    inserted = 0
    for row in rows:
        values = tuple(_adapt_value(table, column, row[column]) for column in write_columns)
        inserted += max(target.execute(statement, values).rowcount, 0)
    return inserted


def _adapt_value(table: str, column: str, value: Any) -> Any:
    if value is None:
        return None
    if (table, column) in JSON_COLUMNS:
        from psycopg.types.json import Jsonb

        return Jsonb(json.loads(value))
    if (table, column) in UUID_COLUMNS:
        return UUID(str(value))
    if (table, column) in BOOLEAN_COLUMNS:
        return bool(value)
    return value


def _restore_run_retries(source: sqlite3.Connection, target: Any) -> None:
    rows = source.execute(
        "SELECT run_id, retry_of_run_id FROM runs WHERE retry_of_run_id IS NOT NULL"
    ).fetchall()
    for row in rows:
        target.execute(
            "UPDATE runs SET retry_of_run_id = %s WHERE run_id = %s",
            (UUID(str(row["retry_of_run_id"])), UUID(str(row["run_id"]))),
        )


def _verify_source_keys(source: sqlite3.Connection, target: Any) -> dict[str, int]:
    from psycopg import sql

    verified: dict[str, int] = {}
    for table, keys in PRIMARY_KEYS.items():
        source_keys = {
            tuple(str(value) for value in row)
            for row in source.execute(f"SELECT {', '.join(keys)} FROM {table}")
        }
        statement = sql.SQL("SELECT {} FROM {}").format(
            sql.SQL(", ").join(map(sql.Identifier, keys)), sql.Identifier(table)
        )
        target_keys = set()
        for row in target.execute(statement).fetchall():
            values = tuple(row[key] for key in keys) if isinstance(row, dict) else tuple(row)
            target_keys.add(tuple(
                str(value).replace("-", "") if table == "runs" else str(value)
                for value in values
            ))
        if table == "runs":
            source_keys = {tuple(value.replace("-", "") for value in key) for key in source_keys}
        verified[table] = len(source_keys & target_keys)
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate StockPulse SQLite history")
    parser.add_argument("--source", type=Path, default=Path("data/stockpulse.db"))
    parser.add_argument(
        "--apply", action="store_true",
        help="Perform the PostgreSQL write; without this flag only inspect SQLite",
    )
    args = parser.parse_args()
    inventory = inspect_sqlite(args.source)
    print("SQLite inventory: " + ", ".join(f"{k}={v}" for k, v in inventory.items()))
    if not args.apply:
        print("Preview only. Add --apply to perform the transactional import.")
        return
    settings = load_settings(load_env_file=True)
    if settings.database_backend != "postgresql" or not settings.database_url:
        raise SystemExit("Configure the PostgreSQL backend and secret URL before --apply.")
    pool = create_postgres_pool(
        settings.database_url,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
        open_pool=True,
    )
    try:
        with pool.connection() as connection:
            apply_postgres_migrations(connection)
        report = migrate_sqlite_to_postgres(args.source, pool)
    finally:
        pool.close()
    print("Verified: " + ", ".join(f"{k}={v}" for k, v in report.verified_counts.items()))
