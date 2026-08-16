"""Tests for StockPulse environment configuration."""

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from decimal import Decimal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.config import load_settings  # noqa: E402


class SettingsTests(unittest.TestCase):
    def test_defaults_target_tsla(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings(load_env_file=False)

        self.assertEqual(settings.symbol, "TSLA")
        self.assertEqual(settings.actor_id, "automation-lab/stocktwits-scraper")
        self.assertEqual(settings.max_messages, 5)
        self.assertEqual(settings.max_total_charge_usd, Decimal("0.05"))
        self.assertEqual(
            settings.sentiment_model,
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
        )
        self.assertEqual(
            settings.sentiment_model_revision,
            "3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7",
        )
        self.assertEqual(settings.sentiment_threshold, 0.60)
        self.assertFalse(settings.has_api_token)

    def test_symbol_is_normalized(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_SYMBOL": " tsla ", "STOCKPULSE_MAX_MESSAGES": "25"},
            clear=True,
        ):
            settings = load_settings(load_env_file=False)

        self.assertEqual(settings.symbol, "TSLA")
        self.assertEqual(settings.max_messages, 25)

    def test_invalid_message_limit_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_MAX_MESSAGES": "0"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                load_settings(load_env_file=False)

    def test_collection_requires_a_real_token(self) -> None:
        with patch.dict(
            os.environ,
            {"APIFY_API_TOKEN": "replace_with_your_apify_token"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "APIFY_API_TOKEN is missing"):
                load_settings(require_token=True, load_env_file=False)

    def test_token_is_hidden_from_settings_representation(self) -> None:
        with patch.dict(
            os.environ,
            {"APIFY_API_TOKEN": "secret-test-token"},
            clear=True,
        ):
            settings = load_settings(require_token=True, load_env_file=False)

        self.assertNotIn("secret-test-token", repr(settings))

    def test_invalid_sentiment_threshold_is_rejected(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_SENTIMENT_THRESHOLD": "1.5"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "must be between 0 and 1"):
                load_settings(load_env_file=False)


if __name__ == "__main__":
    unittest.main()
