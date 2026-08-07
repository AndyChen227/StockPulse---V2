"""Tests for local raw JSON storage."""

from datetime import datetime, timezone
import json
from pathlib import Path
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
        messages = [
            {
                "messageId": 10,
                "body": "$TSLA looks strong",
                "createdAt": "2026-08-05T03:00:00Z",
                "sentiment": "Bullish",
                "symbols": ["TSLA"],
                "username": "tester",
                "userFollowers": 5,
                "url": "https://example.com/10",
            }
        ]
        analysis = MessageAnalysis(
            message_id=10,
            sentiment="Bullish",
            confidence=0.92,
            model_name="test-model",
        )

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            store_messages(messages, database_path=database_path)
            pending_before = get_unanalyzed_messages(database_path=database_path)
            first_updated = store_message_analyses(
                [analysis], database_path=database_path
            )
            second_updated = store_message_analyses(
                [analysis], database_path=database_path
            )
            pending_after = get_unanalyzed_messages(database_path=database_path)
            ai_stats = get_ai_daily_stats(database_path=database_path)

        self.assertEqual([message.message_id for message in pending_before], [10])
        self.assertEqual(first_updated, 1)
        self.assertEqual(second_updated, 0)
        self.assertEqual(pending_after, [])
        self.assertEqual(ai_stats[0]["analyzed_count"], 1)
        self.assertEqual(ai_stats[0]["bullish_count"], 1)
        self.assertEqual(ai_stats[0]["agreement_count"], 1)


if __name__ == "__main__":
    unittest.main()
