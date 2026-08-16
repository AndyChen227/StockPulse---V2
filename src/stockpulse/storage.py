"""Local storage helpers for raw Stocktwits messages."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


@dataclass(frozen=True)
class StorageResult:
    """Summary of one database write."""

    inserted: int
    duplicates: int
    affected_dates: tuple[str, ...]


@dataclass(frozen=True)
class PendingMessage:
    """A stored message that has not received an AI sentiment label yet."""

    message_id: int
    body: str
    stocktwits_sentiment: str | None


@dataclass(frozen=True)
class MessageAnalysis:
    """AI sentiment fields ready to be written to one stored message."""

    message_id: int
    sentiment: str
    confidence: float
    model_name: str
    model_revision: str
    raw_label: str
    low_confidence: bool
    confidence_threshold: float
    analysis_version: str


def save_raw_messages(
    messages: list[dict[str, Any]],
    *,
    symbol: str,
    output_dir: Path = Path("data/raw"),
    collected_at: datetime | None = None,
) -> Path:
    """Save one collection run as readable UTF-8 JSON and return its path."""

    timestamp = collected_at or datetime.now(timezone.utc)
    safe_symbol = symbol.upper().replace(".", "-")
    filename = f"{safe_symbol}_{timestamp:%Y%m%dT%H%M%SZ}.json"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def store_messages(
    messages: list[dict[str, Any]],
    *,
    database_path: Path = Path("data/stockpulse.db"),
    collected_at: datetime | None = None,
) -> StorageResult:
    """Insert new messages into SQLite and refresh their daily statistics."""

    timestamp = collected_at or datetime.now(timezone.utc)
    collected_at_text = timestamp.isoformat()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    inserted = 0
    affected_dates: set[str] = set()

    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            _create_schema(connection)

            for message in messages:
                created_at = str(message["createdAt"])
                stat_date = created_at[:10]
                affected_dates.add(stat_date)

                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO messages (
                        message_id,
                        body,
                        created_at,
                        stocktwits_sentiment,
                        symbols_json,
                        username,
                        user_followers,
                        url,
                        raw_json,
                        collected_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(message["messageId"]),
                        str(message["body"]),
                        created_at,
                        message.get("sentiment"),
                        json.dumps(message.get("symbols", []), ensure_ascii=False),
                        message.get("username"),
                        message.get("userFollowers"),
                        message.get("url"),
                        json.dumps(message, ensure_ascii=False),
                        collected_at_text,
                    ),
                )
                inserted += max(cursor.rowcount, 0)

            for stat_date in affected_dates:
                _refresh_daily_stats(connection, stat_date, collected_at_text)

    return StorageResult(
        inserted=inserted,
        duplicates=len(messages) - inserted,
        affected_dates=tuple(sorted(affected_dates)),
    )


def get_daily_stats(
    *, database_path: Path = Path("data/stockpulse.db")
) -> list[dict[str, Any]]:
    """Return stored daily Stocktwits-label statistics in date order."""

    if not database_path.exists():
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                stat_date,
                total_messages,
                bullish_count,
                bearish_count,
                unlabeled_count,
                updated_at
            FROM daily_stats
            ORDER BY stat_date
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_unanalyzed_messages(
    *,
    database_path: Path = Path("data/stockpulse.db"),
    limit: int = 100,
    analysis_version: str,
    reanalyze: bool = False,
) -> list[PendingMessage]:
    """Return messages missing the requested analysis version."""

    if limit <= 0:
        raise ValueError("Analysis limit must be greater than zero.")
    if not database_path.exists():
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        with connection:
            _create_schema(connection)
        where_clause = "1 = 1" if reanalyze else (
            "ai_sentiment IS NULL OR analysis_version IS NULL "
            "OR analysis_version != ?"
        )
        parameters: tuple[Any, ...]
        if reanalyze:
            parameters = (limit,)
        else:
            parameters = (analysis_version, limit)
        rows = connection.execute(
            f"""
            SELECT message_id, body, stocktwits_sentiment
            FROM messages
            WHERE {where_clause}
            ORDER BY created_at, message_id
            LIMIT ?
            """,
            parameters,
        ).fetchall()

    return [
        PendingMessage(
            message_id=int(row["message_id"]),
            body=str(row["body"]),
            stocktwits_sentiment=row["stocktwits_sentiment"],
        )
        for row in rows
    ]


def store_message_analyses(
    analyses: list[MessageAnalysis],
    *,
    database_path: Path = Path("data/stockpulse.db"),
    analyzed_at: datetime | None = None,
    overwrite: bool = False,
) -> int:
    """Save AI results, replacing only outdated versions unless requested."""

    if not analyses:
        return 0
    if not database_path.exists():
        raise ValueError(f"Database does not exist: {database_path}")

    timestamp = analyzed_at or datetime.now(timezone.utc)
    updated = 0
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            _create_schema(connection)
            for analysis in analyses:
                update_guard = "" if overwrite else (
                    "AND (ai_sentiment IS NULL OR analysis_version IS NULL "
                    "OR analysis_version != ?)"
                )
                parameters: tuple[Any, ...] = (
                    analysis.sentiment,
                    analysis.confidence,
                    analysis.model_name,
                    analysis.model_revision,
                    analysis.raw_label,
                    int(analysis.low_confidence),
                    analysis.confidence_threshold,
                    analysis.analysis_version,
                    timestamp.isoformat(),
                    analysis.message_id,
                )
                if not overwrite:
                    parameters += (analysis.analysis_version,)
                cursor = connection.execute(
                    f"""
                    UPDATE messages
                    SET
                        ai_sentiment = ?,
                        ai_confidence = ?,
                        ai_model = ?,
                        ai_model_revision = ?,
                        ai_raw_label = ?,
                        ai_low_confidence = ?,
                        ai_confidence_threshold = ?,
                        analysis_version = ?,
                        analyzed_at = ?
                    WHERE message_id = ? {update_guard}
                    """,
                    parameters,
                )
                updated += max(cursor.rowcount, 0)
    return updated


def get_ai_daily_stats(
    *,
    database_path: Path = Path("data/stockpulse.db"),
    analysis_version: str | None = None,
) -> list[dict[str, Any]]:
    """Return daily AI sentiment counts and author-label agreement."""

    if not database_path.exists():
        return []

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        with connection:
            _create_schema(connection)
        version_filter = "" if analysis_version is None else "AND analysis_version = ?"
        parameters: tuple[Any, ...] = (
            () if analysis_version is None else (analysis_version,)
        )
        rows = connection.execute(
            f"""
            SELECT
                SUBSTR(created_at, 1, 10) AS stat_date,
                COUNT(*) AS analyzed_count,
                SUM(CASE WHEN ai_sentiment = 'Bullish' THEN 1 ELSE 0 END)
                    AS bullish_count,
                SUM(CASE WHEN ai_sentiment = 'Neutral' THEN 1 ELSE 0 END)
                    AS neutral_count,
                SUM(CASE WHEN ai_sentiment = 'Bearish' THEN 1 ELSE 0 END)
                    AS bearish_count,
                ROUND(AVG(ai_confidence), 4) AS average_confidence,
                SUM(CASE WHEN stocktwits_sentiment IS NOT NULL
                         AND stocktwits_sentiment != '' THEN 1 ELSE 0 END)
                    AS author_labeled_count,
                SUM(CASE WHEN LOWER(stocktwits_sentiment) = LOWER(ai_sentiment)
                         THEN 1 ELSE 0 END) AS agreement_count,
                SUM(CASE WHEN ai_low_confidence = 1 THEN 1 ELSE 0 END)
                    AS low_confidence_count
            FROM messages
            WHERE ai_sentiment IS NOT NULL
                {version_filter}
            GROUP BY SUBSTR(created_at, 1, 10)
            ORDER BY stat_date
            """,
            parameters,
        ).fetchall()

    return [dict(row) for row in rows]


def _create_schema(connection: sqlite3.Connection) -> None:
    """Create the schema and migrate older Phase 2 databases in place."""

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            stocktwits_sentiment TEXT,
            symbols_json TEXT NOT NULL,
            username TEXT,
            user_followers INTEGER,
            url TEXT,
            raw_json TEXT NOT NULL,
            collected_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_messages_created_at
            ON messages(created_at);

        CREATE TABLE IF NOT EXISTS daily_stats (
            stat_date TEXT PRIMARY KEY,
            total_messages INTEGER NOT NULL,
            bullish_count INTEGER NOT NULL,
            bearish_count INTEGER NOT NULL,
            unlabeled_count INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )

    existing_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(messages)")
    }
    migrations = {
        "ai_sentiment": "TEXT",
        "ai_confidence": "REAL",
        "ai_model": "TEXT",
        "ai_model_revision": "TEXT",
        "ai_raw_label": "TEXT",
        "ai_low_confidence": "INTEGER",
        "ai_confidence_threshold": "REAL",
        "analysis_version": "TEXT",
        "analyzed_at": "TEXT",
    }
    for column_name, column_type in migrations.items():
        if column_name not in existing_columns:
            connection.execute(
                f"ALTER TABLE messages ADD COLUMN {column_name} {column_type}"
            )


def _refresh_daily_stats(
    connection: sqlite3.Connection, stat_date: str, updated_at: str
) -> None:
    """Recalculate one day's counts from deduplicated source messages."""

    connection.execute(
        """
        INSERT INTO daily_stats (
            stat_date,
            total_messages,
            bullish_count,
            bearish_count,
            unlabeled_count,
            updated_at
        )
        SELECT
            ?,
            COUNT(*),
            SUM(CASE WHEN LOWER(stocktwits_sentiment) = 'bullish' THEN 1 ELSE 0 END),
            SUM(CASE WHEN LOWER(stocktwits_sentiment) = 'bearish' THEN 1 ELSE 0 END),
            SUM(CASE WHEN stocktwits_sentiment IS NULL OR stocktwits_sentiment = '' THEN 1 ELSE 0 END),
            ?
        FROM messages
        WHERE SUBSTR(created_at, 1, 10) = ?
        ON CONFLICT(stat_date) DO UPDATE SET
            total_messages = excluded.total_messages,
            bullish_count = excluded.bullish_count,
            bearish_count = excluded.bearish_count,
            unlabeled_count = excluded.unlabeled_count,
            updated_at = excluded.updated_at
        """,
        (stat_date, updated_at, stat_date),
    )
