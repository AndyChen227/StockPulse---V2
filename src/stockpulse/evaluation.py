"""Finance-specific sentiment evaluation without external metric dependencies."""

from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Sequence

from stockpulse.sentiment import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    SentimentAnalyzer,
    SentimentResult,
)


LABELS = ("Bullish", "Neutral", "Bearish")


@dataclass(frozen=True)
class EvaluationExample:
    example_id: str
    text: str
    label: str
    category: str


@dataclass(frozen=True)
class LabelMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class EvaluationReport:
    total: int
    correct: int
    accuracy: float
    macro_f1: float
    low_confidence_count: int
    low_confidence_accuracy: float | None
    high_confidence_accuracy: float | None
    average_confidence: float
    per_label: dict[str, LabelMetrics]
    confusion_matrix: dict[str, dict[str, int]]
    errors: tuple[dict[str, Any], ...]


def load_evaluation_set(path: Path) -> list[EvaluationExample]:
    """Load and validate a balanced JSON Lines evaluation set."""

    examples: list[EvaluationExample] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}.") from error
            required = {"id", "text", "label", "category"}
            missing = required.difference(item)
            if missing:
                raise ValueError(
                    f"Evaluation line {line_number} is missing: "
                    f"{', '.join(sorted(missing))}."
                )
            example_id = str(item["id"]).strip()
            text = str(item["text"]).strip()
            label = str(item["label"]).strip()
            category = str(item["category"]).strip()
            if not example_id or example_id in seen_ids:
                raise ValueError(f"Evaluation ID is empty or duplicated: {example_id!r}.")
            if not text or not category:
                raise ValueError(f"Evaluation example {example_id} has empty text.")
            if label not in LABELS:
                raise ValueError(f"Evaluation example {example_id} has invalid label.")
            seen_ids.add(example_id)
            examples.append(EvaluationExample(example_id, text, label, category))

    if not examples:
        raise ValueError("Evaluation set is empty.")
    return examples


def evaluate_predictions(
    examples: Sequence[EvaluationExample],
    predictions: Sequence[SentimentResult],
) -> EvaluationReport:
    """Calculate directional metrics and retain reviewable model errors."""

    if len(examples) != len(predictions):
        raise ValueError("Examples and predictions must have the same length.")
    if not examples:
        raise ValueError("At least one evaluation example is required.")

    confusion = {
        expected: {predicted: 0 for predicted in LABELS} for expected in LABELS
    }
    errors: list[dict[str, Any]] = []
    low_total = low_correct = high_total = high_correct = correct = 0
    total_confidence = 0.0

    for example, prediction in zip(examples, predictions, strict=True):
        if prediction.sentiment not in LABELS:
            raise ValueError(f"Unknown predicted label: {prediction.sentiment}.")
        confusion[example.label][prediction.sentiment] += 1
        is_correct = example.label == prediction.sentiment
        correct += int(is_correct)
        total_confidence += prediction.confidence
        if prediction.low_confidence:
            low_total += 1
            low_correct += int(is_correct)
        else:
            high_total += 1
            high_correct += int(is_correct)
        if not is_correct:
            errors.append(
                {
                    "id": example.example_id,
                    "category": example.category,
                    "expected": example.label,
                    "predicted": prediction.sentiment,
                    "confidence": round(prediction.confidence, 4),
                    "low_confidence": prediction.low_confidence,
                    "text": example.text,
                }
            )

    per_label: dict[str, LabelMetrics] = {}
    for label in LABELS:
        true_positive = confusion[label][label]
        predicted_total = sum(confusion[expected][label] for expected in LABELS)
        support = sum(confusion[label].values())
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_label[label] = LabelMetrics(precision, recall, f1, support)

    return EvaluationReport(
        total=len(examples),
        correct=correct,
        accuracy=correct / len(examples),
        macro_f1=sum(metric.f1 for metric in per_label.values()) / len(LABELS),
        low_confidence_count=low_total,
        low_confidence_accuracy=low_correct / low_total if low_total else None,
        high_confidence_accuracy=high_correct / high_total if high_total else None,
        average_confidence=total_confidence / len(examples),
        per_label=per_label,
        confusion_matrix=confusion,
        errors=tuple(errors),
    )


def report_as_dict(report: EvaluationReport) -> dict[str, Any]:
    """Convert nested metric dataclasses into JSON-compatible values."""

    return asdict(report)


def canonical_dataset_hash(path: Path) -> str:
    """Hash UTF-8 text with LF newlines for cross-platform reproducibility."""

    canonical_text = "\n".join(path.read_text(encoding="utf-8").splitlines()) + "\n"
    return sha256(canonical_text.encode("utf-8")).hexdigest()


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Evaluate StockPulse financial direction.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("evaluations/finance_sentiment_v1.jsonl"),
    )
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--revision", default=DEFAULT_MODEL_REVISION)
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    examples = load_evaluation_set(args.dataset)
    analyzer = SentimentAnalyzer(
        model_name=args.model,
        model_revision=args.revision,
        confidence_threshold=args.confidence_threshold,
    )
    predictions = analyzer.analyze([example.text for example in examples])
    report = evaluate_predictions(examples, predictions)
    first_prediction = predictions[0]
    output = {
        "evaluation_schema_version": 1,
        "dataset": {
            "path": args.dataset.as_posix(),
            "sha256": canonical_dataset_hash(args.dataset),
            "examples": len(examples),
        },
        "analysis": {
            "model_name": first_prediction.model_name,
            "model_revision": first_prediction.model_revision,
            "confidence_threshold": first_prediction.confidence_threshold,
            "analysis_version": first_prediction.analysis_version,
        },
        "metrics": report_as_dict(report),
    }
    payload = json.dumps(output, indent=2, ensure_ascii=False)
    print(payload)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
