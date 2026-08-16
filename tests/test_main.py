"""Smoke test for the StockPulse command-line entry point."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from stockpulse.main import build_startup_message, main  # noqa: E402
from stockpulse.sentiment import (  # noqa: E402
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    SentimentResult,
    build_analysis_version,
)
from stockpulse.storage import PendingMessage, RunResult  # noqa: E402


class MainTests(unittest.TestCase):
    def test_startup_message_contains_project_and_symbol(self) -> None:
        message = build_startup_message()

        self.assertIn("StockPulse", message)
        self.assertIn("TSLA", message)

    def test_preview_mode_does_not_collect(self) -> None:
        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()

    def test_collect_mode_stops_when_token_is_missing(self) -> None:
        with patch(
            "stockpulse.main.load_settings",
            side_effect=ValueError("APIFY_API_TOKEN is missing."),
        ), patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--collect"])

        self.assertEqual(exit_code, 1)
        collect_mock.assert_not_called()

    def test_stats_mode_does_not_collect(self) -> None:
        daily_stats = [
            {
                "stat_date": "2026-08-05",
                "total_messages": 5,
                "bullish_count": 1,
                "bearish_count": 1,
                "unlabeled_count": 3,
                "updated_at": "2026-08-05T00:00:00+00:00",
            }
        ]

        with patch(
            "stockpulse.main.get_daily_stats", return_value=daily_stats
        ), patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--stats"])

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()

    @patch("stockpulse.main.store_message_analyses", return_value=1)
    @patch("stockpulse.main.finish_run")
    @patch("stockpulse.main.start_run", return_value="run-1")
    @patch("stockpulse.main.SentimentAnalyzer")
    @patch("stockpulse.main.get_unanalyzed_messages")
    def test_analyze_mode_uses_only_local_stored_messages(
        self,
        get_pending_mock,
        analyzer_class_mock,
        start_run_mock,
        finish_run_mock,
        store_analyses_mock,
    ) -> None:
        get_pending_mock.return_value = [
            PendingMessage(1, "$TSLA looks strong", "Bullish")
        ]
        analyzer_class_mock.return_value.analyze.return_value = [
            SentimentResult(
                sentiment="Bullish",
                confidence=0.90,
                model_name=DEFAULT_MODEL_NAME,
                model_revision=DEFAULT_MODEL_REVISION,
                raw_label="positive",
                low_confidence=False,
                confidence_threshold=0.60,
                analysis_version=build_analysis_version(
                    DEFAULT_MODEL_NAME, DEFAULT_MODEL_REVISION, 0.60
                ),
            )
        ]

        with patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--analyze"])

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()
        store_analyses_mock.assert_called_once()
        start_run_mock.assert_called_once()
        finish_run_mock.assert_called_once_with(
            "run-1",
            RunResult(status="succeeded", message_count=1, analyzed_count=1),
            database_path=Path("data/stockpulse.db"),
        )

    def test_runs_mode_displays_history_without_collecting(self) -> None:
        history = [
            {
                "started_at": "2026-08-05T01:00:00+00:00",
                "action": "collect",
                "status": "succeeded",
                "message_count": 5,
                "inserted_count": 4,
                "duplicate_count": 1,
                "analyzed_count": 0,
            }
        ]
        with patch(
            "stockpulse.main.get_run_history", return_value=history
        ), patch("stockpulse.main.collect_messages") as collect_mock:
            exit_code = main(["--runs"])

        self.assertEqual(exit_code, 0)
        collect_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
