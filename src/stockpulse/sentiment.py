"""Local sentiment analysis for short Stocktwits messages."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import re
from typing import Any


DEFAULT_MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"
DEFAULT_MODEL_REVISION = "3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7"
DEFAULT_CONFIDENCE_THRESHOLD = 0.60
ANALYSIS_PIPELINE_VERSION = "2"


class SentimentModelError(RuntimeError):
    """Raised when the local sentiment model cannot be loaded or used."""


@dataclass(frozen=True)
class SentimentResult:
    """One normalized StockPulse sentiment prediction."""

    sentiment: str
    confidence: float
    model_name: str
    model_revision: str
    raw_label: str
    low_confidence: bool
    confidence_threshold: float
    analysis_version: str


def build_analysis_version(
    model_name: str, model_revision: str, confidence_threshold: float
) -> str:
    """Return a stable identifier for one complete analysis configuration."""

    return (
        f"{ANALYSIS_PIPELINE_VERSION}:"
        f"{model_name}@{model_revision}:threshold={confidence_threshold:.6g}"
    )


def normalize_social_text(text: str) -> str:
    """Normalize usernames and links in the format used by the model's training data."""

    normalized_words: list[str] = []
    for word in text.split():
        if word.startswith("@") and len(word) > 1:
            normalized_words.append("@user")
        elif re.match(r"https?://|www\.", word, flags=re.IGNORECASE):
            normalized_words.append("http")
        else:
            normalized_words.append(word)
    return " ".join(normalized_words)


def normalize_prediction(
    prediction: dict[str, Any],
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    model_revision: str = DEFAULT_MODEL_REVISION,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> SentimentResult:
    """Map a Hugging Face label to StockPulse's Bullish/Neutral/Bearish labels."""

    label = str(prediction.get("label", "")).strip().lower()
    try:
        score = float(prediction["score"])
    except (KeyError, TypeError, ValueError) as error:
        raise SentimentModelError("The model returned an invalid confidence score.") from error

    label_map = {
        "negative": "Bearish",
        "label_0": "Bearish",
        "neutral": "Neutral",
        "label_1": "Neutral",
        "positive": "Bullish",
        "label_2": "Bullish",
    }
    if label not in label_map:
        raise SentimentModelError(f"The model returned an unknown label: {label!r}.")
    if not 0 <= score <= 1:
        raise SentimentModelError("The model confidence score must be between 0 and 1.")

    sentiment = label_map[label]

    return SentimentResult(
        sentiment=sentiment,
        confidence=score,
        model_name=model_name,
        model_revision=model_revision,
        raw_label=label,
        low_confidence=score < confidence_threshold,
        confidence_threshold=confidence_threshold,
        analysis_version=build_analysis_version(
            model_name, model_revision, confidence_threshold
        ),
    )


class SentimentAnalyzer:
    """Lazy-loading wrapper around a Hugging Face text-classification pipeline."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
        model_revision: str = DEFAULT_MODEL_REVISION,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        classifier: Callable[..., Any] | None = None,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1.")
        self.model_name = model_name
        self.model_revision = model_revision
        self.confidence_threshold = confidence_threshold
        self._classifier = classifier

    def analyze(self, texts: Sequence[str]) -> list[SentimentResult]:
        """Analyze a batch of messages while loading the model only when needed."""

        if not texts:
            return []

        classifier = self._get_classifier()
        normalized_texts = [normalize_social_text(text) for text in texts]
        try:
            predictions = classifier(normalized_texts, truncation=True)
        except Exception as error:  # The library exposes several backend errors.
            raise SentimentModelError(f"Sentiment analysis failed: {error}") from error

        if len(predictions) != len(normalized_texts):
            raise SentimentModelError("The model returned an unexpected number of results.")

        return [
            normalize_prediction(
                prediction,
                model_name=self.model_name,
                model_revision=self.model_revision,
                confidence_threshold=self.confidence_threshold,
            )
            for prediction in predictions
        ]

    def _get_classifier(self) -> Callable[..., Any]:
        if self._classifier is not None:
            return self._classifier

        try:
            from transformers import pipeline
        except ImportError as error:
            raise SentimentModelError(
                "AI dependencies are missing. Install "
                "config/requirements/ai.txt first."
            ) from error

        try:
            self._classifier = pipeline(
                "text-classification",
                model=self.model_name,
                tokenizer=self.model_name,
                revision=self.model_revision,
            )
        except Exception as error:
            raise SentimentModelError(
                "The sentiment model could not be loaded. The first run requires "
                "an internet connection to download the model."
            ) from error
        return self._classifier
