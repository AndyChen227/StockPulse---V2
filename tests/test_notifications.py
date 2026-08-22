"""Tests for email rendering, SMTP safety, and durable duplicate suppression."""

from datetime import datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.anomaly import evaluate_anomaly  # noqa: E402
from stockpulse.config import Settings  # noqa: E402
from stockpulse.notifications import (  # noqa: E402
    NotificationTestError,
    SMTPEmailSender,
    anomaly_alert_email,
    daily_summary_email,
    failure_alert_email,
    send_notification_smoke_test,
    should_send_daily_summary,
)
from stockpulse.repository import SQLiteRepository  # noqa: E402


class NotificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            email_enabled=True,
            smtp_username="owner@gmail.com",
            smtp_app_password="application-secret",
            email_from="owner@gmail.com",
            email_to="owner@gmail.com",
            dashboard_url="https://dashboard.example.com",
        )

    @patch("stockpulse.notifications.smtplib.SMTP")
    def test_smtp_uses_starttls_and_never_puts_password_in_message(self, smtp: MagicMock) -> None:
        sender = SMTPEmailSender(self.settings)
        sender.send(subject="Test", body="Safe body", html_body="<b>Safe HTML</b>")

        client = smtp.return_value.__enter__.return_value
        client.starttls.assert_called_once_with()
        client.login.assert_called_once_with(
            "owner@gmail.com", "application-secret"
        )
        message = client.send_message.call_args.args[0]
        self.assertNotIn("application-secret", message.as_string())
        self.assertTrue(message.is_multipart())
        self.assertIn("Safe body", message.get_body(preferencelist=("plain",)).get_content())
        self.assertIn("Safe HTML", message.get_body(preferencelist=("html",)).get_content())

    def test_daily_summary_is_short_and_contains_core_metrics(self) -> None:
        subject, body, html = daily_summary_email(
            settings=self.settings,
            run_id="run-1",
            run_counts={"messages": 5, "inserted": 3, "duplicates": 2, "analyzed": 3},
            metric={
                "stat_date": "2026-08-20", "sentiment_score": 0.6,
                "analyzed_count": 5, "bullish_count": 3, "neutral_count": 2,
                "bearish_count": 0, "average_confidence": 0.683,
            },
            anomaly=None,
        )

        self.assertIn("StockPulse Daily", subject)
        self.assertIn("Sentiment score: +0.60", body)
        self.assertIn("Bullish / Neutral / Bearish: 60% / 40% / 0%", body)
        self.assertIn("What this means", body)
        self.assertIn("Mildly Bullish", html)
        self.assertIn("View Full Dashboard", html)
        self.assertIn("role=\"presentation\"", html)
        self.assertNotIn("<script", html.lower())

    def test_alert_templates_explain_signal_and_failure_stage(self) -> None:
        metrics = [
            {
                "stat_date": f"2026-08-{day:02d}",
                "analysis_version": "v1", "analyzed_count": 10,
                "sentiment_score": 0.0,
            }
            for day in range(1, 8)
        ] + [{
            "stat_date": "2026-08-08", "analysis_version": "v1",
            "analyzed_count": 25, "sentiment_score": -0.5,
        }]
        result = evaluate_anomaly(metrics)
        _, anomaly_body, anomaly_html = anomaly_alert_email(
            settings=self.settings, run_id="run-2", result=result
        )
        _, failure_body = failure_alert_email(
            settings=self.settings,
            run_id="run-3",
            stage="sentiment analysis",
            error=RuntimeError("model unavailable"),
            run_counts={"messages": 5, "inserted": 5, "duplicates": 0, "analyzed": 0},
            external_run_id="apify-1",
        )

        self.assertIn("volume_spike", anomaly_body)
        self.assertIn("Evidence", anomaly_body)
        self.assertIn("HIGH SEVERITY", anomaly_html)
        self.assertIn("Why the system flagged this", anomaly_html)
        self.assertIn("IN PLAIN ENGLISH", anomaly_html)
        self.assertIn("PROFESSIONAL ANALYSIS", anomaly_html)
        self.assertIn("Discussion activity", anomaly_html)
        self.assertIn("Failed stage: sentiment analysis", failure_body)
        self.assertIn("Error type: RuntimeError", failure_body)

    def test_failure_email_redacts_configured_secrets(self) -> None:
        settings = Settings(
            api_token="apify-secret",
            database_url="postgresql://user:database-secret@example/db",
            smtp_app_password="gmail-secret",
        )
        _, body = failure_alert_email(
            settings=settings,
            run_id="run-4",
            stage="data collection",
            error=RuntimeError(
                "request apify-secret failed near "
                "postgresql://user:database-secret@example/db"
            ),
            run_counts={"messages": 0, "inserted": 0, "duplicates": 0, "analyzed": 0},
            external_run_id=None,
        )

        self.assertNotIn("apify-secret", body)
        self.assertNotIn("database-secret", body)
        self.assertIn("[REDACTED]", body)

    def test_daily_summary_waits_for_later_run(self) -> None:
        self.assertFalse(
            should_send_daily_summary(self.settings, datetime(2026, 8, 20, 9, 0))
        )
        self.assertTrue(
            should_send_daily_summary(self.settings, datetime(2026, 8, 20, 15, 0))
        )

    def test_smoke_tests_are_obvious_and_use_detailed_alert_templates(self) -> None:
        for kind, expected in (
            ("anomaly", "Evidence"),
            ("failure", "Failed stage: notification smoke test"),
        ):
            with self.subTest(kind=kind):
                sender = MagicMock()
                send_notification_smoke_test(
                    self.settings,
                    kind,
                    sender=sender,
                )

                subject = sender.send.call_args.kwargs["subject"]
                body = sender.send.call_args.kwargs["body"]
                self.assertTrue(subject.startswith("[TEST]"))
                self.assertTrue(body.startswith("TEST ONLY"))
                self.assertIn(expected, body)
                if kind == "anomaly":
                    html = sender.send.call_args.kwargs["html_body"]
                    self.assertIn("TEST ONLY", html)
                else:
                    self.assertIsNone(sender.send.call_args.kwargs["html_body"])

    def test_daily_anomaly_states_have_distinct_status_copy(self) -> None:
        base_metric = {
            "stat_date": "2026-08-20", "sentiment_score": 0.0,
            "analyzed_count": 10, "bullish_count": 2, "neutral_count": 6,
            "bearish_count": 2, "average_confidence": 0.75,
        }
        counts = {"messages": 10, "inserted": 10, "duplicates": 0, "analyzed": 10}
        insufficient = evaluate_anomaly([{**base_metric, "analysis_version": "v1"}])
        history = [
            {"stat_date": f"2026-08-{day:02d}", "analysis_version": "v1", "analyzed_count": 10, "sentiment_score": 0.0}
            for day in range(1, 8)
        ]
        normal = evaluate_anomaly(history + [{**base_metric, "analysis_version": "v1"}])

        _, insufficient_text, insufficient_html = daily_summary_email(
            settings=self.settings, run_id="run-i", run_counts=counts,
            metric=base_metric, anomaly=insufficient,
        )
        _, normal_text, normal_html = daily_summary_email(
            settings=self.settings, run_id="run-n", run_counts=counts,
            metric=base_metric, anomaly=normal,
        )
        self.assertIn("Building historical baseline", insufficient_text)
        self.assertIn("#f59e0b", insufficient_html)
        self.assertIn("No unusual movement detected", normal_text)
        self.assertIn("#22c55e", normal_html)

    def test_medium_alert_uses_orange_severity_style(self) -> None:
        history = [
            {"stat_date": f"2026-08-{day:02d}", "analysis_version": "v1", "analyzed_count": 10, "sentiment_score": 0.0}
            for day in range(1, 8)
        ]
        result = evaluate_anomaly(history + [{
            "stat_date": "2026-08-08", "analysis_version": "v1",
            "analyzed_count": 10, "sentiment_score": 0.5,
        }])
        _, text, html = anomaly_alert_email(
            settings=self.settings, run_id="run-medium", result=result
        )
        self.assertIn("Severity: medium", text)
        self.assertIn("MEDIUM SEVERITY", html)
        self.assertIn("#f97316", html)

    def test_smoke_test_transport_failure_is_secret_safe(self) -> None:
        sender = MagicMock()
        sender.send.side_effect = RuntimeError("application-secret")

        with self.assertRaisesRegex(
            NotificationTestError,
            "Test email delivery failed: RuntimeError",
        ) as context:
            send_notification_smoke_test(
                self.settings,
                "failure",
                sender=sender,
            )

        self.assertNotIn("application-secret", str(context.exception))

    def test_delivery_key_is_claimed_once_and_failed_send_can_retry(self) -> None:
        with TemporaryDirectory() as directory:
            repository = SQLiteRepository(Path(directory) / "stockpulse.db")
            self.assertTrue(repository.claim_notification("daily:TSLA:2026-08-20", "daily"))
            self.assertFalse(repository.claim_notification("daily:TSLA:2026-08-20", "daily"))
            repository.finish_notification(
                "daily:TSLA:2026-08-20", delivered=False, error_message="smtp down"
            )
            self.assertTrue(repository.claim_notification("daily:TSLA:2026-08-20", "daily"))
            repository.finish_notification("daily:TSLA:2026-08-20", delivered=True)
            self.assertFalse(repository.claim_notification("daily:TSLA:2026-08-20", "daily"))


if __name__ == "__main__":
    unittest.main()
