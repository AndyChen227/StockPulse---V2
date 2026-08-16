"""Tests for local raw JSON storage."""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.storage import (  # noqa: E402
    MessageAnalysis,
    get_ai_daily_stats,
    get_daily_stats,
    get_unanalyzed_messages,
    save_raw_messages,
    store_message_analyses,
    store_messages,
)


class StorageTests(unittest.TestCase):
    def test_messages_are_saved_as_utf8_json(self) -> None:
        messages = [{"messageId": 123, "body": "$TSLA 测试"}]
        collected_at = datetime(2026, 8, 5, 1, 2, 3, tzinfo=timezone.utc)

        with TemporaryDirectory() as directory:
            output_path = save_raw_messages(
                messages,
                symbol="TSLA",
                output_dir=Path(directory),
                collected_at=collected_at,
            )
            saved_messages = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(output_path.name, "TSLA_20260805T010203Z.json")
        self.assertEqual(saved_messages, messages)

    def test_sqlite_storage_deduplicates_and_updates_daily_stats(self) -> None:
        messages = [
            {
                "messageId": 1,
                "body": "$TSLA bullish test",
                "createdAt": "2026-08-05T01:00:00Z",
                "sentiment": "Bullish",
                "symbols": ["TSLA"],
                "username": "bull",
                "userFollowers": 10,
                "url": "https://example.com/1",
            },
            {
                "messageId": 2,
                "body": "$TSLA unlabeled test",
                "createdAt": "2026-08-05T02:00:00Z",
                "sentiment": None,
                "symbols": ["TSLA"],
                "username": "neutral",
                "userFollowers": 20,
                "url": "https://example.com/2",
            },
        ]

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            first_result = store_messages(messages, database_path=database_path)
            second_result = store_messages(messages, database_path=database_path)
            daily_stats = get_daily_stats(database_path=database_path)

        self.assertEqual(first_result.inserted, 2)
        self.assertEqual(first_result.duplicates, 0)
        self.assertEqual(second_result.inserted, 0)
        self.assertEqual(second_result.duplicates, 2)
        self.assertEqual(
            daily_stats[0],
            {
                "stat_date": "2026-08-05",
                "total_messages": 2,
                "bullish_count": 1,
                "bearish_count": 0,
                "unlabeled_count": 1,
                "updated_at": daily_stats[0]["updated_at"],
            },
        )

    def test_phase_two_database_is_migrated_and_ai_results_are_idempotent(self) -> None:
        analysis_version = "2:test-model@revision-a:threshold=0.6"
        analysis = MessageAnalysis(
            message_id=10,
            sentiment="Bullish",
            confidence=0.92,
            model_name="test-model",
            model_revision="revision-a",
            raw_label="positive",
            low_confidence=False,
            confidence_threshold=0.60,
            analysis_version=analysis_version,
        )

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            self._create_phase_two_database(database_path)
            pending_before = get_unanalyzed_messages(
                database_path=database_path,
                analysis_version=analysis_version,
            )
            first_updated = store_message_analyses(
                [analysis], database_path=database_path
            )
            second_updated = store_message_analyses(
                [analysis], database_path=database_path
            )
            pending_after = get_unanalyzed_messages(
                database_path=database_path,
                analysis_version=analysis_version,
            )
            ai_stats = get_ai_daily_stats(
                database_path=database_path,
                analysis_version=analysis_version,
            )
            with closing(sqlite3.connect(database_path)) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(messages)")
                }

        self.assertEqual([message.message_id for message in pending_before], [10])
        self.assertEqual(first_updated, 1)
        self.assertEqual(second_updated, 0)
        self.assertEqual(pending_after, [])
        self.assertEqual(ai_stats[0]["analyzed_count"], 1)
        self.assertEqual(ai_stats[0]["bullish_count"], 1)
        self.assertEqual(ai_stats[0]["agreement_count"], 1)
        self.assertIn("analysis_version", columns)
        self.assertIn("ai_model_revision", columns)

    def test_new_analysis_version_requeues_and_updates_message(self) -> None:
        old = MessageAnalysis(
            10, "Bullish", 0.92, "test-model", "revision-a", "positive",
            False, 0.60, "version-a"
        )
        new = MessageAnalysis(
            10, "Bearish", 0.88, "test-model", "revision-b", "negative",
            False, 0.60, "version-b"
        )

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            self._create_phase_two_database(database_path)
            self.assertEqual(store_message_analyses([old], database_path=database_path), 1)
            pending = get_unanalyzed_messages(
                database_path=database_path, analysis_version="version-b"
            )
            self.assertEqual([message.message_id for message in pending], [10])
            self.assertEqual(store_message_analyses([new], database_path=database_path), 1)
            stats = get_ai_daily_stats(
                database_path=database_path, analysis_version="version-b"
            )

        self.assertEqual(stats[0]["bearish_count"], 1)

    def test_explicit_overwrite_reanalyzes_current_version(self) -> None:
        first = MessageAnalysis(
            10, "Bullish", 0.92, "test-model", "revision-a", "positive",
            False, 0.60, "version-a"
        )
        replacement = MessageAnalysis(
            10, "Bearish", 0.88, "test-model", "revision-a", "negative",
            False, 0.60, "version-a"
        )

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            self._create_phase_two_database(database_path)
            self.assertEqual(store_message_analyses([first], database_path=database_path), 1)
            self.assertEqual(
                store_message_analyses([replacement], database_path=database_path), 0
            )
            self.assertEqual(
                store_message_analyses(
                    [replacement], database_path=database_path, overwrite=True
                ),
                1,
            )
            stats = get_ai_daily_stats(
                database_path=database_path, analysis_version="version-a"
            )

        self.assertEqual(stats[0]["bearish_count"], 1)

    @staticmethod
    def _create_phase_two_database(database_path: Path) -> None:
        """Create a genuine pre-AI database for migration tests."""

        with closing(sqlite3.connect(database_path)) as connection:
            with connection:
                connection.executescript(
                    """
                CREATE TABLE messages (
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
                CREATE TABLE daily_stats (
                    stat_date TEXT PRIMARY KEY,
                    total_messages INTEGER NOT NULL,
                    bullish_count INTEGER NOT NULL,
                    bearish_count INTEGER NOT NULL,
                    unlabeled_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO messages VALUES (
                    10, '$TSLA looks strong', '2026-08-05T03:00:00Z',
                    'Bullish', '["TSLA"]', 'tester', 5,
                    'https://example.com/10', '{}', '2026-08-05T04:00:00Z'
                );
                    """
                )


if __name__ == "__main__":
    unittest.main()
