"""Shared validation for the durable StockPulse message contract."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


REQUIRED_MESSAGE_FIELDS = frozenset(
    {
        "messageId",
        "body",
        "createdAt",
        "sentiment",
        "symbols",
        "username",
        "userFollowers",
        "url",
    }
)
ALLOWED_AUTHOR_SENTIMENTS = frozenset({"Bullish", "Bearish"})


def validate_message(message: dict[str, Any], *, index: int) -> None:
    """Reject values that cannot safely enter the historical data contract."""

    missing_fields = REQUIRED_MESSAGE_FIELDS.difference(message)
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Message {index} is missing required fields: {missing}.")

    message_id = message["messageId"]
    if (
        isinstance(message_id, bool)
        or not isinstance(message_id, int)
        or message_id <= 0
    ):
        raise ValueError(f"Message {index} has an invalid messageId.")

    body = message["body"]
    if not isinstance(body, str) or not body.strip():
        raise ValueError(f"Message {index} has an empty or invalid body.")

    normalize_created_at(message["createdAt"], index=index)

    sentiment = message["sentiment"]
    if sentiment is not None and sentiment not in ALLOWED_AUTHOR_SENTIMENTS:
        raise ValueError(f"Message {index} has an invalid author sentiment.")

    symbols = message["symbols"]
    if not isinstance(symbols, list) or any(
        not isinstance(symbol, str) or not symbol.strip() for symbol in symbols
    ):
        raise ValueError(f"Message {index} has an invalid symbols list.")

    username = message["username"]
    if username is not None and not isinstance(username, str):
        raise ValueError(f"Message {index} has an invalid username.")

    followers = message["userFollowers"]
    if (
        followers is not None
        and (
            isinstance(followers, bool)
            or not isinstance(followers, int)
            or followers < 0
        )
    ):
        raise ValueError(f"Message {index} has an invalid userFollowers value.")

    url = message["url"]
    if url is not None:
        if not isinstance(url, str):
            raise ValueError(f"Message {index} has an invalid url.")
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError(f"Message {index} has an invalid url.")


def normalize_created_at(value: Any, *, index: int) -> str:
    """Validate a source timestamp and return a canonical UTC value."""

    if not isinstance(value, str):
        raise ValueError(f"Message {index} has an invalid createdAt timestamp.")
    try:
        parsed_timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"Message {index} has an invalid createdAt timestamp."
        ) from error
    if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
        raise ValueError(
            f"Message {index} createdAt timestamp must include a timezone."
        )

    return parsed_timestamp.astimezone(timezone.utc).isoformat()


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """Validate a collection before any part of it is persisted."""

    for index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            raise ValueError(f"Message {index} must be an object.")
        validate_message(message, index=index)
