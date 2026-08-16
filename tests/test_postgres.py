"""Tests for PostgreSQL schema and connection foundations."""

from contextlib import nullcontext
from datetime import date, datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.postgres import (  # noqa: E402
    POSTGRES_MIGRATIONS,
    POSTGRES_SCHEMA_VERSION,
    apply_postgres_migrations,
    create_postgres_pool,
)
from stockpulse.postgres_repository import PostgresDashboardRepository  # noqa: E402


class FakeResult:
    def __init__(self, row=None, rows=None) -> None:
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, version: int = 0) -> None:
        self.version = version
        self.executions = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).split())
        self.executions.append((normalized, params))
        if "MAX(version)" in normalized:
            return FakeResult((self.version,))
        if normalized.startswith("INSERT INTO schema_migrations"):
            self.version = int(params[0])
        return FakeResult()


class PostgresFoundationTests(unittest.TestCase):
    def test_migrations_are_ordered_and_use_native_postgres_types(self) -> None:
        self.assertEqual(
            [migration.version for migration in POSTGRES_MIGRATIONS],
            list(range(1, POSTGRES_SCHEMA_VERSION + 1)),
        )
        combined = "\n".join(migration.sql for migration in POSTGRES_MIGRATIONS)
        self.assertIn("TIMESTAMPTZ", combined)
        self.assertIn("JSONB", combined)
        self.assertIn("BIGINT PRIMARY KEY", combined)
        self.assertIn("NUMERIC(10, 4)", combined)

    def test_pending_migrations_apply_once_in_one_transaction(self) -> None:
        connection = FakeConnection()

        first = apply_postgres_migrations(connection)
        executions_after_first = len(connection.executions)
        second = apply_postgres_migrations(connection)

        self.assertEqual(first, POSTGRES_SCHEMA_VERSION)
        self.assertEqual(second, POSTGRES_SCHEMA_VERSION)
        self.assertEqual(connection.version, POSTGRES_SCHEMA_VERSION)
        self.assertEqual(
            sum(
                sql.startswith("INSERT INTO schema_migrations")
                for sql, _ in connection.executions
            ),
            POSTGRES_SCHEMA_VERSION,
        )
        self.assertEqual(len(connection.executions), executions_after_first + 3)

    def test_newer_database_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "newer"):
            apply_postgres_migrations(FakeConnection(POSTGRES_SCHEMA_VERSION + 1))

    def test_pool_is_bounded_and_closed_by_default(self) -> None:
        pool_class = MagicMock()
        fake_module = SimpleNamespace(ConnectionPool=pool_class)
        fake_rows = SimpleNamespace(dict_row="dict-row")
        fake_psycopg = SimpleNamespace(rows=fake_rows)
        with patch.dict(
            sys.modules,
            {
                "psycopg_pool": fake_module,
                "psycopg": fake_psycopg,
                "psycopg.rows": fake_rows,
            },
        ):
            create_postgres_pool(
                "postgresql://user:secret@db/stockpulse",
                min_size=2,
                max_size=5,
            )

        kwargs = pool_class.call_args.kwargs
        self.assertEqual(kwargs["min_size"], 2)
        self.assertEqual(kwargs["max_size"], 5)
        self.assertFalse(kwargs["open"])
        self.assertEqual(kwargs["kwargs"]["connect_timeout"], 10)
        self.assertEqual(kwargs["kwargs"]["row_factory"], "dict-row")

    def test_dashboard_repository_serializes_native_values(self) -> None:
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [
            {
                "stat_date": date(2026, 8, 6),
                "total_messages": 2,
                "bullish_count": 1,
                "bearish_count": 1,
                "unlabeled_count": 0,
                "updated_at": datetime(2026, 8, 6, tzinfo=timezone.utc),
            }
        ]
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = connection

        rows = PostgresDashboardRepository(pool).get_daily_stats()

        self.assertEqual(rows[0]["stat_date"], "2026-08-06")
        self.assertEqual(rows[0]["updated_at"], "2026-08-06T00:00:00+00:00")

    def test_dashboard_message_query_uses_stable_tuple_cursor(self) -> None:
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = []
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = connection

        PostgresDashboardRepository(pool).get_messages(
            before_created_at="2026-08-06T00:00:00+00:00",
            before_message_id=101,
            topic_version="topics-v1",
        )

        sql, params = connection.execute.call_args.args
        self.assertIn("(m.created_at, m.message_id) <", sql)
        self.assertEqual(params[:2], ("2026-08-06T00:00:00+00:00", 101))


if __name__ == "__main__":
    unittest.main()
