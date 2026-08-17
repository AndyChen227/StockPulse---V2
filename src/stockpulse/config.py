"""Application configuration loaded from environment variables."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import os

from dotenv import load_dotenv

from stockpulse.sentiment import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
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
    sentiment_model_revision: str = DEFAULT_MODEL_REVISION
    sentiment_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    database_backend: str = "sqlite"
    database_url: str | None = field(default=None, repr=False)
    database_pool_min_size: int = 1
    database_pool_max_size: int = 4
    action_api_token: str | None = field(default=None, repr=False)

    @property
    def has_api_token(self) -> bool:
        """Return whether a usable Apify token is configured."""

        return bool(self.api_token)

    @property
    def has_action_api_token(self) -> bool:
        return bool(self.action_api_token)


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
    sentiment_model_revision = os.getenv(
        "STOCKPULSE_SENTIMENT_MODEL_REVISION", DEFAULT_MODEL_REVISION
    ).strip()
    sentiment_threshold_text = os.getenv(
        "STOCKPULSE_SENTIMENT_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD)
    ).strip()
    database_backend = os.getenv("STOCKPULSE_DATABASE_BACKEND", "sqlite").strip().lower()
    database_url = _clean_secret(os.getenv("STOCKPULSE_DATABASE_URL"))
    pool_min_text = os.getenv("STOCKPULSE_DATABASE_POOL_MIN_SIZE", "1").strip()
    pool_max_text = os.getenv("STOCKPULSE_DATABASE_POOL_MAX_SIZE", "4").strip()
    action_api_token = _clean_secret(os.getenv("STOCKPULSE_ACTION_API_TOKEN"))

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
    if not sentiment_model_revision:
        raise ValueError("STOCKPULSE_SENTIMENT_MODEL_REVISION cannot be empty.")

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

    if database_backend not in {"sqlite", "postgresql"}:
        raise ValueError(
            "STOCKPULSE_DATABASE_BACKEND must be 'sqlite' or 'postgresql'."
        )
    if database_backend == "postgresql":
        if not database_url:
            raise ValueError(
                "STOCKPULSE_DATABASE_URL is required for the PostgreSQL backend."
            )
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError(
                "STOCKPULSE_DATABASE_URL must use a PostgreSQL connection URL."
            )

    try:
        database_pool_min_size = int(pool_min_text)
        database_pool_max_size = int(pool_max_text)
    except ValueError as error:
        raise ValueError("Database pool sizes must be whole numbers.") from error
    if not 1 <= database_pool_min_size <= database_pool_max_size <= 10:
        raise ValueError(
            "Database pool sizes must satisfy 1 <= minimum <= maximum <= 10."
        )
    if action_api_token and len(action_api_token) < 32:
        raise ValueError("STOCKPULSE_ACTION_API_TOKEN must contain at least 32 characters.")

    return Settings(
        api_token=api_token,
        actor_id=actor_id,
        symbol=symbol,
        max_messages=max_messages,
        max_total_charge_usd=max_total_charge_usd,
        sentiment_model=sentiment_model,
        sentiment_model_revision=sentiment_model_revision,
        sentiment_threshold=sentiment_threshold,
        database_backend=database_backend,
        database_url=database_url,
        database_pool_min_size=database_pool_min_size,
        database_pool_max_size=database_pool_max_size,
        action_api_token=action_api_token,
    )


def _clean_secret(value: str | None) -> str | None:
    """Treat empty values and the public example placeholder as missing."""

    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned or cleaned == "replace_with_your_apify_token":
        return None

    return cleaned
