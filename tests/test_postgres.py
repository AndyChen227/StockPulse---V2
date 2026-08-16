"""Tests for PostgreSQL schema and connection foundations."""

from contextlib import nullcontext
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


class FakeResult:
    def __init__(self, row=None) -> None:
        self.row = row

    def fetchone(self):
        return self.row


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
        with patch.dict(sys.modules, {"psycopg_pool": fake_module}):
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


if __name__ == "__main__":
    unittest.main()
