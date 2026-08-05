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
    get_daily_stats,
    save_raw_messages,
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


if __name__ == "__main__":
    unittest.main()
