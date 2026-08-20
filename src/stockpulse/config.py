"""Application configuration loaded from environment variables."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from stockpulse.sentiment import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
)


DEFAULT_ACTOR_ID = "automation-lab/stocktwits-scraper"
DEFAULT_MAX_CHARGE_USD = Decimal("0.05")
ENVIRONMENTS = frozenset({"development", "production"})
RUNTIME_ROLES = frozenset({"service", "job"})


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
    environment: str = "development"
    email_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_timeout_seconds: int = 20
    smtp_username: str | None = None
    smtp_app_password: str | None = field(default=None, repr=False)
    email_from: str | None = None
    email_to: str | None = None
    daily_email_after_hour: int = 14
    email_timezone: str = "America/Los_Angeles"
    dashboard_url: str | None = None
    cloud_run_job_url: str | None = None

    @property
    def has_api_token(self) -> bool:
        """Return whether a usable Apify token is configured."""

        return bool(self.api_token)

    @property
    def has_action_api_token(self) -> bool:
        return bool(self.action_api_token)

    @property
    def has_email_config(self) -> bool:
        return bool(
            self.email_enabled
            and self.smtp_username
            and self.smtp_app_password
            and self.email_from
            and self.email_to
        )


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
    environment = os.getenv("STOCKPULSE_ENVIRONMENT", "development").strip().lower()
    email_enabled = _parse_bool(
        os.getenv("STOCKPULSE_EMAIL_ENABLED", "false"),
        "STOCKPULSE_EMAIL_ENABLED",
    )
    smtp_host = os.getenv("STOCKPULSE_SMTP_HOST", "smtp.gmail.com").strip()
    smtp_port_text = os.getenv("STOCKPULSE_SMTP_PORT", "587").strip()
    smtp_timeout_text = os.getenv("STOCKPULSE_SMTP_TIMEOUT_SECONDS", "20").strip()
    smtp_username = _clean_secret(os.getenv("STOCKPULSE_SMTP_USERNAME"))
    smtp_app_password = _clean_secret(os.getenv("STOCKPULSE_SMTP_APP_PASSWORD"))
    if smtp_app_password:
        smtp_app_password = "".join(smtp_app_password.split())
    email_from = _clean_secret(os.getenv("STOCKPULSE_EMAIL_FROM"))
    email_to = _clean_secret(os.getenv("STOCKPULSE_EMAIL_TO"))
    daily_email_hour_text = os.getenv(
        "STOCKPULSE_DAILY_EMAIL_AFTER_HOUR", "14"
    ).strip()
    email_timezone = os.getenv(
        "STOCKPULSE_EMAIL_TIMEZONE", "America/Los_Angeles"
    ).strip()
    dashboard_url = _clean_secret(os.getenv("STOCKPULSE_DASHBOARD_URL"))
    cloud_run_job_url = _clean_secret(os.getenv("STOCKPULSE_CLOUD_RUN_JOB_URL"))

    if environment not in ENVIRONMENTS:
        raise ValueError(
            "STOCKPULSE_ENVIRONMENT must be 'development' or 'production'."
        )

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

    try:
        smtp_port = int(smtp_port_text)
        smtp_timeout_seconds = int(smtp_timeout_text)
        daily_email_after_hour = int(daily_email_hour_text)
    except ValueError as error:
        raise ValueError(
            "SMTP port, timeout, and daily email hour must be whole numbers."
        ) from error
    if not 1 <= smtp_port <= 65535:
        raise ValueError("STOCKPULSE_SMTP_PORT must be between 1 and 65535.")
    if not 1 <= smtp_timeout_seconds <= 120:
        raise ValueError("STOCKPULSE_SMTP_TIMEOUT_SECONDS must be between 1 and 120.")
    if not 0 <= daily_email_after_hour <= 23:
        raise ValueError("STOCKPULSE_DAILY_EMAIL_AFTER_HOUR must be between 0 and 23.")
    try:
        ZoneInfo(email_timezone)
    except ZoneInfoNotFoundError as error:
        raise ValueError("STOCKPULSE_EMAIL_TIMEZONE is not a valid timezone.") from error
    email_values = {
        "STOCKPULSE_SMTP_USERNAME": smtp_username,
        "STOCKPULSE_SMTP_APP_PASSWORD": smtp_app_password,
        "STOCKPULSE_EMAIL_FROM": email_from,
        "STOCKPULSE_EMAIL_TO": email_to,
    }
    if email_enabled:
        missing = [name for name, value in email_values.items() if not value]
        if missing:
            raise ValueError(
                "Email is enabled but required settings are missing: "
                + ", ".join(missing)
            )
        if "@" not in str(email_from) or "@" not in str(email_to):
            raise ValueError("Email sender and recipient must be valid email addresses.")
    if not smtp_host:
        raise ValueError("STOCKPULSE_SMTP_HOST cannot be empty.")

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
        environment=environment,
        email_enabled=email_enabled,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_timeout_seconds=smtp_timeout_seconds,
        smtp_username=smtp_username,
        smtp_app_password=smtp_app_password,
        email_from=email_from,
        email_to=email_to,
        daily_email_after_hour=daily_email_after_hour,
        email_timezone=email_timezone,
        dashboard_url=dashboard_url,
        cloud_run_job_url=cloud_run_job_url,
    )


def validate_runtime_settings(settings: Settings, role: str) -> tuple[str, ...]:
    """Validate one production runtime without exposing secret values."""

    normalized_role = role.strip().lower()
    if normalized_role not in RUNTIME_ROLES:
        raise ValueError("Runtime role must be 'service' or 'job'.")
    if settings.environment != "production":
        raise ValueError(
            "STOCKPULSE_ENVIRONMENT must be 'production' for a production preflight."
        )
    if settings.database_backend != "postgresql" or not settings.database_url:
        raise ValueError("Production requires the PostgreSQL database backend and URL.")
    if settings.database_pool_max_size > 4:
        raise ValueError(
            "Production database pool maximum cannot exceed 4 in the initial deployment."
        )

    checks = [
        "environment=production",
        "database=postgresql",
        f"database_pool={settings.database_pool_min_size}..{settings.database_pool_max_size}",
    ]
    if normalized_role == "job":
        if not settings.has_api_token:
            raise ValueError("APIFY_API_TOKEN is required for the production job.")
        if (
            settings.sentiment_model != DEFAULT_MODEL_NAME
            or settings.sentiment_model_revision != DEFAULT_MODEL_REVISION
        ):
            raise ValueError(
                "Production job model and revision must match the model pinned in its image."
            )
        checks.extend(("apify_token=configured", "sentiment_model=pinned"))
        if settings.email_enabled:
            if not settings.has_email_config:
                raise ValueError(
                    "Production job email delivery is enabled but incomplete."
                )
            checks.append("email=enabled")
        else:
            checks.append("email=disabled")
    else:
        checks.append(
            "action_api=enabled" if settings.has_action_api_token else "action_api=disabled"
        )

    return tuple(checks)


def _clean_secret(value: str | None) -> str | None:
    """Treat empty values and the public example placeholder as missing."""

    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned or cleaned == "replace_with_your_apify_token":
        return None

    return cleaned


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")
