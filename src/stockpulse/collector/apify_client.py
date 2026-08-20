"""Cost-capped Stocktwits collection through the Apify API."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from apify_client import ApifyClient
from apify_client.errors import ApifyClientError
from impit import RequestError

from stockpulse.config import Settings
from stockpulse.validation import validate_messages as validate_message_contract


class CollectionError(RuntimeError):
    """Raised when an Apify run or its output cannot be used safely."""


@dataclass(frozen=True)
class CollectionBatch:
    """Validated messages plus the external records that produced them."""

    messages: list[dict[str, Any]]
    external_run_id: str
    external_dataset_id: str


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
) -> CollectionBatch:
    """Run the Actor with item, charge, and time limits and return messages."""

    if not settings.api_token:
        raise CollectionError("An Apify API token is required for collection.")

    apify_client = client or ApifyClient(settings.api_token)
    try:
        run = apify_client.actor(settings.actor_id).call(
            run_input=build_run_input(settings),
            max_items=settings.max_messages,
            max_total_charge_usd=settings.max_total_charge_usd,
            run_timeout=timedelta(seconds=60),
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
    external_run_id = getattr(run, "id", None)
    if not external_run_id:
        raise CollectionError("The Apify run did not return a run ID.")

    return CollectionBatch(
        messages=_read_dataset(apify_client, dataset_id, settings.max_messages),
        external_run_id=str(external_run_id),
        external_dataset_id=str(dataset_id),
    )


def retrieve_run_messages(
    settings: Settings,
    run_id: str,
    *,
    client: ApifyClient | None = None,
) -> CollectionBatch:
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

    return CollectionBatch(
        messages=_read_dataset(apify_client, dataset_id, settings.max_messages),
        external_run_id=cleaned_run_id,
        external_dataset_id=str(dataset_id),
    )


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

    try:
        validate_message_contract(messages)
    except ValueError as error:
        raise CollectionError(str(error)) from error
