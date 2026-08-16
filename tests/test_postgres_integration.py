"""Integration contract for Dashboard reads against ephemeral PostgreSQL."""

import os
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.postgres import apply_postgres_migrations, create_postgres_pool  # noqa: E402
from stockpulse.postgres_repository import PostgresDashboardRepository  # noqa: E402
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
