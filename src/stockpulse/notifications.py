"""Secret-safe, deduplicated email notifications for production pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import escape
import smtplib
from typing import Any, Protocol

from stockpulse.anomaly import AnomalyResult, evaluate_anomaly
from stockpulse.config import Settings


class EmailSender(Protocol):
    """Small interface that keeps SMTP out of pipeline tests."""

    def send(
        self, *, subject: str, body: str, html_body: str | None = None
    ) -> None: ...


class NotificationTestError(RuntimeError):
    """Raised when an explicit notification smoke test cannot be delivered."""


@dataclass(frozen=True)
class SMTPEmailSender:
    """Send a multipart email through a TLS-protected SMTP connection."""

    settings: Settings

    def send(
        self, *, subject: str, body: str, html_body: str | None = None
    ) -> None:
        if not self.settings.has_email_config:
            raise ValueError("Email delivery is not fully configured.")
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.email_from
        message["To"] = self.settings.email_to
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

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
        subject, body, html_body = anomaly_alert_email(
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
        html_body = None

    test_subject = f"[TEST] {subject}"
    test_body = "TEST ONLY — no production alert occurred.\n\n" + body
    if html_body:
        html_body = html_body.replace(
            "<!-- email-preheader -->",
            '<!-- email-preheader --><div style="background:#fbbf24;color:#111827;'
            'font:bold 14px Arial,sans-serif;text-align:center;padding:10px">'
            "TEST ONLY — no production alert occurred.</div>",
            1,
        )
    transport = sender or SMTPEmailSender(settings)
    try:
        transport.send(subject=test_subject, body=test_body, html_body=html_body)
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
) -> tuple[str, str, str]:
    """Render a multipart once-per-day summary."""

    stat_date = str(metric["stat_date"])
    score = float(metric["sentiment_score"])
    label, tone, summary = _sentiment_view(score)
    analyzed = int(metric["analyzed_count"])
    bullish = int(metric["bullish_count"])
    neutral = int(metric["neutral_count"])
    bearish = int(metric["bearish_count"])
    subject = f"StockPulse Daily — {settings.symbol} sentiment is {label.lower()}"
    lines = [
        f"StockPulse Daily — {settings.symbol} — {stat_date}",
        "",
        f"{label}: {summary}",
        f"Sentiment score: {score:+.2f}",
        f"Bullish / Neutral / Bearish: {_percent(bullish, analyzed)} / "
        f"{_percent(neutral, analyzed)} / {_percent(bearish, analyzed)}",
        f"Messages analyzed: {analyzed}",
        f"Average confidence: {float(metric['average_confidence']):.1%}",
        "",
        "What this means",
        _daily_interpretation(label, bullish, neutral, bearish),
        "This is a measure of discussion tone, not a forecast of the stock price.",
        "",
        "What to watch next",
        _watch_next(anomaly, label),
        "",
        "Anomaly check",
        _anomaly_text(anomaly),
        "",
        "Latest collection",
        (
            "Collected / new / duplicates / successfully analyzed: "
            f"{run_counts['messages']} / {run_counts['inserted']} / "
            f"{run_counts['duplicates']} / {run_counts['analyzed']}"
        ),
        "",
        "Professional readout",
        "Sentiment methodology: each message is classified as bullish, neutral, "
        "or bearish; the daily score aggregates those classifications on a -1.00 "
        "to +1.00 scale.",
        "Model confidence: the average classification probability across analyzed "
        "messages. It measures model certainty, not market or investment certainty.",
        "Anomaly methodology: the latest metrics are compared with a rolling median "
        "of prior eligible days using explicit, versioned thresholds.",
        "Reproducibility: analysis version, detector version, history window, and "
        "run ID allow the result to be traced and replayed.",
        "",
        f"Run ID: {run_id}",
    ]
    _append_link(lines, "Dashboard", settings.dashboard_url)
    text_body = "\n".join(lines) + "\n"
    html_body = _daily_html(
        settings=settings, run_id=run_id, stat_date=stat_date, score=score,
        label=label, tone=tone, summary=summary, analyzed=analyzed,
        bullish=bullish, neutral=neutral, bearish=bearish,
        confidence=float(metric["average_confidence"]), run_counts=run_counts,
        anomaly=anomaly,
    )
    return subject, text_body, html_body


def anomaly_alert_email(
    *, settings: Settings, run_id: str, result: AnomalyResult
) -> tuple[str, str, str]:
    """Render a detailed anomaly explanation and its supporting measurements."""

    signals = ", ".join(result.signals) or "none"
    direction = _shift_direction(result.sentiment_shift)
    subject = (
        f"⚠️ StockPulse Alert — {result.severity.title()} {direction} shift "
        f"detected in {settings.symbol}"
    )
    lines = [
        f"StockPulse detected an anomaly for {settings.symbol}.",
        "",
        f"Severity: {result.severity}",
        f"Signals: {signals}",
        f"Explanation: {result.explanation}",
        "",
        "Why flagged",
        result.explanation,
        "In plain English: " + _plain_alert_takeaway(result),
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
        "What to do next",
        "1. Review the messages and source links behind the change.",
        "2. Check whether multiple independent discussions support the same story.",
        "3. Treat the alert as a research lead, not a buy or sell signal.",
        "",
        "Professional readout",
        "Baseline: rolling median of prior eligible days within the detector window.",
        f"Detector version: {result.detector_version}",
        f"Analysis version: {result.analysis_version}",
        f"Run ID: {run_id}",
    ]
    _append_link(lines, "Dashboard", settings.dashboard_url)
    text_body = "\n".join(lines) + "\n"
    return subject, text_body, _alert_html(settings, run_id, result)


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


def _sentiment_view(score: float) -> tuple[str, str, str]:
    if score >= 0.2:
        return "Mildly Bullish", "#22c55e", "Investor discussion leaned positive today."
    if score <= -0.2:
        return "Bearish", "#ef4444", "Investor discussion leaned negative today."
    return "Neutral", "#3b82f6", "Investor discussion was broadly balanced today."


def _daily_interpretation(
    label: str, bullish: int, neutral: int, bearish: int
) -> str:
    total = bullish + neutral + bearish
    neutral_share = _percent(neutral, total)
    if label == "Neutral":
        return (
            "Discussion is balanced; neither bullish nor bearish messages dominate. "
            f"Neutral messages represent {neutral_share} of everything analyzed."
        )
    stronger, weaker = (bullish, bearish) if label == "Mildly Bullish" else (bearish, bullish)
    direction = "Bullish" if label == "Mildly Bullish" else "Bearish"
    if weaker:
        ratio = f"{stronger / weaker:.1f} to 1"
    else:
        ratio = f"{stronger} to 0"
    return (
        f"Among directional messages, {direction.lower()} views outnumbered the "
        f"opposite view {ratio}. Neutral messages still represented {neutral_share} "
        "of everything analyzed."
    )


def _anomaly_text(anomaly: AnomalyResult | None) -> str:
    if anomaly is None:
        return "Not evaluated for this run."
    if anomaly.status == "insufficient_history":
        return f"Building historical baseline: {anomaly.history_days} of 7 required days available."
    if anomaly.status == "normal":
        return "No unusual movement detected against the recent baseline."
    return f"{anomaly.severity.title()} anomaly detected: {anomaly.explanation}"


def _percent(count: int, total: int) -> str:
    return f"{count / total:.0%}" if total else "0%"


def _shift_direction(shift: float | None) -> str:
    if shift is None or shift == 0:
        return "Unusual"
    return "Bullish" if shift > 0 else "Bearish"


def _watch_next(anomaly: AnomalyResult | None, label: str) -> str:
    if anomaly is None or anomaly.status == "insufficient_history":
        return (
            "Keep watching whether this tone persists as StockPulse builds a more "
            "reliable historical baseline. One day alone is not a trend."
        )
    if anomaly.status == "anomaly":
        return (
            "Review the messages behind the alert and check whether the shift "
            "continues across the next collection window."
        )
    return (
        f"Today's {label.lower()} tone remains within the recent range. A repeated "
        "move in the same direction would be more meaningful than a single reading."
    )


def _plain_alert_takeaway(result: AnomalyResult) -> str:
    pieces = []
    if "volume_spike" in result.signals:
        pieces.append(
            f"people are discussing the stock about {_number(result.volume_ratio, suffix='x')} "
            "as much as on a typical recent day"
        )
    if "bullish_shift" in result.signals or "bearish_shift" in result.signals:
        pieces.append(
            f"the overall tone moved {_shift_direction(result.sentiment_shift).lower()} "
            f"by {abs(result.sentiment_shift or 0):.2f} points"
        )
    if "topic_shift" in result.signals and result.shifted_topic:
        pieces.append(f"{result.shifted_topic} became unusually prominent")
    if not pieces:
        return "the discussion pattern crossed an anomaly threshold."
    return "; and ".join(pieces).capitalize() + "."


def _distribution_bar(bullish: int, neutral: int, bearish: int, total: int) -> str:
    widths = [
        round(100 * bullish / total) if total else 0,
        round(100 * neutral / total) if total else 0,
        round(100 * bearish / total) if total else 0,
    ]
    return f'''<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:14px"><tr>
<td width="{widths[0]}%" bgcolor="#22c55e" height="10" style="font-size:0;line-height:0">&nbsp;</td>
<td width="{widths[1]}%" bgcolor="#60a5fa" height="10" style="font-size:0;line-height:0">&nbsp;</td>
<td width="{widths[2]}%" bgcolor="#ef4444" height="10" style="font-size:0;line-height:0">&nbsp;</td>
</tr></table>'''


def _daily_professional_panel(data: dict[str, Any]) -> str:
    anomaly = data["anomaly"]
    if anomaly is None:
        baseline = "Not evaluated in this run"
        detector = "Not available"
    elif anomaly.status == "insufficient_history":
        baseline = f"{anomaly.history_days} prior days available; 7 required"
        detector = anomaly.detector_version
    else:
        baseline = (
            f"Rolling median across {anomaly.history_days} prior eligible days"
        )
        detector = anomaly.detector_version
    return f'''<div style="margin-top:24px;background:#0b2342;border-radius:14px;overflow:hidden;color:#fff">
<div style="padding:21px 22px;background:#102e53;border-bottom:1px solid #274669"><div style="font-size:11px;color:#56d6ff;font-weight:800;letter-spacing:1.5px">PROFESSIONAL ANALYSIS</div><div style="margin-top:7px;font-size:20px;font-weight:800">How StockPulse produced this reading</div><div style="margin-top:7px;color:#b6c8dc;font-size:13px;line-height:1.55">The result is designed to be explainable, versioned, and reproducible—not a black-box market prediction.</div></div>
<div style="padding:5px 22px 20px">
{_method_row("01", "Sentiment methodology", "Each analyzed message is classified as bullish, neutral, or bearish. The daily score aggregates those classifications on a −1.00 to +1.00 scale, where zero represents a balanced mix.", f'Today: {data["score"]:+.2f}')}
{_method_row("02", "Model confidence", "Average confidence summarizes how certain the language model was about its message-level labels. It is model certainty—not confidence that a stock will rise or fall.", f'Today: {data["confidence"]:.1%}')}
{_method_row("03", "Historical comparison", "Daily activity and sentiment are compared with a rolling median of prior eligible days. Median baselines reduce the influence of one unusually noisy day.", baseline)}
{_method_row("04", "Reproducibility", "Detector thresholds and analysis versions are stored with the result so the same data can be replayed and audited later.", f'Run: {data["run_id"]}')}
<div style="margin-top:14px;padding:12px 14px;background:#071a32;border-radius:8px;color:#8fa8c3;font-size:10px;line-height:1.5;word-break:break-word"><b style="color:#bcd0e6">Detector version:</b> {escape(detector)}</div>
</div></div>'''


def _alert_professional_panel(result: AnomalyResult, run_id: str) -> str:
    severity_reason = (
        f"{result.severity.title()} because {len(result.signals)} independent "
        "thresholds were crossed"
    )
    comparison = (
        f"{result.current_messages} messages today vs. "
        f"{_number(result.baseline_messages)} median; sentiment "
        f"{result.current_sentiment:+.2f} vs. {_signed(result.baseline_sentiment)}"
    )
    return f'''<div style="margin-top:24px;background:#0b2342;border-radius:14px;overflow:hidden;color:#fff">
<div style="padding:21px 22px;background:#102e53;border-bottom:1px solid #274669"><div style="font-size:11px;color:#56d6ff;font-weight:800;letter-spacing:1.5px">PROFESSIONAL ANALYSIS</div><div style="margin-top:7px;font-size:20px;font-weight:800">Why this qualifies as an anomaly</div><div style="margin-top:7px;color:#b6c8dc;font-size:13px;line-height:1.55">StockPulse compares the latest observation with a robust historical baseline and only alerts when explicit thresholds are crossed.</div></div>
<div style="padding:5px 22px 20px">
{_method_row("01", "Baseline construction", "The reference value is the rolling median of prior eligible days. A median is less sensitive than a mean to one unusually active or emotional day.", f'{result.history_days} prior days')}
{_method_row("02", "Observed deviation", "Today’s activity and sentiment are evaluated separately against their historical reference values, so the evidence remains interpretable.", comparison)}
{_method_row("03", "Severity assignment", "One crossed threshold produces a medium alert; multiple independent signals produce a high alert. Severity describes statistical unusualness, not investment risk.", severity_reason)}
{_method_row("04", "Reproducibility", "The analysis version, detector configuration, evidence, and run identifier are retained so this alert can be replayed and audited.", f'Run: {run_id}')}
<div style="margin-top:14px;padding:12px 14px;background:#071a32;border-radius:8px;color:#8fa8c3;font-size:10px;line-height:1.5;word-break:break-word"><b style="color:#bcd0e6">Detector version:</b> {escape(result.detector_version)}<br><b style="color:#bcd0e6">Analysis version:</b> {escape(result.analysis_version)}</div>
</div></div>'''


def _method_row(number: str, title: str, explanation: str, value: str) -> str:
    return f'''<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-bottom:1px solid #274669"><tr><td width="38" valign="top" style="padding:16px 0;color:#56d6ff;font-size:12px;font-weight:800">{number}</td><td valign="top" style="padding:15px 10px 15px 0"><div style="font-size:14px;font-weight:800;color:#f4f8fc">{escape(title)}</div><div style="margin-top:5px;color:#aebfd2;font-size:12px;line-height:1.55">{escape(explanation)}</div></td><td width="125" align="right" valign="top" style="padding:16px 0;color:#dbe8f5;font-size:11px;font-weight:700">{escape(value)}</td></tr></table>'''


def _signal_badges(signals: tuple[str, ...], color: str) -> str:
    cells = "".join(
        f'<td style="padding:0 6px 6px 0"><span style="display:inline-block;padding:7px 10px;background:#fff;border:1px solid {color};border-radius:20px;color:{color};font-size:11px;font-weight:800;text-transform:uppercase">{escape(signal.replace("_", " "))}</span></td>'
        for signal in signals
    )
    return f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:13px"><tr>{cells}</tr></table>'


def _shell(preheader: str, content: str) -> str:
    return f'''<!doctype html><html><body style="margin:0;padding:0;background:#eef2f7;">
<!-- email-preheader --><div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{escape(preheader)}</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f7"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="640" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:640px;background:#ffffff;border-radius:18px;overflow:hidden;font-family:Arial,sans-serif;color:#172033;box-shadow:0 12px 36px rgba(7,29,59,.12)">
<tr><td style="background:#071d3b;padding:27px 32px;color:#ffffff"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td><span style="font-size:24px;font-weight:800;letter-spacing:.2px">Stock<span style="color:#56d6ff">Pulse</span></span><br><span style="font-size:11px;color:#a9bdd7;letter-spacing:1.8px">INVESTOR SENTIMENT INTELLIGENCE</span></td><td align="right"><span style="display:inline-block;padding:7px 10px;border:1px solid #315071;border-radius:20px;color:#bcd0e6;font-size:10px;font-weight:700">DAILY MONITOR</span></td></tr></table></td></tr>
{content}</table></td></tr></table></body></html>'''


def _daily_html(**data: Any) -> str:
    settings = data["settings"]
    anomaly = data["anomaly"]
    status_color = "#f59e0b" if anomaly is None or anomaly.status == "insufficient_history" else ("#22c55e" if anomaly.status == "normal" else "#ef4444")
    cta = _cta(settings.dashboard_url, "View Full Dashboard →", data["tone"])
    rows = "".join(
        _metric_cell(label, value, color)
        for label, value, color in (
            ("BULLISH", _percent(data["bullish"], data["analyzed"]), "#16a34a"),
            ("NEUTRAL", _percent(data["neutral"], data["analyzed"]), "#3b82f6"),
            ("BEARISH", _percent(data["bearish"], data["analyzed"]), "#dc2626"),
        )
    )
    counts = data["run_counts"]
    content = f'''
<tr><td style="padding:32px"><div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.2px">DAILY BRIEF · {escape(settings.symbol)} · {escape(data["stat_date"])}</div>
<div style="margin-top:10px;font-size:17px;line-height:1.45;font-weight:700;color:#172033">Today’s investor conversation leaned <span style="color:{data["tone"]}">{escape(data["label"].lower())}</span>. Read this as discussion context—not a price forecast.</div>
<div style="margin-top:18px;padding:24px;border-radius:14px;background:#f3f8ff;border:1px solid #dce9f8;border-left:6px solid {data["tone"]}"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td><div style="font-size:12px;font-weight:800;color:#64748b;letter-spacing:1px">TODAY'S PULSE</div><div style="font-size:26px;font-weight:800;color:{data["tone"]};margin-top:7px">{escape(data["label"])}</div><div style="color:#526178;margin-top:7px;line-height:1.5">{escape(data["summary"])}</div></td><td width="125" align="right" valign="middle"><div style="font-size:11px;color:#64748b">SENTIMENT SCORE</div><div style="font-size:40px;font-weight:800;color:#172033;margin-top:4px">{data["score"]:+.2f}</div><div style="font-size:10px;color:#94a3b8">−1.00 to +1.00</div></td></tr></table></div>
<table role="presentation" width="100%" cellspacing="8" cellpadding="0" border="0" style="margin:18px -8px 0">{rows}</table>
{_distribution_bar(data["bullish"], data["neutral"], data["bearish"], data["analyzed"])}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td style="padding:10px 0;color:#526178">Messages analyzed</td><td align="right" style="font-weight:700">{data["analyzed"]}</td></tr><tr><td style="padding:10px 0;color:#526178;border-top:1px solid #e5eaf1">Average confidence</td><td align="right" style="font-weight:700;border-top:1px solid #e5eaf1">{data["confidence"]:.1%}</td></tr></table>
<div style="margin-top:18px;padding:14px 16px;background:#f8fafc;border-radius:9px"><span style="font-size:12px;font-weight:800;color:#172033">PLAIN ENGLISH · </span><span style="font-size:12px;color:#526178;line-height:1.5">{escape(_daily_interpretation(data["label"], data["bullish"], data["neutral"], data["bearish"]))}</span></div>
<div style="margin-top:18px;padding:18px 20px;background:#f8fafc;border-radius:12px;border:1px solid #e5eaf1"><div style="font-size:12px;font-weight:800;color:#172033;text-transform:uppercase;letter-spacing:1px">What to watch next</div><div style="margin-top:8px;color:#526178;line-height:1.6">{escape(_watch_next(anomaly, data["label"]))}</div></div>
<div style="margin-top:18px;padding:16px;background:#f8fafc;border:1px solid #e5eaf1;border-radius:10px"><div style="font-size:12px;font-weight:700;color:{status_color};text-transform:uppercase">Anomaly check</div><div style="margin-top:7px;line-height:1.55">{escape(_anomaly_text(anomaly))}</div></div>
{_section("Latest collection", f'Collected {counts["messages"]} · New {counts["inserted"]} · Duplicates {counts["duplicates"]} · Successfully analyzed {counts["analyzed"]}')}
{_daily_professional_panel(data)}
{cta}</td></tr>{_footer(f'Run ID: {data["run_id"]}', "StockPulse monitors discussion patterns. It does not predict prices or provide investment advice.")}'''
    return _shell(f'{settings.symbol} sentiment is {data["label"].lower()}', content)


def _alert_html(settings: Settings, run_id: str, result: AnomalyResult) -> str:
    high = result.severity == "high"
    accent = "#dc2626" if high else "#f97316"
    direction = _shift_direction(result.sentiment_shift)
    signal_names = ", ".join(signal.replace("_", " ").title() for signal in result.signals)
    content = f'''
<tr><td style="background:{accent};padding:15px 32px;color:#fff"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr><td style="font-size:13px;font-weight:800;letter-spacing:1.2px">⚠ {result.severity.upper()} SEVERITY</td><td align="right" style="font-size:11px;font-weight:700">{len(result.signals)} INDEPENDENT SIGNALS</td></tr></table></td></tr>
<tr><td style="padding:32px"><div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.2px">ANOMALY BRIEF · {escape(settings.symbol)} · {escape(result.stat_date)}</div><div style="font-size:30px;line-height:1.2;font-weight:800;color:#991b1b;margin-top:14px">Something changed in the conversation.</div><div style="font-size:18px;line-height:1.5;font-weight:700;color:#172033;margin-top:8px">StockPulse detected a significant {direction.lower()} shift compared with the stock’s recent discussion pattern.</div>
<div style="margin-top:16px;padding:17px 19px;background:#fff7ed;border-left:5px solid {accent};border-radius:10px"><div style="font-size:11px;color:{accent};font-weight:800;letter-spacing:1px">IN PLAIN ENGLISH</div><div style="margin-top:7px;color:#523126;line-height:1.6;font-weight:600">{escape(_plain_alert_takeaway(result))}</div></div>
{_signal_badges(result.signals, accent)}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:20px;border:1px solid #fecaca;border-radius:10px"><tr style="background:#fff1f2"><td style="padding:12px;font-size:12px;font-weight:700">SIGNAL</td><td align="right" style="padding:12px;font-size:12px;font-weight:700">TODAY</td><td align="right" style="padding:12px;font-size:12px;font-weight:700">BASELINE</td><td align="right" style="padding:12px;font-size:12px;font-weight:700">CHANGE</td></tr>{_alert_row("Sentiment", f'{result.current_sentiment:+.2f}', _signed(result.baseline_sentiment), _signed(result.sentiment_shift), accent)}{_alert_row("Discussion activity", str(result.current_messages), _number(result.baseline_messages), _number(result.volume_ratio, suffix="×"), accent)}</table>
{_section("Why the system flagged this", result.explanation)}
<div style="margin-top:20px;padding:20px;background:#f8fafc;border:1px solid #e5eaf1;border-radius:12px"><div style="font-size:15px;font-weight:800;color:#172033">How a careful reader should use this</div><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:10px"><tr><td width="28" valign="top" style="color:{accent};font-weight:800;padding:6px 0">1</td><td style="padding:6px 0;color:#526178;line-height:1.5">Open the underlying messages and verify the source context.</td></tr><tr><td width="28" valign="top" style="color:{accent};font-weight:800;padding:6px 0">2</td><td style="padding:6px 0;color:#526178;line-height:1.5">Look for independent discussions supporting the same explanation.</td></tr><tr><td width="28" valign="top" style="color:{accent};font-weight:800;padding:6px 0">3</td><td style="padding:6px 0;color:#526178;line-height:1.5">Treat this as a research lead—not an automatic buy or sell signal.</td></tr></table></div>
<div style="margin-top:18px;padding:17px 19px;background:#fff7ed;border-left:4px solid {accent};border-radius:8px"><b>Current sentiment:</b> {_sentiment_view(result.current_sentiment)[0]} ({result.current_sentiment:+.2f}). <span style="color:#7c4a33">The score summarizes discussion tone on a −1.00 to +1.00 scale.</span></div>
{_alert_professional_panel(result, run_id)}
{_cta(settings.dashboard_url, "Investigate in Dashboard →", accent)}</td></tr>{_footer(f'Signals: {signal_names or "None"} · History: {result.history_days} days · Run ID: {run_id}', "StockPulse anomaly alerts describe discussion changes, not investment advice.")}'''
    return _shell(f'{result.severity.title()} {direction.lower()} shift detected in {settings.symbol}', content)


def _metric_cell(label: str, value: str, color: str) -> str:
    return f'<td width="33.33%" align="center" style="padding:14px 5px;background:#f8fafc;border-radius:9px"><div style="font-size:11px;color:#64748b">{label}</div><div style="font-size:22px;font-weight:800;color:{color};margin-top:5px">{value}</div></td>'


def _section(title: str, body: str) -> str:
    return f'<div style="margin-top:22px"><div style="font-size:16px;font-weight:800;color:#172033">{escape(title)}</div><div style="margin-top:7px;color:#526178;line-height:1.6">{escape(body)}</div></div>'


def _cta(url: str | None, label: str, color: str) -> str:
    if not url:
        return ""
    return f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin-top:26px"><tr><td bgcolor="{color}" style="border-radius:8px"><a href="{escape(url, quote=True)}" style="display:inline-block;padding:14px 24px;color:#fff;text-decoration:none;font-weight:700">{escape(label)}</a></td></tr></table>'


def _alert_row(label: str, today: str, baseline: str, change: str, color: str) -> str:
    return f'<tr><td style="padding:13px;border-top:1px solid #fee2e2;font-weight:700">{escape(label)}</td><td align="right" style="padding:13px;border-top:1px solid #fee2e2">{escape(today)}</td><td align="right" style="padding:13px;border-top:1px solid #fee2e2">{escape(baseline)}</td><td align="right" style="padding:13px;border-top:1px solid #fee2e2;color:{color};font-weight:800">{escape(change)}</td></tr>'


def _footer(technical: str, disclaimer: str) -> str:
    return f'<tr><td style="padding:20px 30px;background:#071d3b;color:#a9bdd7;font-size:11px;line-height:1.6"><div>{escape(disclaimer)}</div><div style="margin-top:8px;color:#738aa7">{escape(technical)}</div></td></tr>'


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
