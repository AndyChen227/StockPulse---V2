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

from stockpulse.config import Settings, load_settings, validate_runtime_settings  # noqa: E402


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
        self.assertEqual(settings.database_backend, "sqlite")
        self.assertIsNone(settings.database_url)
        self.assertEqual(settings.database_pool_min_size, 1)
        self.assertEqual(settings.database_pool_max_size, 4)
        self.assertFalse(settings.has_action_api_token)
        self.assertFalse(settings.has_api_token)
        self.assertEqual(settings.environment, "development")

    def test_environment_rejects_unknown_value(self) -> None:
        with patch.dict(
            os.environ, {"STOCKPULSE_ENVIRONMENT": "staging"}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "development.*production"):
                load_settings(load_env_file=False)

    def test_production_service_requires_postgres_and_bounded_pool(self) -> None:
        settings = Settings(environment="production")
        with self.assertRaisesRegex(ValueError, "PostgreSQL"):
            validate_runtime_settings(settings, "service")

        settings = Settings(
            environment="production",
            database_backend="postgresql",
            database_url="postgresql://user:secret@db/stockpulse",
            database_pool_max_size=5,
        )
        with self.assertRaisesRegex(ValueError, "cannot exceed 4"):
            validate_runtime_settings(settings, "service")

    def test_production_roles_return_only_secret_safe_checks(self) -> None:
        secret = "secret-apify-token"
        common = {
            "environment": "production",
            "database_backend": "postgresql",
            "database_url": "postgresql://user:database-secret@db/stockpulse",
        }
        service_checks = validate_runtime_settings(Settings(**common), "service")
        job_checks = validate_runtime_settings(
            Settings(api_token=secret, **common), "job"
        )

        rendered = " ".join(service_checks + job_checks)
        self.assertIn("action_api=disabled", service_checks)
        self.assertIn("apify_token=configured", job_checks)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("database-secret", rendered)

    def test_production_job_requires_token_and_image_pinned_model(self) -> None:
        common = {
            "environment": "production",
            "database_backend": "postgresql",
            "database_url": "postgresql://user:secret@db/stockpulse",
        }
        with self.assertRaisesRegex(ValueError, "APIFY_API_TOKEN"):
            validate_runtime_settings(Settings(**common), "job")
        with self.assertRaisesRegex(ValueError, "match the model pinned"):
            validate_runtime_settings(
                Settings(api_token="token", sentiment_model_revision="main", **common),
                "job",
            )

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

    def test_postgres_requires_a_secret_url_and_bounded_pool(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_DATABASE_BACKEND": "postgresql"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "DATABASE_URL is required"):
                load_settings(load_env_file=False)

        with patch.dict(
            os.environ,
            {
                "STOCKPULSE_DATABASE_BACKEND": "postgresql",
                "STOCKPULSE_DATABASE_URL": "postgresql://user:secret@db/stockpulse",
                "STOCKPULSE_DATABASE_POOL_MIN_SIZE": "2",
                "STOCKPULSE_DATABASE_POOL_MAX_SIZE": "5",
            },
            clear=True,
        ):
            settings = load_settings(load_env_file=False)

        self.assertEqual(settings.database_backend, "postgresql")
        self.assertEqual(settings.database_pool_min_size, 2)
        self.assertEqual(settings.database_pool_max_size, 5)
        self.assertNotIn("secret", repr(settings))

    def test_database_pool_rejects_unbounded_configuration(self) -> None:
        with patch.dict(
            os.environ,
            {"STOCKPULSE_DATABASE_POOL_MAX_SIZE": "11"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "maximum <= 10"):
                load_settings(load_env_file=False)

    def test_action_secret_is_hidden_and_must_be_long(self) -> None:
        with patch.dict(
            os.environ, {"STOCKPULSE_ACTION_API_TOKEN": "too-short"}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "at least 32"):
                load_settings(load_env_file=False)

        secret = "a" * 32
        with patch.dict(
            os.environ, {"STOCKPULSE_ACTION_API_TOKEN": secret}, clear=True
        ):
            settings = load_settings(load_env_file=False)

        self.assertTrue(settings.has_action_api_token)
        self.assertNotIn(secret, repr(settings))


if __name__ == "__main__":
    unittest.main()
