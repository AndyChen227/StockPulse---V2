"""Tests for bounded manual-action authentication and confirmation."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from stockpulse.actions import ActionGate  # noqa: E402


class ActionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = ActionGate("s" * 32)

    def test_tampered_confirmation_is_rejected(self) -> None:
        token = self.gate.issue(
            action="collect", symbol="TSLA", max_messages=5, max_charge="0.05"
        )
        encoded, signature = token.split(".", 1)
        tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaisesRegex(ValueError, "Invalid"):
            self.gate.consume(f"{encoded}.{tampered_signature}")

    def test_confirmation_preserves_server_limits(self) -> None:
        token = self.gate.issue(
            action="collect", symbol="TSLA", max_messages=5, max_charge="0.05"
        )
        payload = self.gate.consume(token)
        self.assertEqual(payload["action"], "collect")
        self.assertEqual(payload["symbol"], "TSLA")
        self.assertEqual(payload["max_messages"], 5)
        self.assertEqual(payload["max_total_charge_usd"], "0.05")


if __name__ == "__main__":
    unittest.main()
