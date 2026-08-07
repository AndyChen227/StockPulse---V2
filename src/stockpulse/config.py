"""Application configuration loaded from environment variables."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import os

from dotenv import load_dotenv

from stockpulse.sentiment import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_NAME,
)


DEFAULT_ACTOR_ID = "automation-lab/stocktwits-scraper"
DEFAULT_MAX_CHARGE_USD = Decimal("0.05")


@dataclass(frozen=True)
class Settings:
    """Validated settings used by the StockPulse application."""

    api_token: str | None = field(default=None, repr=False)
    actor_id: str = DEFAULT_ACTOR_ID
    symbol: str = "TSLA"
    max_messages: int = 5
    max_total_charge_usd: Decimal = DEFAULT_MAX_CHARGE_USD
    sentiment_model: str = DEFAULT_MODEL_NAME
    sentiment_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD

    @property
    def has_api_token(self) -> bool:
        """Return whether a usable Apify token is configured."""

        return bool(self.api_token)


def load_settings(
    *, require_token: bool = False, load_env_file: bool = True
) -> Settings:
    """Load and validate settings without ever printing the API token."""

    if load_env_file:
        load_dotenv(override=False)

    api_token = _clean_secret(os.getenv("APIFY_API_TOKEN"))
    actor_id = os.getenv("APIFY_ACTOR_ID", DEFAULT_ACTOR_ID).strip()
    symbol = os.getenv("STOCKPULSE_SYMBOL", "TSLA").strip().upper()
    max_messages_text = os.getenv("STOCKPULSE_MAX_MESSAGES", "5").strip()
    max_charge_text = os.getenv(
        "APIFY_MAX_TOTAL_CHARGE_USD", str(DEFAULT_MAX_CHARGE_USD)
    ).strip()
    sentiment_model = os.getenv(
        "STOCKPULSE_SENTIMENT_MODEL", DEFAULT_MODEL_NAME
    ).strip()
    sentiment_threshold_text = os.getenv(
        "STOCKPULSE_SENTIMENT_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD)
    ).strip()

    if require_token and not api_token:
        raise ValueError(
            "APIFY_API_TOKEN is missing. Add it to the local .env file before collecting."
        )

    if "/" not in actor_id or actor_id.startswith("/") or actor_id.endswith("/"):
        raise ValueError("APIFY_ACTOR_ID must look like 'author/actor-name'.")

    if not symbol:
        raise ValueError("STOCKPULSE_SYMBOL cannot be empty.")

    try:
        max_messages = int(max_messages_text)
    except ValueError as error:
        raise ValueError("STOCKPULSE_MAX_MESSAGES must be a whole number.") from error

    if max_messages <= 0:
        raise ValueError("STOCKPULSE_MAX_MESSAGES must be greater than zero.")

    if max_messages > 100:
        raise ValueError(
            "STOCKPULSE_MAX_MESSAGES cannot exceed 100 in the cost-aware V1."
        )

    try:
        max_total_charge_usd = Decimal(max_charge_text)
    except InvalidOperation as error:
        raise ValueError(
            "APIFY_MAX_TOTAL_CHARGE_USD must be a valid dollar amount."
        ) from error

    if max_total_charge_usd <= 0 or max_total_charge_usd > Decimal("1.00"):
        raise ValueError(
            "APIFY_MAX_TOTAL_CHARGE_USD must be greater than 0 and at most 1.00."
        )

    if not sentiment_model:
        raise ValueError("STOCKPULSE_SENTIMENT_MODEL cannot be empty.")

    try:
        sentiment_threshold = float(sentiment_threshold_text)
    except ValueError as error:
        raise ValueError(
            "STOCKPULSE_SENTIMENT_THRESHOLD must be a number between 0 and 1."
        ) from error

    if not 0 <= sentiment_threshold <= 1:
        raise ValueError(
            "STOCKPULSE_SENTIMENT_THRESHOLD must be between 0 and 1."
        )

    return Settings(
        api_token=api_token,
        actor_id=actor_id,
        symbol=symbol,
        max_messages=max_messages,
        max_total_charge_usd=max_total_charge_usd,
        sentiment_model=sentiment_model,
        sentiment_threshold=sentiment_threshold,
    )


def _clean_secret(value: str | None) -> str | None:
    """Treat empty values and the public example placeholder as missing."""

    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned or cleaned == "replace_with_your_apify_token":
        return None

    return cleaned
