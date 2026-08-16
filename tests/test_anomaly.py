"""Tests for versioned rolling-baseline anomaly detection."""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.anomaly import (  # noqa: E402
    DETECTOR_VERSION,
    AnomalyConfig,
    evaluate_anomaly,
    replay_anomalies,
)


class AnomalyTests(unittest.TestCase):
    def test_requires_minimum_history_without_alerting(self) -> None:
        result = evaluate_anomaly([self._metric(1, 10, 0.1)])

        self.assertEqual(result.status, "insufficient_history")
        self.assertEqual(result.signals, ())

    def test_detects_explainable_volume_and_bearish_shift(self) -> None:
        metrics = [self._metric(day, 10, 0.2) for day in range(1, 8)]
        metrics.append(self._metric(8, 25, -0.4))

        result = evaluate_anomaly(metrics)

        self.assertEqual(result.status, "anomaly")
        self.assertEqual(result.severity, "high")
        self.assertEqual(result.signals, ("volume_spike", "bearish_shift"))
        self.assertEqual(result.baseline_messages, 10.0)
        self.assertEqual(result.volume_ratio, 2.5)
        self.assertEqual(result.sentiment_shift, -0.6)
        self.assertIn("2.50x", result.explanation)

    def test_low_volume_day_does_not_trigger_sentiment_noise(self) -> None:
        metrics = [self._metric(day, 10, 0.0) for day in range(1, 8)]
        metrics.append(self._metric(8, 2, -1.0))

        result = evaluate_anomaly(metrics)

        self.assertEqual(result.status, "normal")
        self.assertEqual(result.signals, ())

    def test_detects_newly_prominent_topic_share(self) -> None:
        metrics = [self._metric(day, 10, 0.0) for day in range(1, 9)]
        topic_metrics = []
        for day in range(1, 8):
            topic_metrics.extend(
                [
                    self._topic_metric(day, "Robotaxi", 1),
                    self._topic_metric(day, "Deliveries & Demand", 9),
                ]
            )
        topic_metrics.extend(
            [
                self._topic_metric(8, "Robotaxi", 6),
                self._topic_metric(8, "Deliveries & Demand", 4),
            ]
        )

        result = evaluate_anomaly(metrics, topic_metrics=topic_metrics)

        self.assertEqual(result.status, "anomaly")
        self.assertEqual(result.severity, "medium")
        self.assertEqual(result.signals, ("topic_shift",))
        self.assertEqual(result.shifted_topic, "Robotaxi")
        self.assertEqual(result.current_topic_share, 0.6)
        self.assertEqual(result.baseline_topic_share, 0.1)
        self.assertEqual(result.topic_share_shift, 0.5)
        self.assertIn("Robotaxi share rose", result.explanation)

    def test_replay_uses_only_prior_data_and_has_stable_fingerprints(self) -> None:
        metrics = [self._metric(day, 10, 0.0) for day in range(1, 8)]
        metrics.append(self._metric(8, 20, 0.5))

        first = replay_anomalies(metrics)
        second = replay_anomalies(metrics)

        self.assertTrue(all(item.status == "insufficient_history" for item in first[:7]))
        self.assertEqual(first[7].status, "anomaly")
        self.assertEqual(
            [item.fingerprint for item in first],
            [item.fingerprint for item in second],
        )

    def test_topic_version_changes_evaluation_fingerprint(self) -> None:
        metrics = [self._metric(day, 10, 0.0) for day in range(1, 9)]

        first = evaluate_anomaly(metrics, topic_version="topics-v1")
        second = evaluate_anomaly(metrics, topic_version="topics-v2")

        self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_rejects_mixed_analysis_versions(self) -> None:
        metrics = [self._metric(1, 10, 0.0), self._metric(2, 10, 0.0)]
        metrics[1]["analysis_version"] = "different"

        with self.assertRaisesRegex(ValueError, "share one analysis version"):
            evaluate_anomaly(metrics)

    def test_rejects_invalid_configuration(self) -> None:
        with self.assertRaisesRegex(ValueError, "Lookback"):
            AnomalyConfig(lookback_days=2, minimum_history_days=7)

    def test_detector_version_changes_with_thresholds(self) -> None:
        default = AnomalyConfig()
        stricter = AnomalyConfig(volume_ratio_threshold=3.0)

        self.assertEqual(default.detector_version, DETECTOR_VERSION)
        self.assertNotEqual(default.detector_version, stricter.detector_version)

    @staticmethod
    def _metric(day: int, messages: int, sentiment: float) -> dict[str, object]:
        return {
            "stat_date": f"2026-08-{day:02d}",
            "analysis_version": "analysis-v1",
            "analyzed_count": messages,
            "sentiment_score": sentiment,
        }

    @staticmethod
    def _topic_metric(day: int, topic: str, messages: int) -> dict[str, object]:
        return {
            "stat_date": f"2026-08-{day:02d}",
            "topic": topic,
            "message_count": messages,
        }


if __name__ == "__main__":
    unittest.main()
