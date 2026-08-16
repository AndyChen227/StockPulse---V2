"""Tests for cost-capped Apify collection without making network requests."""

from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.collector.apify_client import (  # noqa: E402
    CollectionBatch,
    CollectionError,
    collect_messages,
    retrieve_run_messages,
    validate_messages,
)
from stockpulse.config import Settings  # noqa: E402


VALID_MESSAGE = {
    "messageId": 123,
    "body": "$TSLA test message",
    "createdAt": "2026-08-05T00:00:00Z",
    "sentiment": None,
    "symbols": ["TSLA"],
    "username": "tester",
    "userFollowers": 10,
    "url": "https://stocktwits.com/tester/message/123",
}


class FakeActor:
    def __init__(self) -> None:
        self.call_kwargs: dict[str, object] | None = None

    def call(self, **kwargs: object) -> SimpleNamespace:
        self.call_kwargs = kwargs
        return SimpleNamespace(id="new-run", default_dataset_id="test-dataset")


class FakeDataset:
    def list_items(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(items=[VALID_MESSAGE])


class FakeRun:
    def get(self) -> SimpleNamespace:
        return SimpleNamespace(default_dataset_id="existing-dataset")


class FakeClient:
    def __init__(self) -> None:
        self.actor_id: str | None = None
        self.dataset_id: str | None = None
        self.run_id: str | None = None
        self.actor_client = FakeActor()

    def actor(self, actor_id: str) -> FakeActor:
        self.actor_id = actor_id
        return self.actor_client

    def dataset(self, dataset_id: str) -> FakeDataset:
        self.dataset_id = dataset_id
        return FakeDataset()

    def run(self, run_id: str) -> FakeRun:
        self.run_id = run_id
        return FakeRun()


class CollectorTests(unittest.TestCase):
    def test_collection_uses_cost_and_item_limits(self) -> None:
        settings = Settings(api_token="test-token")
        client = FakeClient()

        batch = collect_messages(settings, client=client)  # type: ignore[arg-type]

        self.assertEqual(
            batch,
            CollectionBatch([VALID_MESSAGE], "new-run", "test-dataset"),
        )
        self.assertEqual(client.actor_id, "automation-lab/stocktwits-scraper")
        self.assertEqual(client.dataset_id, "test-dataset")
        self.assertIsNotNone(client.actor_client.call_kwargs)
        call_kwargs = client.actor_client.call_kwargs or {}
        self.assertEqual(call_kwargs["max_items"], 5)
        self.assertEqual(call_kwargs["max_total_charge_usd"], Decimal("0.05"))
        self.assertEqual(
            call_kwargs["run_input"],
            {
                "mode": "symbol",
                "symbols": ["TSLA"],
                "maxMessages": 5,
                "onlyPriceTargets": False,
            },
        )

    def test_missing_output_field_is_rejected(self) -> None:
        incomplete_message = dict(VALID_MESSAGE)
        incomplete_message.pop("messageId")

        with self.assertRaisesRegex(CollectionError, "messageId"):
            validate_messages([incomplete_message])

    def test_invalid_timestamp_is_rejected(self) -> None:
        invalid_message = dict(VALID_MESSAGE, createdAt="not-a-timestamp")

        with self.assertRaisesRegex(CollectionError, "createdAt"):
            validate_messages([invalid_message])

    def test_timestamp_without_timezone_is_rejected(self) -> None:
        invalid_message = dict(VALID_MESSAGE, createdAt="2026-08-05T00:00:00")

        with self.assertRaisesRegex(CollectionError, "timezone"):
            validate_messages([invalid_message])

    def test_invalid_types_are_rejected(self) -> None:
        invalid_messages = (
            dict(VALID_MESSAGE, messageId=True),
            dict(VALID_MESSAGE, body="  "),
            dict(VALID_MESSAGE, symbols="TSLA"),
            dict(VALID_MESSAGE, userFollowers=-1),
            dict(VALID_MESSAGE, url="not-a-url"),
        )

        for invalid_message in invalid_messages:
            with self.subTest(invalid_message=invalid_message):
                with self.assertRaises(CollectionError):
                    validate_messages([invalid_message])

    def test_existing_run_is_retrieved_without_starting_actor(self) -> None:
        settings = Settings(api_token="test-token")
        client = FakeClient()

        batch = retrieve_run_messages(
            settings,
            "existing-run",
            client=client,  # type: ignore[arg-type]
        )

        self.assertEqual(
            batch,
            CollectionBatch([VALID_MESSAGE], "existing-run", "existing-dataset"),
        )
        self.assertEqual(client.run_id, "existing-run")
        self.assertEqual(client.dataset_id, "existing-dataset")
        self.assertIsNone(client.actor_client.call_kwargs)


if __name__ == "__main__":
    unittest.main()
