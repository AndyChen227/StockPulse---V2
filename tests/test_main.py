"""Smoke test for the StockPulse command-line entry point."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.main import build_startup_message, main  # noqa: E402
from stockpulse.collector.apify_client import CollectionBatch  # noqa: E402
from stockpulse.config import Settings  # noqa: E402
from stockpulse.sentiment import (  # noqa: E402
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    SentimentResult,
    build_analysis_version,
)
from stockpulse.storage import PendingMessage, RunResult, TopicCandidate  # noqa: E402
from stockpulse.topics import TOPIC_ANALYSIS_VERSION  # noqa: E402
from stockpulse.anomaly import DETECTOR_VERSION  # noqa: E402


class MainTests(unittest.TestCase):
    def test_startup_message_contains_project_and_symbol(self) -> None:
        message = build_startup_message()

        self.assertIn("StockPulse", message)
        self.assertIn("TSLA", message)

    def test_preview_mode_does_not_collect(self) -> None:
        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()

    def test_collect_mode_stops_when_token_is_missing(self) -> None:
        with patch(
            "stockpulse.main.load_settings",
            side_effect=ValueError("APIFY_API_TOKEN is missing."),
        ), patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--collect"])

        self.assertEqual(exit_code, 1)
        collect_mock.assert_not_called()

    def test_daily_pipeline_requires_token_and_uses_one_orchestrator(self) -> None:
        settings = Settings(api_token="test-token")
        repository = MagicMock()
        with patch("stockpulse.main.load_settings", return_value=settings), patch(
            "stockpulse.main.run_daily_pipeline", return_value="pipeline-run-1"
        ) as pipeline_mock, patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--daily-pipeline"], repository=repository)

        self.assertEqual(exit_code, 0)
        pipeline_mock.assert_called_once()
        collect_mock.assert_not_called()

    def test_production_preflight_is_offline_and_secret_safe(self) -> None:
        settings = Settings(
            environment="production",
            database_backend="postgresql",
            database_url="postgresql://user:database-secret@db/stockpulse",
        )
        with patch("stockpulse.main.load_settings", return_value=settings), patch(
            "stockpulse.main.create_postgres_pool"
        ) as pool_mock, patch("stockpulse.main.SQLiteRepository") as sqlite_mock, patch(
            "builtins.print"
        ) as print_mock:
            exit_code = main(["--check-production-config", "service"])

        self.assertEqual(exit_code, 0)
        pool_mock.assert_not_called()
        sqlite_mock.assert_not_called()
        output = " ".join(str(call) for call in print_mock.call_args_list)
        self.assertIn("configuration is valid", output)
        self.assertNotIn("database-secret", output)

    def test_stats_mode_does_not_collect(self) -> None:
        daily_stats = [
            {
                "stat_date": "2026-08-05",
                "total_messages": 5,
                "bullish_count": 1,
                "bearish_count": 1,
                "unlabeled_count": 3,
                "updated_at": "2026-08-05T00:00:00+00:00",
            }
        ]

        repository = MagicMock()
        repository.get_daily_stats.return_value = daily_stats
        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--stats"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()

    @patch("stockpulse.main.SentimentAnalyzer")
    def test_analyze_mode_uses_only_local_stored_messages(
        self,
        analyzer_class_mock,
    ) -> None:
        repository = MagicMock()
        repository.start_run.return_value = "run-1"
        repository.get_unanalyzed_messages.return_value = [
            PendingMessage(1, "$TSLA looks strong", "Bullish")
        ]
        repository.store_message_analyses.return_value = 1
        analyzer_class_mock.return_value.analyze.return_value = [
            SentimentResult(
                sentiment="Bullish",
                confidence=0.90,
                model_name=DEFAULT_MODEL_NAME,
                model_revision=DEFAULT_MODEL_REVISION,
                raw_label="positive",
                low_confidence=False,
                confidence_threshold=0.60,
                analysis_version=build_analysis_version(
                    DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, 0.60
                ),
            )
        ]

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--analyze"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        repository.store_message_analyses.assert_called_once()
        repository.start_run.assert_called_once()
        repository.finish_run.assert_called_once_with(
            "run-1",
            RunResult(status="succeeded", message_count=1, analyzed_count=1),
        )

    def test_runs_mode_displays_history_without_collecting(self) -> None:
        history = [
            {
                "started_at": "2026-08-05T01:00:00+00:00",
                "action": "collect",
                "status": "succeeded",
                "message_count": 5,
                "inserted_count": 4,
                "duplicate_count": 1,
                "analyzed_count": 0,
            }
        ]
        repository = MagicMock()
        repository.get_run_history.return_value = history
        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--runs"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()

    def test_collect_mode_records_limits_and_apify_identifiers(self) -> None:
        settings = Settings(api_token="test-token")
        repository = MagicMock()
        repository.start_run.return_value = "app-run-1"
        batch = CollectionBatch(
            messages=[],
            external_run_id="apify-run-1",
            external_dataset_id="dataset-1",
        )
        storage_result = SimpleNamespace(inserted=0, duplicates=0)

        repository.store_messages.return_value = storage_result
        with patch("stockpulse.main.load_settings", return_value=settings), patch(
            "stockpulse.main.collect_messages", return_value=batch
        ), patch(
            "stockpulse.main.save_raw_messages", return_value=Path("raw.json")
        ):
            exit_code = main(["--collect"], repository=repository)

        self.assertEqual(exit_code, 0)
        repository.start_run.assert_called_once_with(
            "collect",
            symbol="TSLA",
            max_messages=5,
            max_total_charge_usd="0.05",
        )
        repository.finish_run.assert_called_once_with(
            "app-run-1",
            RunResult(
                status="succeeded",
                external_run_id="apify-run-1",
                external_dataset_id="dataset-1",
            ),
        )

    def test_topic_analysis_uses_only_local_messages(self) -> None:
        repository = MagicMock()
        repository.start_run.return_value = "topic-run-1"
        repository.get_topic_candidates.return_value = [
            TopicCandidate(
                message_id=1,
                body="Delivery demand is rising.",
                created_at="2026-08-05T00:00:00+00:00",
                ai_sentiment="Bullish",
                ai_confidence=0.9,
                user_followers=10,
                url="https://example.com/1",
            )
        ]
        repository.store_message_topics.return_value = 1

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--analyze-topics"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        repository.start_run.assert_called_once_with(
            "topics",
            symbol="TSLA",
            analysis_version=TOPIC_ANALYSIS_VERSION,
        )
        repository.store_message_topics.assert_called_once()
        repository.finish_run.assert_called_once_with(
            "topic-run-1",
            RunResult(status="succeeded", message_count=1, analyzed_count=1),
        )

    def test_topic_history_uses_only_local_metrics(self) -> None:
        repository = MagicMock()
        repository.get_topic_daily_stats.return_value = [
            {
                "stat_date": "2026-08-05",
                "topic": "Robotaxi",
                "message_count": 2,
                "bullish_count": 1,
                "neutral_count": 0,
                "bearish_count": 1,
                "sentiment_score": 0.0,
            }
        ]

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--topic-history"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        repository.get_topic_daily_stats.assert_called_once_with(
            topic_version=TOPIC_ANALYSIS_VERSION
        )

    def test_anomaly_detection_uses_local_metrics_and_records_run(self) -> None:
        repository = MagicMock()
        repository.start_run.return_value = "anomaly-run-1"
        repository.store_anomaly_results.return_value = 1
        repository.get_ai_daily_stats.return_value = [
            {
                "stat_date": f"2026-08-{day:02d}",
                "analysis_version": build_analysis_version(
                    DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, 0.60
                ),
                "analyzed_count": 10 if day < 8 else 25,
                "sentiment_score": 0.0 if day < 8 else -0.5,
            }
            for day in range(1, 9)
        ]
        repository.get_topic_daily_stats.return_value = []

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--detect-anomalies"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        repository.start_run.assert_called_once()
        repository.get_topic_daily_stats.assert_called_once_with(
            topic_version=TOPIC_ANALYSIS_VERSION
        )
        repository.store_anomaly_results.assert_called_once()
        repository.finish_run.assert_called_once_with(
            "anomaly-run-1",
            RunResult(status="succeeded", message_count=1, analyzed_count=1),
        )

    def test_anomaly_history_is_local_and_version_filtered(self) -> None:
        repository = MagicMock()
        repository.get_anomaly_history.return_value = []

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--anomalies"], repository=repository)

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        repository.get_anomaly_history.assert_called_once_with(
            analysis_version=build_analysis_version(
                DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, 0.60
            ),
            detector_version=DETECTOR_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
