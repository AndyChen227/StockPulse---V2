"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Non-secret settings used by the StockPulse application."""

    symbol: str = "TSLA"
    max_messages: int = 100


def load_settings() -> Settings:
    """Load settings while providing safe defaults for local development."""

    symbol = os.getenv("STOCKPULSE_SYMBOL", "TSLA").strip().upper()
    max_messages_text = os.getenv("STOCKPULSE_MAX_MESSAGES", "100").strip()

    if not symbol:
        raise ValueError("STOCKPULSE_SYMBOL cannot be empty.")

    try:
        max_messages = int(max_messages_text)
    except ValueError as error:
        raise ValueError("STOCKPULSE_MAX_MESSAGES must be a whole number.") from error

    if max_messages <= 0:
        raise ValueError("STOCKPULSE_MAX_MESSAGES must be greater than zero.")

    return Settings(symbol=symbol, max_messages=max_messages)
