"""Cost-capped Stocktwits collection through the Apify API."""

from datetime import timedelta
from typing import Any

from apify_client import ApifyClient
from apify_client.errors import ApifyClientError
from impit import RequestError

from stockpulse.config import Settings


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


class CollectionError(RuntimeError):
    """Raised when an Apify run or its output cannot be used safely."""


def build_run_input(settings: Settings) -> dict[str, Any]:
    """Build the documented input for the selected Stocktwits Actor."""

    return {
        "mode": "symbol",
        "symbols": [settings.symbol],
        "maxMessages": settings.max_messages,
        "onlyPriceTargets": False,
    }


def collect_messages(
    settings: Settings, *, client: ApifyClient | None = None
) -> list[dict[str, Any]]:
    """Run the Actor with item, charge, and time limits and return messages."""

    if not settings.api_token:
        raise CollectionError("An Apify API token is required for collection.")

    apify_client = client or ApifyClient(settings.api_token)
    try:
        run = apify_client.actor(settings.actor_id).call(
            run_input=build_run_input(settings),
            max_items=settings.max_messages,
            max_total_charge_usd=settings.max_total_charge_usd,
            run_timeout=timedelta(minutes=5),
        )
    except (ApifyClientError, RequestError, TimeoutError) as error:
        raise CollectionError(
            "The Apify request failed. Check the network, token, and Actor settings."
        ) from error

    if run is None:
        raise CollectionError("The Apify Actor run did not complete successfully.")

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id:
        raise CollectionError("The Apify run did not return a default dataset ID.")

    return _read_dataset(apify_client, dataset_id, settings.max_messages)


def retrieve_run_messages(
    settings: Settings,
    run_id: str,
    *,
    client: ApifyClient | None = None,
) -> list[dict[str, Any]]:
    """Read an existing successful run without starting or charging a new run."""

    if not settings.api_token:
        raise CollectionError("An Apify API token is required to retrieve a run.")

    cleaned_run_id = run_id.strip()
    if not cleaned_run_id:
        raise CollectionError("An Apify run ID is required.")

    apify_client = client or ApifyClient(settings.api_token)
    try:
        run = apify_client.run(cleaned_run_id).get()
    except (ApifyClientError, RequestError, TimeoutError) as error:
        raise CollectionError(
            "The existing Apify run could not be retrieved."
        ) from error
    if run is None:
        raise CollectionError(f"Apify run '{cleaned_run_id}' was not found.")

    dataset_id = getattr(run, "default_dataset_id", None)
    if not dataset_id:
        raise CollectionError("The existing Apify run has no default dataset ID.")

    return _read_dataset(apify_client, dataset_id, settings.max_messages)


def _read_dataset(
    apify_client: ApifyClient, dataset_id: str, limit: int
) -> list[dict[str, Any]]:
    """Read and validate a limited number of items from one dataset."""

    try:
        page = apify_client.dataset(dataset_id).list_items(limit=limit)
    except (ApifyClientError, RequestError, TimeoutError) as error:
        raise CollectionError("The Apify dataset could not be retrieved.") from error
    messages = [dict(item) for item in page.items]
    validate_messages(messages)
    return messages


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """Verify that each message contains the fields required by StockPulse V1."""

    for index, message in enumerate(messages, start=1):
        missing_fields = REQUIRED_MESSAGE_FIELDS.difference(message)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise CollectionError(
                f"Message {index} is missing required fields: {missing}."
            )
