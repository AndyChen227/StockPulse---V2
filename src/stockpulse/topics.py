"""Explainable, versioned topic extraction for TSLA investor messages."""

from collections.abc import Sequence
from dataclasses import dataclass
import re


TOPIC_PIPELINE_VERSION = "1"
TOPIC_TAXONOMY_VERSION = "tsla-keywords-2026-08"
TOPIC_ANALYSIS_VERSION = f"{TOPIC_PIPELINE_VERSION}:{TOPIC_TAXONOMY_VERSION}"
OTHER_TOPIC = "Other"


TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Deliveries & Demand": (
        "deliveries",
        "delivery",
        "demand",
        "orders",
        "order backlog",
        "inventory",
        "price cut",
        "discount",
    ),
    "Earnings & Margins": (
        "earnings",
        "revenue",
        "profit",
        "margin",
        "cash flow",
        "eps",
        "guidance",
    ),
    "Price Action": (
        "price target",
        "support",
        "resistance",
        "breakout",
        "breakdown",
        "rally",
        "selloff",
        "short squeeze",
        "moving average",
    ),
    "Autonomy & FSD": (
        "autonomy",
        "autonomous",
        "full self-driving",
        "self-driving",
        "fsd",
        "autopilot",
    ),
    "Robotaxi": (
        "robotaxi",
        "cybercab",
        "ride-hailing",
        "ride hailing",
    ),
    "Energy": (
        "energy storage",
        "megapack",
        "powerwall",
        "solar",
        "energy margin",
    ),
    "Regulation & Safety": (
        "regulation",
        "regulatory",
        "investigation",
        "recall",
        "safety",
        "approval",
        "nhtsa",
    ),
    "Competition": (
        "competition",
        "competitor",
        "market share",
        "byd",
        "rivian",
        "legacy automaker",
    ),
    "Manufacturing & Supply": (
        "factory",
        "gigafactory",
        "production",
        "manufacturing",
        "supply chain",
        "battery supply",
        "ramp",
    ),
    "Leadership & Governance": (
        "elon musk",
        "musk",
        "executive",
        "board",
        "governance",
        "compensation package",
        "shareholder meeting",
    ),
}


@dataclass(frozen=True)
class TopicPrediction:
    """One explainable topic match for a message."""

    topic: str
    score: float
    matched_terms: tuple[str, ...]
    rank: int
    topic_version: str = TOPIC_ANALYSIS_VERSION


@dataclass(frozen=True)
class RepresentativeMessage:
    """Message fields used for deterministic representative ranking."""

    message_id: int
    body: str
    topic: str
    topic_score: float
    ai_sentiment: str
    ai_confidence: float
    user_followers: int | None
    created_at: str
    url: str | None


def extract_topics(text: str, *, max_topics: int = 3) -> tuple[TopicPrediction, ...]:
    """Return up to three keyword topics with matched terms for explanation."""

    if max_topics <= 0:
        raise ValueError("max_topics must be greater than zero.")
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    matches: list[tuple[int, str, tuple[str, ...]]] = []
    for taxonomy_order, (topic, terms) in enumerate(TOPIC_KEYWORDS.items()):
        matched = tuple(term for term in terms if _contains_term(normalized, term))
        if matched:
            matches.append((taxonomy_order, topic, matched))

    if not matches:
        return (TopicPrediction(OTHER_TOPIC, 0.0, (), 1),)

    matches.sort(key=lambda item: (-len(item[2]), item[0]))
    strongest_count = len(matches[0][2])
    return tuple(
        TopicPrediction(
            topic=topic,
            score=round(len(matched) / strongest_count, 4),
            matched_terms=matched,
            rank=rank,
        )
        for rank, (_, topic, matched) in enumerate(matches[:max_topics], start=1)
    )


def select_representative_messages(
    messages: Sequence[RepresentativeMessage], *, limit: int = 3
) -> list[RepresentativeMessage]:
    """Select stable high-signal examples for one topic without inventing text."""

    if limit <= 0:
        raise ValueError("Representative limit must be greater than zero.")
    if not messages:
        return []
    topics = {message.topic for message in messages}
    if len(topics) != 1:
        raise ValueError("Representative candidates must share one topic.")

    def ranking_key(message: RepresentativeMessage) -> tuple[float, float, int, str, int]:
        followers = max(message.user_followers or 0, 0)
        return (
            message.topic_score,
            message.ai_confidence,
            min(followers, 100_000),
            message.created_at,
            message.message_id,
        )

    return sorted(messages, key=ranking_key, reverse=True)[:limit]


def _contains_term(text: str, term: str) -> bool:
    """Match complete words or phrases without substring false positives."""

    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, text) is not None
