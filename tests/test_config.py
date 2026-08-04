"""Tests for StockPulse environment configuration."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.config import load_settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_defaults_target_tsla(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.symbol, "TSLA")
        self.assertEqual(settings.max_messages, 100)

    def test_symbol_is_normalized(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_SYMBOL": " tsla ", "STOCKPULSE_MAX_MESSAGES": "25"},
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.symbol, "TSLA")
        self.assertEqual(settings.max_messages, 25)

    def test_invalid_message_limit_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_MAX_MESSAGES": "0"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                load_settings()


if __name__ == "__main__":
    unittest.main()
