"""Tests for safe SQLite history migration."""

from contextlib import closing
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.migration import inspect_sqlite  # noqa: E402
from stockpulse.storage import _create_schema  # noqa: E402


class MigrationInventoryTests(unittest.TestCase):
    def test_inventory_is_read_only_and_deterministic(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            with closing(sqlite3.connect(database_path)) as connection:
                _create_schema(connection)
                connection.commit()

            first = inspect_sqlite(database_path)
            second = inspect_sqlite(database_path)

        self.assertEqual(first, second)
        self.assertEqual(set(first), {
            "messages", "daily_stats", "daily_metrics", "runs",
            "message_topics", "anomaly_results",
        })
        self.assertTrue(all(count == 0 for count in first.values()))

    def test_inventory_rejects_unsupported_schema(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "stockpulse.db"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    "CREATE TABLE schema_migrations "
                    "(version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)"
                )
                connection.execute(
                    "INSERT INTO schema_migrations VALUES (999, 'future', 'now')"
                )
                connection.commit()

            with self.assertRaisesRegex(ValueError, "missing tables"):
                inspect_sqlite(database_path)


if __name__ == "__main__":
    unittest.main()
