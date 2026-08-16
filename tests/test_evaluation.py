"""Tests for the finance-specific sentiment evaluation harness."""

from pathlib import Path
from hashlib import sha256
import json
import sys
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.evaluation import (  # noqa: E402
    EvaluationExample,
    evaluate_predictions,
    load_evaluation_set,
)
from stockpulse.sentiment import DEFAULT_MODEL_REVISION, SentimentResult  # noqa: E402


def prediction(
    sentiment: str, confidence: float, *, low_confidence: bool = False
) -> SentimentResult:
    return SentimentResult(
        sentiment=sentiment,
        confidence=confidence,
        model_name="test-model",
        model_revision="test-revision",
        raw_label=sentiment.lower(),
        low_confidence=low_confidence,
        confidence_threshold=0.60,
        analysis_version="test-version",
    )


class EvaluationTests(unittest.TestCase):
    def test_version_one_dataset_is_balanced_and_unique(self) -> None:
        dataset_path = PROJECT_ROOT / "evaluations" / "finance_sentiment_v1.jsonl"
        examples = load_evaluation_set(dataset_path)
        counts = {
            label: sum(example.label == label for example in examples)
            for label in ("Bullish", "Neutral", "Bearish")
        }

        self.assertEqual(len(examples), 36)
        self.assertEqual(counts, {"Bullish": 12, "Neutral": 12, "Bearish": 12})
        self.assertEqual(len({example.example_id for example in examples}), 36)

        baseline = json.loads(
            (
                PROJECT_ROOT
                / "evaluations"
                / "results"
                / "twitter-roberta-v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            baseline["dataset"]["sha256"],
            sha256(dataset_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(baseline["dataset"]["examples"], len(examples))
        self.assertEqual(
            baseline["analysis"]["model_revision"], DEFAULT_MODEL_REVISION
        )

    def test_metrics_include_confusion_and_confidence_segments(self) -> None:
        examples = [
            EvaluationExample("1", "up", "Bullish", "test"),
            EvaluationExample("2", "flat", "Neutral", "test"),
            EvaluationExample("3", "down", "Bearish", "test"),
        ]
        predictions = [
            prediction("Bullish", 0.90),
            prediction("Bearish", 0.55, low_confidence=True),
            prediction("Bearish", 0.80),
        ]

        report = evaluate_predictions(examples, predictions)

        self.assertEqual(report.correct, 2)
        self.assertAlmostEqual(report.accuracy, 2 / 3)
        self.assertEqual(report.confusion_matrix["Neutral"]["Bearish"], 1)
        self.assertEqual(report.low_confidence_count, 1)
        self.assertEqual(report.low_confidence_accuracy, 0.0)
        self.assertEqual(report.high_confidence_accuracy, 1.0)
        self.assertEqual(report.errors[0]["id"], "2")
        self.assertAlmostEqual(report.per_label["Bearish"].precision, 0.5)

    def test_loader_rejects_duplicate_ids(self) -> None:
        with TemporaryDirectory() as directory:
            dataset = Path(directory) / "duplicate.jsonl"
            dataset.write_text(
                '{"id":"same","text":"a","label":"Neutral","category":"x"}\n'
                '{"id":"same","text":"b","label":"Neutral","category":"x"}\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicated"):
                load_evaluation_set(dataset)

    def test_prediction_count_must_match_examples(self) -> None:
        examples = [EvaluationExample("1", "up", "Bullish", "test")]

        with self.assertRaisesRegex(ValueError, "same length"):
            evaluate_predictions(examples, [])


if __name__ == "__main__":
    unittest.main()
