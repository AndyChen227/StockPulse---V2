"""Tests for the complete bounded daily pipeline."""

from pathlib import Path
from contextlib import nullcontext
from datetime import datetime
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.collector.apify_client import CollectionBatch  # noqa: E402
from stockpulse.config import Settings  # noqa: E402
from stockpulse.pipeline import (  # noqa: E402
    PipelineAlreadyRunningError,
    run_daily_pipeline,
)
from stockpulse.sentiment import (  # noqa: E402
    DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, SentimentResult,
    build_analysis_version,
)
from stockpulse.storage import PendingMessage, RunResult, TopicCandidate  # noqa: E402


class DailyPipelineTests(unittest.TestCase):
    def test_pipeline_materializes_every_stage_and_records_one_run(self) -> None:
        repository = MagicMock()
        repository.pipeline_guard.return_value = nullcontext(True)
        repository.start_run.return_value = "pipeline-run-1"
        repository.store_messages.return_value = SimpleNamespace(inserted=1, duplicates=0)
        repository.get_unanalyzed_messages.return_value = [
            PendingMessage(1, "TSLA robotaxi demand is strong", "Bullish")
        ]
        repository.store_message_analyses.return_value = 1
        repository.get_topic_candidates.return_value = [
            TopicCandidate(
                1, "TSLA robotaxi demand is strong", "2026-08-17T00:00:00+00:00",
                "Bullish", 0.9, 10, "https://example.com/1"
            )
        ]
        repository.get_ai_daily_stats.return_value = []
        batch = CollectionBatch([{"messageId": 1}], "apify-1", "dataset-1")
        analyzer = MagicMock()
        analyzer.analyze.return_value = [
            SentimentResult(
                "Bullish", 0.9, DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION,
                "positive", False, 0.6,
                build_analysis_version(DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, 0.6),
            )
        ]

        run_id = run_daily_pipeline(
            repository,
            Settings(api_token="test-token"),
            collector=MagicMock(return_value=batch),
            analyzer_factory=MagicMock(return_value=analyzer),
            raw_writer=MagicMock(return_value=Path("raw.json")),
        )

        self.assertEqual(run_id, "pipeline-run-1")
        repository.store_messages.assert_called_once_with(batch.messages)
        repository.store_message_analyses.assert_called_once()
        repository.store_message_topics.assert_called_once()
        repository.finish_run.assert_called_once_with(
            "pipeline-run-1",
            RunResult(
                status="succeeded", message_count=1, inserted_count=1,
                analyzed_count=1, external_run_id="apify-1",
                external_dataset_id="dataset-1",
            ),
        )

    def test_pipeline_failure_is_audited_and_propagated(self) -> None:
        repository = MagicMock()
        repository.pipeline_guard.return_value = nullcontext(True)
        repository.start_run.return_value = "pipeline-run-2"

        with self.assertRaisesRegex(RuntimeError, "collector failed"):
            run_daily_pipeline(
                repository,
                Settings(api_token="test-token"),
                collector=MagicMock(side_effect=RuntimeError("collector failed")),
                raw_writer=MagicMock(),
            )

        repository.finish_run.assert_called_once_with(
            "pipeline-run-2",
            RunResult(
                status="failed", error_type="RuntimeError",
                error_message="collector failed",
            ),
        )

    def test_overlapping_pipeline_stops_before_paid_collection(self) -> None:
        repository = MagicMock()
        repository.pipeline_guard.return_value = nullcontext(False)
        collector = MagicMock()

        with self.assertRaisesRegex(PipelineAlreadyRunningError, "already running"):
            run_daily_pipeline(
                repository,
                Settings(api_token="test-token"),
                collector=collector,
            )

        collector.assert_not_called()
        repository.start_run.assert_not_called()

    def test_later_run_sends_one_deduplicated_daily_summary(self) -> None:
        repository = MagicMock()
        repository.pipeline_guard.return_value = nullcontext(True)
        repository.start_run.return_value = "pipeline-run-email"
        repository.store_messages.return_value = SimpleNamespace(inserted=0, duplicates=1)
        repository.get_unanalyzed_messages.return_value = []
        repository.get_topic_candidates.return_value = []
        repository.get_topic_daily_stats.return_value = []
        repository.get_ai_daily_stats.return_value = [{
            "stat_date": "2026-08-20",
            "analysis_version": "v1",
            "analyzed_count": 5,
            "bullish_count": 3,
            "neutral_count": 2,
            "bearish_count": 0,
            "average_confidence": 0.68,
            "sentiment_score": 0.6,
        }]
        repository.claim_notification.return_value = True
        sender = MagicMock()
        settings = Settings(
            api_token="test-token",
            email_enabled=True,
            smtp_username="owner@gmail.com",
            smtp_app_password="application-secret",
            email_from="owner@gmail.com",
            email_to="owner@gmail.com",
        )

        run_daily_pipeline(
            repository,
            settings,
            collector=MagicMock(
                return_value=CollectionBatch([{"messageId": 1}], "apify-1", "dataset-1")
            ),
            raw_writer=MagicMock(return_value=Path("raw.json")),
            notification_sender=sender,
            now_factory=lambda: datetime(2026, 8, 20, 15, 0),
        )

        repository.claim_notification.assert_called_once_with(
            "daily:TSLA:2026-08-20",
            "daily_summary",
            run_id="pipeline-run-email",
        )
        sender.send.assert_called_once()
        self.assertIn("StockPulse Daily", sender.send.call_args.kwargs["subject"])
        self.assertIn("<html>", sender.send.call_args.kwargs["html_body"])
        repository.finish_notification.assert_called_once_with(
            "daily:TSLA:2026-08-20", delivered=True
        )


if __name__ == "__main__":
    unittest.main()
