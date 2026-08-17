"""Build-time download of the pinned sentiment model."""

from stockpulse.sentiment import DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION


def main() -> None:
    """Cache both tokenizer and model at the exact evaluated revision."""

    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    AutoTokenizer.from_pretrained(
        DEFAULT_MODEL_NAME, revision=DEFAULT_MODEL_REVISION
    )
    AutoModelForSequenceClassification.from_pretrained(
        DEFAULT_MODEL_NAME, revision=DEFAULT_MODEL_REVISION
    )


if __name__ == "__main__":
    main()
