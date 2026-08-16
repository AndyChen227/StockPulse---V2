"""Backend-neutral repository contract tests, currently exercised by SQLite."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.repository import SQLiteRepository, StockPulseRepository  # noqa: E402
from stockpulse.storage import MessageAnalysis, MessageTopic, RunResult  # noqa: E402
from stockpulse.topics import (  # noqa: E402
    TOPIC_ANALYSIS_VERSION,
    extract_topics,
    select_representative_messages,
)


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

    def test_topic_lifecycle_is_versioned_idempotent_and_source_linked(self) -> None:
        self.repository.store_messages([VALID_MESSAGE])
        analysis_version = "test-analysis-v1"
        self.repository.store_message_analyses(
            [
                MessageAnalysis(
                    message_id=101,
                    sentiment="Bullish",
                    confidence=0.9,
                    model_name="test-model",
                    model_revision="test-revision",
                    raw_label="positive",
                    low_confidence=False,
                    confidence_threshold=0.6,
                    analysis_version=analysis_version,
                )
            ]
        )
        candidates = self.repository.get_topic_candidates(
            topic_version=TOPIC_ANALYSIS_VERSION,
            analysis_version=analysis_version,
            limit=10,
        )
        predictions = extract_topics("Delivery demand and inventory are improving.")
        assignments = [
            MessageTopic(
                message_id=101,
                topic=prediction.topic,
                score=prediction.score,
                matched_terms=prediction.matched_terms,
                rank=prediction.rank,
                topic_version=prediction.topic_version,
            )
            for prediction in predictions
        ]
        first = self.repository.store_message_topics(assignments)
        second = self.repository.store_message_topics(assignments)
        pending_after = self.repository.get_topic_candidates(
            topic_version=TOPIC_ANALYSIS_VERSION,
            analysis_version=analysis_version,
            limit=10,
        )
        summary = self.repository.get_topic_summary(
            topic_version=TOPIC_ANALYSIS_VERSION
        )
        representative_candidates = self.repository.get_representative_candidates(
            topic="Deliveries & Demand",
            topic_version=TOPIC_ANALYSIS_VERSION,
        )
        representatives = select_representative_messages(representative_candidates)

        self.assertEqual([candidate.message_id for candidate in candidates], [101])
        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(pending_after, [])
        self.assertEqual(summary[0]["topic"], "Deliveries & Demand")
        self.assertEqual(summary[0]["message_count"], 1)
        self.assertEqual(representatives[0].message_id, 101)
        self.assertEqual(representatives[0].url, "https://example.com/101")


class SQLiteRepositoryContractTests(RepositoryContractMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        database_path = Path(self.temporary_directory.name) / "stockpulse.db"
        self.repository = SQLiteRepository(database_path)


if __name__ == "__main__":
    unittest.main()
