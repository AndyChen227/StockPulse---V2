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


def _create_schema(connection: sqlite3.Connection) -> None:
    """Create the small V1 database schema when it does not yet exist."""

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
