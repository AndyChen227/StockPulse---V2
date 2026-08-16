"""Tests for explainable topic extraction and representative selection."""

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.topics import (  # noqa: E402
    OTHER_TOPIC,
    RepresentativeMessage,
    TOPIC_ANALYSIS_VERSION,
    extract_topics,
    select_representative_messages,
)


class TopicTests(unittest.TestCase):
    def test_extracts_ranked_topics_and_explanations(self) -> None:
        predictions = extract_topics(
            "TSLA delivery demand is strong, while factory production ramps."
        )

        self.assertEqual(predictions[0].topic, "Deliveries & Demand")
        self.assertEqual(predictions[0].matched_terms, ("delivery", "demand"))
        self.assertEqual(predictions[0].score, 1.0)
        self.assertEqual(predictions[1].topic, "Manufacturing & Supply")
        self.assertEqual(predictions[1].rank, 2)
        self.assertEqual(predictions[0].topic_version, TOPIC_ANALYSIS_VERSION)

    def test_topic_limit_and_taxonomy_order_are_deterministic(self) -> None:
        predictions = extract_topics(
            "Revenue, price target, robotaxi, and BYD.",
            max_topics=2,
        )

        self.assertEqual(len(predictions), 2)
        self.assertEqual(
            [prediction.topic for prediction in predictions],
            ["Earnings & Margins", "Price Action"],
        )

    def test_unmatched_text_uses_other_topic(self) -> None:
        prediction = extract_topics("Interesting day for TSLA.")[0]

        self.assertEqual(prediction.topic, OTHER_TOPIC)
        self.assertEqual(prediction.score, 0.0)
        self.assertEqual(prediction.matched_terms, ())

    def test_word_boundaries_avoid_partial_matches(self) -> None:
        prediction = extract_topics("The boardwalk was crowded.")[0]

        self.assertEqual(prediction.topic, OTHER_TOPIC)

    def test_representatives_rank_signal_confidence_followers_and_recency(self) -> None:
        candidates = [
            self._message(1, topic_score=1.0, confidence=0.8, followers=10),
            self._message(2, topic_score=1.0, confidence=0.9, followers=1),
            self._message(3, topic_score=0.5, confidence=0.99, followers=100_000),
        ]

        selected = select_representative_messages(candidates, limit=2)

        self.assertEqual([message.message_id for message in selected], [2, 1])

    def test_representatives_must_share_one_topic(self) -> None:
        candidates = [
            self._message(1),
            self._message(2, topic="Robotaxi"),
        ]

        with self.assertRaisesRegex(ValueError, "share one topic"):
            select_representative_messages(candidates)

    @staticmethod
    def _message(
        message_id: int,
        *,
        topic: str = "Deliveries & Demand",
        topic_score: float = 1.0,
        confidence: float = 0.8,
        followers: int | None = 10,
    ) -> RepresentativeMessage:
        return RepresentativeMessage(
            message_id=message_id,
            body="test",
            topic=topic,
            topic_score=topic_score,
            ai_sentiment="Bullish",
            ai_confidence=confidence,
            user_followers=followers,
            created_at=f"2026-08-0{message_id}T00:00:00+00:00",
            url=f"https://example.com/{message_id}",
        )


if __name__ == "__main__":
    unittest.main()
