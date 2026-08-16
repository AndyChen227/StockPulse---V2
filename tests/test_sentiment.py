"""Tests for the local social-media sentiment adapter."""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.sentiment import (  # noqa: E402
    SentimentAnalyzer,
    SentimentModelError,
    build_analysis_version,
    normalize_prediction,
    normalize_social_text,
)


class SentimentTests(unittest.TestCase):
    def test_social_text_normalizes_users_and_links_but_keeps_cashtags(self) -> None:
        text = "$TSLA looks strong @trader https://example.com/chart"

        self.assertEqual(
            normalize_social_text(text),
            "$TSLA looks strong @user http",
        )

    def test_positive_prediction_maps_to_bullish(self) -> None:
        result = normalize_prediction({"label": "Positive", "score": 0.91})

        self.assertEqual(result.sentiment, "Bullish")
        self.assertEqual(result.confidence, 0.91)

    def test_low_confidence_prediction_keeps_original_direction(self) -> None:
        result = normalize_prediction(
            {"label": "Negative", "score": 0.55},
            confidence_threshold=0.60,
        )

        self.assertEqual(result.sentiment, "Bearish")
        self.assertTrue(result.low_confidence)
        self.assertEqual(result.raw_label, "negative")

    def test_analysis_version_changes_with_model_revision_or_threshold(self) -> None:
        baseline = build_analysis_version("model", "revision-a", 0.60)

        self.assertNotEqual(
            baseline, build_analysis_version("model", "revision-b", 0.60)
        )
        self.assertNotEqual(
            baseline, build_analysis_version("model", "revision-a", 0.70)
        )

    def test_unknown_model_label_is_rejected(self) -> None:
        with self.assertRaisesRegex(SentimentModelError, "unknown label"):
            normalize_prediction({"label": "surprised", "score": 0.90})

    def test_analyzer_uses_injected_classifier_without_loading_model(self) -> None:
        received: list[str] = []

        def fake_classifier(texts: list[str], **_: object) -> list[dict[str, object]]:
            received.extend(texts)
            return [
                {"label": "Positive", "score": 0.88},
                {"label": "Negative", "score": 0.93},
            ]

        analyzer = SentimentAnalyzer(classifier=fake_classifier)
        results = analyzer.analyze(["$TSLA up @andy", "$TSLA down"])

        self.assertEqual(received, ["$TSLA up @user", "$TSLA down"])
        self.assertEqual([result.sentiment for result in results], ["Bullish", "Bearish"])


if __name__ == "__main__":
    unittest.main()
