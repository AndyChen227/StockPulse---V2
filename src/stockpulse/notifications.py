"""Secret-safe, deduplicated email notifications for production pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
import smtplib
from typing import Any, Protocol

from stockpulse.anomaly import AnomalyResult, evaluate_anomaly
from stockpulse.config import Settings


class EmailSender(Protocol):
    """Small interface that keeps SMTP out of pipeline tests."""

    def send(self, *, subject: str, body: str) -> None: ...


class NotificationTestError(RuntimeError):
    """Raised when an explicit notification smoke test cannot be delivered."""


@dataclass(frozen=True)
class SMTPEmailSender:
    """Send one plain-text message through a TLS-protected SMTP connection."""

    settings: Settings

    def send(self, *, subject: str, body: str) -> None:
        if not self.settings.has_email_config:
            raise ValueError("Email delivery is not fully configured.")
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.email_from
        message["To"] = self.settings.email_to
        message.set_content(body)

        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.smtp_timeout_seconds,
        ) as client:
            client.starttls()
            client.login(
                self.settings.smtp_username,
                self.settings.smtp_app_password,
            )
            client.send_message(message)


def send_notification_smoke_test(
    settings: Settings,
    kind: str,
    *,
    sender: EmailSender | None = None,
) -> None:
    """Send an obvious test alert without Apify, database access, or deduplication."""

    if kind not in {"anomaly", "failure"}:
        raise ValueError("Notification test kind must be 'anomaly' or 'failure'.")
    if not settings.has_email_config:
        raise ValueError("Email delivery is not fully configured.")

    run_id = "notification-smoke-test"
    if kind == "anomaly":
        metrics = [
            {
                "stat_date": f"2026-08-{day:02d}",
                "analysis_version": "notification-test",
                "analyzed_count": 10,
                "sentiment_score": 0.0,
            }
            for day in range(1, 8)
        ] + [
            {
                "stat_date": "2026-08-08",
                "analysis_version": "notification-test",
                "analyzed_count": 25,
                "sentiment_score": -0.5,
            }
        ]
        subject, body = anomaly_alert_email(
            settings=settings,
            run_id=run_id,
            result=evaluate_anomaly(metrics),
        )
    else:
        subject, body = failure_alert_email(
            settings=settings,
            run_id=run_id,
            stage="notification smoke test",
            error=RuntimeError("Synthetic failure used to verify alert delivery."),
            run_counts={
                "messages": 0,
                "inserted": 0,
                "duplicates": 0,
                "analyzed": 0,
            },
            external_run_id=None,
        )

    test_subject = f"[TEST] {subject}"
    test_body = (
        "TEST ONLY — no production anomaly or pipeline failure occurred.\n\n" + body
    )
    transport = sender or SMTPEmailSender(settings)
    try:
        transport.send(subject=test_subject, body=test_body)
    except Exception as error:
        raise NotificationTestError(
            f"Test email delivery failed: {type(error).__name__}"
        ) from error


def daily_summary_email(
    *,
    settings: Settings,
    run_id: str,
    run_counts: dict[str, int],
    metric: dict[str, Any],
    anomaly: AnomalyResult | None,
) -> tuple[str, str]:
    """Render the deliberately compact once-per-day summary."""

    stat_date = str(metric["stat_date"])
    score = float(metric["sentiment_score"])
    subject = (
        f"[StockPulse Daily] {settings.symbol} {stat_date}: "
        f"sentiment {score:+.2f}, {int(metric['analyzed_count'])} messages"
    )
    lines = [
        f"StockPulse daily summary — {settings.symbol} — {stat_date}",
        "",
        f"Sentiment score: {score:+.2f}",
        f"Analyzed messages: {int(metric['analyzed_count'])}",
        (
            "Bullish / Neutral / Bearish: "
            f"{int(metric['bullish_count'])} / {int(metric['neutral_count'])} / "
            f"{int(metric['bearish_count'])}"
        ),
        f"Average confidence: {float(metric['average_confidence']):.1%}",
        (
            "This run — collected / new / duplicate / analyzed: "
            f"{run_counts['messages']} / {run_counts['inserted']} / "
            f"{run_counts['duplicates']} / {run_counts['analyzed']}"
        ),
        f"Anomaly status: {anomaly.status if anomaly else 'not evaluated'}",
        f"Run ID: {run_id}",
    ]
    _append_link(lines, "Dashboard", settings.dashboard_url)
    return subject, "\n".join(lines) + "\n"


def anomaly_alert_email(
    *, settings: Settings, run_id: str, result: AnomalyResult
) -> tuple[str, str]:
    """Render a detailed anomaly explanation and its supporting measurements."""

    signals = ", ".join(result.signals) or "none"
    subject = (
        f"[StockPulse ALERT] {settings.symbol} anomaly "
        f"({result.severity}) on {result.stat_date}"
    )
    lines = [
        f"StockPulse detected an anomaly for {settings.symbol}.",
        "",
        f"Severity: {result.severity}",
        f"Signals: {signals}",
        f"Explanation: {result.explanation}",
        "",
        "Evidence",
        f"- Current messages: {result.current_messages}",
        f"- Baseline messages: {_number(result.baseline_messages)}",
        f"- Volume ratio: {_number(result.volume_ratio, suffix='x')}",
        f"- Current sentiment: {result.current_sentiment:+.2f}",
        f"- Baseline sentiment: {_signed(result.baseline_sentiment)}",
        f"- Sentiment shift: {_signed(result.sentiment_shift)}",
        f"- Shifted topic: {result.shifted_topic or 'none'}",
        f"- History days: {result.history_days}",
        "",
        f"Run ID: {run_id}",
        "Suggested action: review the Dashboard messages and source links before "
        "drawing any market conclusion.",
    ]
    _append_link(lines, "Dashboard", settings.dashboard_url)
    return subject, "\n".join(lines) + "\n"


def failure_alert_email(
    *,
    settings: Settings,
    run_id: str,
    stage: str,
    error: Exception,
    run_counts: dict[str, int],
    external_run_id: str | None,
) -> tuple[str, str]:
    """Render a detailed operational failure without including secret values."""

    error_message = _safe_error_message(error, settings)
    subject = f"[StockPulse FAILED] {settings.symbol} pipeline at {stage}"
    lines = [
        f"The StockPulse pipeline failed for {settings.symbol}.",
        "",
        f"Failed stage: {stage}",
        f"Error type: {type(error).__name__}",
        f"Error message: {error_message}",
        f"Run ID: {run_id}",
        f"Apify run ID: {external_run_id or 'not started or unavailable'}",
        "",
        "Progress before failure",
        f"- Collected messages: {run_counts['messages']}",
        f"- New messages: {run_counts['inserted']}",
        f"- Duplicate messages: {run_counts['duplicates']}",
        f"- Analyzed messages: {run_counts['analyzed']}",
        "",
        "Suggested checks: open the Cloud Run execution logs, inspect the failed "
        "stage above, then confirm Apify, database, and email secrets are enabled.",
    ]
    _append_link(lines, "Dashboard", settings.dashboard_url)
    _append_link(lines, "Cloud Run Job", settings.cloud_run_job_url)
    return subject, "\n".join(lines) + "\n"


def should_send_daily_summary(settings: Settings, now: datetime) -> bool:
    """Only the later scheduled execution is eligible for the daily email."""

    return now.hour >= settings.daily_email_after_hour


def _append_link(lines: list[str], label: str, value: str | None) -> None:
    if value:
        lines.append(f"{label}: {value}")


def _number(value: float | None, *, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:.2f}{suffix}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}"


def _safe_error_message(error: Exception, settings: Settings) -> str:
    message = " ".join(str(error).split())[:1000] or "No error message"
    for secret in (
        settings.api_token,
        settings.database_url,
        settings.action_api_token,
        settings.smtp_app_password,
    ):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message
