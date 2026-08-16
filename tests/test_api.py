"""HTTP contract tests for the read-only dashboard API."""

from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from stockpulse.api import create_app  # noqa: E402


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = MagicMock()
        self.repository.get_ai_daily_stats.return_value = [
            {
                "stat_date": "2026-08-05",
                "analyzed_count": 10,
                "sentiment_score": 0.2,
            },
            {
                "stat_date": "2026-08-06",
                "analyzed_count": 12,
                "sentiment_score": -0.1,
            },
        ]
        self.repository.get_anomaly_history.return_value = []
        self.repository.get_run_history.return_value = []
        self.repository.get_topic_summary.return_value = []
        self.repository.get_topic_daily_stats.return_value = []
        self.repository.get_messages.return_value = []
        self.repository.get_run.return_value = None
        self.repository.check_ready.return_value = True
        self.client = TestClient(
            create_app(
                repository=self.repository,
                analysis_version="analysis-test-v1",
            )
        )

    def test_health_has_stable_versioned_contract(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["api_version"], "v1")

    def test_readiness_checks_database_separately_from_liveness(self) -> None:
        ready = self.client.get("/api/v1/ready")
        self.repository.check_ready.return_value = False
        unavailable = self.client.get("/api/v1/ready")

        self.assertEqual(ready.status_code, 200)
        self.assertEqual(ready.json()["status"], "ready")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json()["error"]["code"], "request_error")

    def test_overview_combines_latest_dashboard_data(self) -> None:
        self.repository.get_topic_summary.return_value = [
            {"topic": "Robotaxi", "message_count": 4, "average_score": 0.9}
        ]

        response = self.client.get("/api/v1/overview")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["symbol"], "TSLA")
        self.assertEqual(body["latest_metric"]["stat_date"], "2026-08-06")
        self.assertEqual(body["top_topics"][0]["topic"], "Robotaxi")
        self.assertEqual(body["versions"]["analysis"], "analysis-test-v1")

    def test_sentiment_history_filters_inclusive_date_range(self) -> None:
        response = self.client.get(
            "/api/v1/metrics/sentiment",
            params={"start_date": "2026-08-06", "end_date": "2026-08-06"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(response.json()["data"][0]["stat_date"], "2026-08-06")

    def test_invalid_date_range_returns_422(self) -> None:
        response = self.client.get(
            "/api/v1/topics/history",
            params={"start_date": "2026-08-07", "end_date": "2026-08-06"},
        )

        self.assertEqual(response.status_code, 422)
        self.repository.get_topic_daily_stats.assert_not_called()

    def test_anomaly_query_is_bounded_and_filtered(self) -> None:
        response = self.client.get(
            "/api/v1/anomalies", params={"anomalies_only": "true", "limit": 25}
        )

        self.assertEqual(response.status_code, 200)
        self.repository.get_anomaly_history.assert_called_with(
            analysis_version="analysis-test-v1",
            detector_version=response.json()["meta"]["detector_version"],
            anomalies_only=True,
            limit=25,
        )

    def test_limits_are_rejected_before_repository_access(self) -> None:
        response = self.client.get("/api/v1/runs", params={"limit": 101})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.repository.get_run_history.assert_not_called()

    def test_run_history_filters_and_detail_not_found(self) -> None:
        history = self.client.get(
            "/api/v1/runs",
            params={
                "status": "failed",
                "action": "collect",
                "start_date": "2026-08-01",
                "end_date": "2026-08-05",
                "limit": 10,
            },
        )
        missing = self.client.get("/api/v1/runs/missing-run")

        self.assertEqual(history.status_code, 200)
        self.repository.get_run_history.assert_called_with(
            limit=10,
            status="failed",
            action="collect",
            start_date="2026-08-01",
            end_date="2026-08-05",
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")
        self.assertEqual(missing.json()["error"]["message"], "Run not found")

    def test_run_detail_returns_complete_record(self) -> None:
        self.repository.get_run.return_value = {
            "run_id": "run-1",
            "status": "failed",
            "error_type": "ExampleError",
            "error_message": "bounded error",
        }

        response = self.client.get("/api/v1/runs/run-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["error_message"], "bounded error")

    def test_message_explorer_returns_stable_next_cursor(self) -> None:
        self.repository.get_messages.return_value = [
            {
                "message_id": message_id,
                "created_at": f"2026-08-0{message_id}T00:00:00+00:00",
                "body": f"message {message_id}",
                "topics": [],
            }
            for message_id in (3, 2, 1)
        ]

        first = self.client.get("/api/v1/messages", params={"limit": 2})

        self.assertEqual(first.status_code, 200)
        self.assertEqual([row["message_id"] for row in first.json()["data"]], [3, 2])
        self.assertTrue(first.json()["meta"]["has_more"])
        cursor = first.json()["meta"]["next_cursor"]
        self.repository.get_messages.return_value = []

        second = self.client.get(
            "/api/v1/messages", params={"limit": 2, "cursor": cursor}
        )

        self.assertEqual(second.status_code, 200)
        call = self.repository.get_messages.call_args
        self.assertEqual(call.kwargs["before_message_id"], 2)
        self.assertEqual(call.kwargs["before_created_at"], "2026-08-02T00:00:00+00:00")

    def test_message_filters_are_validated_before_query(self) -> None:
        invalid_cursor = self.client.get(
            "/api/v1/messages", params={"cursor": "not-a-cursor"}
        )
        invalid_confidence = self.client.get(
            "/api/v1/messages", params={"minimum_confidence": 1.5}
        )

        self.assertEqual(invalid_cursor.status_code, 422)
        self.assertEqual(invalid_confidence.status_code, 422)
        self.repository.get_messages.assert_not_called()


if __name__ == "__main__":
    unittest.main()
