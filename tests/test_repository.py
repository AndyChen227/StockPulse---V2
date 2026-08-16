"""Backend-neutral repository contract tests, currently exercised by SQLite."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.repository import SQLiteRepository, StockPulseRepository  # noqa: E402
from stockpulse.storage import RunResult  # noqa: E402


VALID_MESSAGE = {
    "messageId": 101,
    "body": "$TSLA repository contract",
    "createdAt": "2026-08-05T23:30:00-07:00",
    "sentiment": "Bullish",
    "symbols": ["TSLA"],
    "username": "tester",
    "userFollowers": 10,
    "url": "https://example.com/101",
}


class RepositoryContractMixin:
    """Tests that every future storage backend must pass unchanged."""

    repository: StockPulseRepository

    def test_message_write_is_idempotent_and_updates_daily_stats(self) -> None:
        first = self.repository.store_messages([VALID_MESSAGE])
        second = self.repository.store_messages([VALID_MESSAGE])
        stats = self.repository.get_daily_stats()

        self.assertEqual((first.inserted, first.duplicates), (1, 0))
        self.assertEqual((second.inserted, second.duplicates), (0, 1))
        self.assertEqual(stats[0]["stat_date"], "2026-08-06")
        self.assertEqual(stats[0]["total_messages"], 1)

    def test_run_lifecycle_preserves_operational_metadata(self) -> None:
        run_id = self.repository.start_run(
            "collect",
            symbol="TSLA",
            max_messages=5,
            max_total_charge_usd="0.05",
        )
        self.repository.finish_run(
            run_id,
            RunResult(
                status="succeeded",
                message_count=1,
                inserted_count=1,
                external_run_id="apify-run-1",
                external_dataset_id="dataset-1",
            ),
        )
        run = self.repository.get_run_history()[0]

        self.assertEqual(run["run_id"], run_id)
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["max_total_charge_usd"], "0.05")
        self.assertEqual(run["external_run_id"], "apify-run-1")
        self.assertEqual(run["external_dataset_id"], "dataset-1")


class SQLiteRepositoryContractTests(RepositoryContractMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "stockpulse.db"
        self.repository = SQLiteRepository(database_path)


if __name__ == "__main__":
    unittest.main()
