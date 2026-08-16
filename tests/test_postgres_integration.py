"""Integration contract for Dashboard reads against ephemeral PostgreSQL."""

import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.migration import migrate_sqlite_to_postgres  # noqa: E402
from stockpulse.postgres import apply_postgres_migrations, create_postgres_pool  # noqa: E402
from stockpulse.postgres_repository import PostgresDashboardRepository  # noqa: E402
from stockpulse.storage import _create_schema  # noqa: E402
from tests.test_repository import RepositoryContractMixin  # noqa: E402


@unittest.skipUnless(os.getenv("STOCKPULSE_TEST_POSTGRES_URL"), "PostgreSQL test URL not set")
class PostgresDashboardIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = create_postgres_pool(
            os.environ["STOCKPULSE_TEST_POSTGRES_URL"], open_pool=True
        )
        with cls.pool.connection() as connection:
            apply_postgres_migrations(connection)
        cls.repository = PostgresDashboardRepository(cls.pool)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.pool.close()

    def setUp(self) -> None:
        with self.pool.connection() as connection:
            with connection.transaction():
                connection.execute(
                    "TRUNCATE message_topics, anomaly_results, daily_metrics, "
                    "daily_stats, runs, messages CASCADE"
                )
                connection.execute(
                    """INSERT INTO messages (
                           message_id, body, created_at, stocktwits_sentiment,
                           symbols_json, username, user_followers, url, raw_json,
                           collected_at, ai_sentiment, ai_confidence,
                           ai_low_confidence, analysis_version
                       ) VALUES (
                           101, 'Robotaxi launch looks strong',
                           '2026-08-06T00:00:00Z', 'Bullish', '["TSLA"]'::jsonb,
                           'tester', 10, 'https://example.com/101', '{}'::jsonb,
                           '2026-08-06T00:01:00Z', 'Bullish', 0.9, false,
                           'analysis-v1'
                       )"""
                )
                connection.execute(
                    """INSERT INTO daily_metrics VALUES (
                           '2026-08-06', 'analysis-v1', 1, 1, 0, 0, 0.9, 0,
                           1, 1, 1.0, '2026-08-06T01:00:00Z'
                       )"""
                )
                connection.execute(
                    """INSERT INTO message_topics VALUES (
                           101, 'Robotaxi', 1.0, '["robotaxi"]'::jsonb, 1,
                           'topics-v1', '2026-08-06T01:00:00Z'
                       )"""
                )
                connection.execute(
                    """INSERT INTO runs (
                           run_id, action, status, symbol, started_at,
                           finished_at, message_count, inserted_count
                       ) VALUES (
                           '00000000-0000-0000-0000-000000000001', 'collect',
                           'succeeded', 'TSLA', '2026-08-06T00:00:00Z',
                           '2026-08-06T00:00:10Z', 1, 1
                       )"""
                )
                connection.execute(
                    """INSERT INTO anomaly_results (
                           fingerprint, stat_date, analysis_version,
                           detector_version, status, severity, signals_json,
                           explanation, history_days, current_messages,
                           current_sentiment, created_at
                       ) VALUES (
                           'fingerprint-1', '2026-08-06', 'analysis-v1',
                           'detector-v1', 'anomaly', 'high',
                           '["volume_spike"]'::jsonb, 'Volume increased.', 7, 20,
                           -0.4, '2026-08-06T01:00:00Z'
                       )"""
                )

    def test_reads_dashboard_history_with_api_safe_values(self) -> None:
        metrics = self.repository.get_ai_daily_stats(analysis_version="analysis-v1")
        messages = self.repository.get_messages(
            topic="Robotaxi", topic_version="topics-v1"
        )
        topics = self.repository.get_topic_summary(topic_version="topics-v1")
        runs = self.repository.get_run_history(status="succeeded")
        anomalies = self.repository.get_anomaly_history(anomalies_only=True)

        self.assertTrue(self.repository.check_ready())
        self.assertEqual(metrics[0]["stat_date"], "2026-08-06")
        self.assertEqual(messages[0]["message_id"], 101)
        self.assertEqual(messages[0]["topics"][0]["topic"], "Robotaxi")
        self.assertEqual(topics[0]["message_count"], 1)
        self.assertEqual(runs[0]["run_id"], "00000000000000000000000000000001")
        self.assertEqual(anomalies[0]["signals"], ("volume_spike",))


@unittest.skipUnless(os.getenv("STOCKPULSE_TEST_POSTGRES_URL"), "PostgreSQL test URL not set")
class PostgresMigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = create_postgres_pool(
            os.environ["STOCKPULSE_TEST_POSTGRES_URL"], open_pool=True
        )
        with cls.pool.connection() as connection:
            apply_postgres_migrations(connection)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.pool.close()

    def setUp(self) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                "TRUNCATE message_topics, anomaly_results, daily_metrics, "
                "daily_stats, runs, messages CASCADE"
            )
            connection.commit()

    def test_full_history_migration_is_verified_and_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            source_path = Path(directory) / "stockpulse.db"
            with sqlite3.connect(source_path) as source:
                _create_schema(source)
                source.execute(
                    """INSERT INTO messages (
                           message_id, body, created_at, stocktwits_sentiment,
                           symbols_json, username, user_followers, url, raw_json,
                           collected_at, ai_sentiment, ai_confidence, ai_model,
                           ai_model_revision, ai_raw_label, ai_low_confidence,
                           ai_confidence_threshold, analysis_version, analyzed_at
                       ) VALUES (101, 'TSLA robotaxi', '2026-08-06T00:00:00+00:00',
                           'Bullish', '["TSLA"]', 'tester', 50,
                           'https://example.com/101', '{"messageId":101}',
                           '2026-08-06T00:01:00+00:00', 'Bullish', 0.9,
                           'model', 'revision', 'positive', 0, 0.6,
                           'analysis-v1', '2026-08-06T00:02:00+00:00')"""
                )
                source.execute(
                    "INSERT INTO daily_stats VALUES "
                    "('2026-08-06', 1, 1, 0, 0, '2026-08-06T00:01:00+00:00')"
                )
                source.execute(
                    """INSERT INTO daily_metrics VALUES (
                           '2026-08-06', 'analysis-v1', 1, 1, 0, 0, 0.9, 0,
                           1, 1, 1.0, '2026-08-06T00:02:00+00:00')"""
                )
                source.execute(
                    """INSERT INTO runs (
                           run_id, action, status, symbol, started_at, finished_at
                       ) VALUES ('00000000000000000000000000000001', 'collect',
                           'succeeded', 'TSLA', '2026-08-06T00:00:00+00:00',
                           '2026-08-06T00:01:00+00:00')"""
                )
                source.execute(
                    """INSERT INTO runs (
                           run_id, action, status, symbol, started_at, finished_at,
                           retry_of_run_id
                       ) VALUES ('00000000000000000000000000000002', 'resume',
                           'succeeded', 'TSLA', '2026-08-06T01:00:00+00:00',
                           '2026-08-06T01:01:00+00:00',
                           '00000000000000000000000000000001')"""
                )
                source.execute(
                    """INSERT INTO message_topics VALUES (
                           101, 'Robotaxi', 1.0, '["robotaxi"]', 1, 'topics-v1',
                           '2026-08-06T00:03:00+00:00')"""
                )
                source.execute(
                    """INSERT INTO anomaly_results (
                           fingerprint, stat_date, analysis_version,
                           detector_version, status, severity, signals_json,
                           explanation, history_days, current_messages,
                           current_sentiment, created_at
                       ) VALUES ('fingerprint-1', '2026-08-06', 'analysis-v1',
                           'detector-v1', 'normal', 'none', '[]', 'Normal day.',
                           7, 1, 1.0, '2026-08-06T00:04:00+00:00')"""
                )
                source.commit()

            first = migrate_sqlite_to_postgres(source_path, self.pool)
            second = migrate_sqlite_to_postgres(source_path, self.pool)

        self.assertEqual(first.source_counts, first.verified_counts)
        self.assertEqual(first.inserted_counts["runs"], 2)
        self.assertTrue(all(count == 0 for count in second.inserted_counts.values()))
        with self.pool.connection() as connection:
            retry = connection.execute(
                "SELECT retry_of_run_id FROM runs WHERE run_id = %s",
                ("00000000-0000-0000-0000-000000000002",),
            ).fetchone()
        self.assertEqual(str(retry["retry_of_run_id"]).replace("-", ""),
                         "00000000000000000000000000000001")


@unittest.skipUnless(os.getenv("STOCKPULSE_TEST_POSTGRES_URL"), "PostgreSQL test URL not set")
class PostgresRepositoryContractTests(RepositoryContractMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pool = create_postgres_pool(
            os.environ["STOCKPULSE_TEST_POSTGRES_URL"], open_pool=True
        )
        with cls.pool.connection() as connection:
            apply_postgres_migrations(connection)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.pool.close()

    def setUp(self) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                "TRUNCATE message_topics, anomaly_results, daily_metrics, "
                "daily_stats, runs, messages CASCADE"
            )
            connection.commit()
        self.repository = PostgresDashboardRepository(self.pool)


if __name__ == "__main__":
    unittest.main()
