"""Versioned, explainable anomaly detection over daily StockPulse metrics."""

from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from statistics import median
from typing import Any, Sequence


DETECTOR_VERSION = (
    "1:rolling-median:lookback=28:min-history=7:min-messages=5:"
    "volume=2:sentiment=0.35:min-topic=3:topic-share=0.25"
)


@dataclass(frozen=True)
class AnomalyConfig:
    """Experimental thresholds kept explicit for replay and review."""

    lookback_days: int = 28
    minimum_history_days: int = 7
    minimum_current_messages: int = 5
    volume_ratio_threshold: float = 2.0
    sentiment_shift_threshold: float = 0.35
    minimum_topic_messages: int = 3
    topic_share_shift_threshold: float = 0.25

    def __post_init__(self) -> None:
        if self.lookback_days < self.minimum_history_days or self.lookback_days <= 0:
            raise ValueError("Lookback must include at least the minimum history days.")
        if (
            self.minimum_history_days <= 0
            or self.minimum_current_messages <= 0
            or self.minimum_topic_messages <= 0
        ):
            raise ValueError("Minimum history and message counts must be positive.")
        if self.volume_ratio_threshold <= 1:
            raise ValueError("Volume ratio threshold must be greater than one.")
        if not 0 < self.sentiment_shift_threshold <= 2:
            raise ValueError("Sentiment shift threshold must be between zero and two.")
        if not 0 < self.topic_share_shift_threshold <= 1:
            raise ValueError("Topic share shift threshold must be between zero and one.")

    @property
    def detector_version(self) -> str:
        """Derive a stable version from every behavior-changing threshold."""

        return (
            "1:rolling-median:"
            f"lookback={self.lookback_days}:"
            f"min-history={self.minimum_history_days}:"
            f"min-messages={self.minimum_current_messages}:"
            f"volume={self.volume_ratio_threshold:g}:"
            f"sentiment={self.sentiment_shift_threshold:g}"
            f":min-topic={self.minimum_topic_messages}"
            f":topic-share={self.topic_share_shift_threshold:g}"
        )


@dataclass(frozen=True)
class AnomalyResult:
    stat_date: str
    analysis_version: str
    detector_version: str
    topic_version: str | None
    status: str
    severity: str
    signals: tuple[str, ...]
    explanation: str
    history_days: int
    baseline_start_date: str | None
    baseline_end_date: str | None
    current_messages: int
    baseline_messages: float | None
    volume_ratio: float | None
    current_sentiment: float
    baseline_sentiment: float | None
    sentiment_shift: float | None
    shifted_topic: str | None
    current_topic_share: float | None
    baseline_topic_share: float | None
    topic_share_shift: float | None
    fingerprint: str


def evaluate_anomaly(
    metrics: Sequence[dict[str, Any]],
    *,
    topic_metrics: Sequence[dict[str, Any]] = (),
    topic_version: str | None = None,
    config: AnomalyConfig = AnomalyConfig(),
) -> AnomalyResult:
    """Evaluate the latest date against earlier dates in its rolling window."""

    if not metrics:
        raise ValueError("At least one daily metric is required.")
    ordered = sorted(metrics, key=lambda row: str(row["stat_date"]))
    target = ordered[-1]
    target_date = date.fromisoformat(str(target["stat_date"]))
    analysis_version = str(target["analysis_version"])
    if any(str(row["analysis_version"]) != analysis_version for row in ordered):
        raise ValueError("Anomaly metrics must share one analysis version.")

    window_start = target_date - timedelta(days=config.lookback_days)
    history = [
        row
        for row in ordered[:-1]
        if window_start <= date.fromisoformat(str(row["stat_date"])) < target_date
    ]
    current_messages = int(target["analyzed_count"])
    current_sentiment = float(target["sentiment_score"])
    fingerprint = _fingerprint(
        target_date, analysis_version, config.detector_version, topic_version
    )

    if len(history) < config.minimum_history_days:
        return AnomalyResult(
            stat_date=target_date.isoformat(),
            analysis_version=analysis_version,
            detector_version=config.detector_version,
            topic_version=topic_version,
            status="insufficient_history",
            severity="none",
            signals=(),
            explanation=(
                f"Need {config.minimum_history_days} prior days; "
                f"only {len(history)} are available."
            ),
            history_days=len(history),
            baseline_start_date=(str(history[0]["stat_date"]) if history else None),
            baseline_end_date=(str(history[-1]["stat_date"]) if history else None),
            current_messages=current_messages,
            baseline_messages=None,
            volume_ratio=None,
            current_sentiment=current_sentiment,
            baseline_sentiment=None,
            sentiment_shift=None,
            shifted_topic=None,
            current_topic_share=None,
            baseline_topic_share=None,
            topic_share_shift=None,
            fingerprint=fingerprint,
        )

    baseline_messages = float(median(int(row["analyzed_count"]) for row in history))
    baseline_sentiment = float(median(float(row["sentiment_score"]) for row in history))
    volume_ratio = (
        current_messages / baseline_messages if baseline_messages > 0 else None
    )
    sentiment_shift = current_sentiment - baseline_sentiment
    signals: list[str] = []
    if (
        current_messages >= config.minimum_current_messages
        and volume_ratio is not None
        and volume_ratio >= config.volume_ratio_threshold
    ):
        signals.append("volume_spike")
    if (
        current_messages >= config.minimum_current_messages
        and abs(sentiment_shift) >= config.sentiment_shift_threshold
    ):
        signals.append(
            "bullish_shift" if sentiment_shift > 0 else "bearish_shift"
        )
    topic_shift = _find_topic_shift(
        topic_metrics,
        target_date=target_date,
        history_dates=[date.fromisoformat(str(row["stat_date"])) for row in history],
        config=config,
    )
    if topic_shift is not None:
        signals.append("topic_shift")

    status = "anomaly" if signals else "normal"
    severity = "high" if len(signals) > 1 else ("medium" if signals else "none")
    explanation = _explain(
        signals,
        current_messages=current_messages,
        baseline_messages=baseline_messages,
        volume_ratio=volume_ratio,
        current_sentiment=current_sentiment,
        baseline_sentiment=baseline_sentiment,
        sentiment_shift=sentiment_shift,
        topic_shift=topic_shift,
    )
    return AnomalyResult(
        stat_date=target_date.isoformat(),
        analysis_version=analysis_version,
        detector_version=config.detector_version,
        topic_version=topic_version,
        status=status,
        severity=severity,
        signals=tuple(signals),
        explanation=explanation,
        history_days=len(history),
        baseline_start_date=str(history[0]["stat_date"]),
        baseline_end_date=str(history[-1]["stat_date"]),
        current_messages=current_messages,
        baseline_messages=round(baseline_messages, 4),
        volume_ratio=round(volume_ratio, 4) if volume_ratio is not None else None,
        current_sentiment=round(current_sentiment, 4),
        baseline_sentiment=round(baseline_sentiment, 4),
        sentiment_shift=round(sentiment_shift, 4),
        shifted_topic=topic_shift[0] if topic_shift else None,
        current_topic_share=round(topic_shift[1], 4) if topic_shift else None,
        baseline_topic_share=round(topic_shift[2], 4) if topic_shift else None,
        topic_share_shift=round(topic_shift[3], 4) if topic_shift else None,
        fingerprint=fingerprint,
    )


def replay_anomalies(
    metrics: Sequence[dict[str, Any]],
    *,
    topic_metrics: Sequence[dict[str, Any]] = (),
    topic_version: str | None = None,
    config: AnomalyConfig = AnomalyConfig(),
) -> list[AnomalyResult]:
    """Re-evaluate every date in order using only data available at that date."""

    ordered = sorted(metrics, key=lambda row: str(row["stat_date"]))
    return [
        evaluate_anomaly(
            ordered[: index + 1],
            topic_metrics=topic_metrics,
            topic_version=topic_version,
            config=config,
        )
        for index in range(len(ordered))
    ]


def _fingerprint(
    stat_date: date,
    analysis_version: str,
    detector_version: str,
    topic_version: str | None,
) -> str:
    value = (
        f"{stat_date.isoformat()}|{analysis_version}|{detector_version}|"
        f"{topic_version or 'no-topics'}"
    )
    return sha256(value.encode("utf-8")).hexdigest()


def _explain(
    signals: Sequence[str],
    *,
    current_messages: int,
    baseline_messages: float,
    volume_ratio: float | None,
    current_sentiment: float,
    baseline_sentiment: float,
    sentiment_shift: float,
    topic_shift: tuple[str, float, float, float] | None,
) -> str:
    if not signals:
        return (
            f"No threshold crossed: {current_messages} messages versus "
            f"{baseline_messages:.1f} baseline; sentiment {current_sentiment:+.2f} "
            f"versus {baseline_sentiment:+.2f}."
        )
    details: list[str] = []
    if "volume_spike" in signals:
        details.append(
            f"volume is {volume_ratio:.2f}x the {baseline_messages:.1f}-message baseline"
        )
    if "bullish_shift" in signals or "bearish_shift" in signals:
        direction = "bullish" if sentiment_shift > 0 else "bearish"
        details.append(
            f"sentiment shifted {direction} by {abs(sentiment_shift):.2f} "
            f"from {baseline_sentiment:+.2f} to {current_sentiment:+.2f}"
        )
    if topic_shift is not None:
        topic, current_share, baseline_share, shift = topic_shift
        details.append(
            f"{topic} share rose by {shift:.0%} "
            f"from {baseline_share:.0%} to {current_share:.0%}"
        )
    return "Anomaly detected: " + "; ".join(details) + "."


def _find_topic_shift(
    topic_metrics: Sequence[dict[str, Any]],
    *,
    target_date: date,
    history_dates: Sequence[date],
    config: AnomalyConfig,
) -> tuple[str, float, float, float] | None:
    """Return the strongest newly prominent topic, if it crosses the threshold."""

    counts: dict[date, dict[str, int]] = {}
    for row in topic_metrics:
        row_date = date.fromisoformat(str(row["stat_date"]))
        if row_date == target_date or row_date in history_dates:
            counts.setdefault(row_date, {})[str(row["topic"])] = int(
                row["message_count"]
            )
    current = counts.get(target_date, {})
    current_total = sum(current.values())
    if current_total <= 0:
        return None

    strongest: tuple[str, float, float, float] | None = None
    for topic, topic_count in current.items():
        if topic == "Other" or topic_count < config.minimum_topic_messages:
            continue
        current_share = topic_count / current_total
        history_shares = []
        for history_date in history_dates:
            daily = counts.get(history_date, {})
            total = sum(daily.values())
            history_shares.append(daily.get(topic, 0) / total if total else 0.0)
        baseline_share = float(median(history_shares))
        shift = current_share - baseline_share
        candidate = (topic, current_share, baseline_share, shift)
        if shift >= config.topic_share_shift_threshold and (
            strongest is None or shift > strongest[3]
        ):
            strongest = candidate
    return strongest
