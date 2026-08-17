"""Authentication and explicit confirmation for bounded manual actions."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Any, Callable


ActionDispatcher = Callable[[dict[str, Any]], str]


@dataclass
class ActionGate:
    """Issue and consume short-lived, signed, single-use confirmations."""

    secret: str
    lifetime_seconds: int = 300

    def __post_init__(self) -> None:
        if len(self.secret) < 32:
            raise ValueError("Action secret must contain at least 32 characters.")
        self._consumed: set[str] = set()

    def authenticate(self, authorization: str | None) -> None:
        expected = f"Bearer {self.secret}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise PermissionError("Valid action authentication is required.")

    def issue(self, *, action: str, symbol: str, max_messages: int, max_charge: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "action": action,
            "symbol": symbol,
            "max_messages": max_messages,
            "max_total_charge_usd": max_charge,
            "nonce": secrets.token_urlsafe(18),
            "expires_at": (now + timedelta(seconds=self.lifetime_seconds)).isoformat(),
        }
        encoded = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        signature = hmac.new(self.secret.encode(), encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{_encode(signature)}"

    def consume(self, token: str) -> dict[str, Any]:
        try:
            encoded, supplied_signature = token.split(".", 1)
            expected = hmac.new(
                self.secret.encode(), encoded.encode(), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(_decode(supplied_signature), expected):
                raise ValueError
            payload = json.loads(_decode(encoded))
            expires_at = datetime.fromisoformat(payload["expires_at"])
            nonce = str(payload["nonce"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
            raise ValueError("Invalid action confirmation.") from None
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("Action confirmation has expired.")
        if nonce in self._consumed:
            raise ValueError("Action confirmation was already used.")
        self._consumed.add(nonce)
        return payload


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
