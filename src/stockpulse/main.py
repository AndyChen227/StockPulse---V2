"""Command-line entry point for StockPulse."""

from stockpulse import __version__
from stockpulse.config import load_settings


def build_startup_message() -> str:
    """Return a safe startup summary without exposing API credentials."""

    settings = load_settings()
    return (
        f"StockPulse v{__version__} is ready. "
        f"Symbol: {settings.symbol}. "
        f"Maximum messages per daily run: {settings.max_messages}."
    )


def main() -> None:
    """Run the current Phase 1 application."""

    print(build_startup_message())
    print("Phase 1 setup is complete. No Apify request was made.")


if __name__ == "__main__":
    main()
