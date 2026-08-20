"""One bounded, idempotent daily StockPulse workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from stockpulse.anomaly import evaluate_anomaly
from stockpulse.collector.apify_client import CollectionBatch, collect_messages
from stockpulse.config import Settings
from stockpulse.repository import StockPulseRepository
from stockpulse.sentiment import SentimentAnalyzer, build_analysis_version
from stockpulse.storage import MessageAnalysis, MessageTopic, RunResult, save_raw_messages
from stockpulse.topics import TOPIC_ANALYSIS_VERSION, extract_topics


class PipelineAlreadyRunningError(RuntimeError):
    """Raised before collection when another production pipeline holds the lock."""


def run_daily_pipeline(
    repository: StockPulseRepository,
    settings: Settings,
    *,
    output_dir: Path = Path("data/raw"),
    analysis_limit: int = 100,
    topic_limit: int = 100,
    collector: Callable[[Settings], CollectionBatch] = collect_messages,
    analyzer_factory: Callable[..., Any] = SentimentAnalyzer,
    raw_writer: Callable[..., Path] = save_raw_messages,
) -> str:
    """Collect and materialize all current-version daily analytics once."""

    with repository.pipeline_guard() as acquired:
        if not acquired:
            raise PipelineAlreadyRunningError(
                "Another StockPulse pipeline is already running; collection was not started."
            )
        return _run_daily_pipeline_unlocked(
            repository,
            settings,
            output_dir=output_dir,
            analysis_limit=analysis_limit,
            topic_limit=topic_limit,
            collector=collector,
            analyzer_factory=analyzer_factory,
            raw_writer=raw_writer,
        )


def _run_daily_pipeline_unlocked(
    repository: StockPulseRepository,
    settings: Settings,
    *,
    output_dir: Path,
    analysis_limit: int,
    topic_limit: int,
    collector: Callable[[Settings], CollectionBatch],
    analyzer_factory: Callable[..., Any],
    raw_writer: Callable[..., Path],
) -> str:
    """Run the pipeline after its cross-execution guard has been acquired."""

    analysis_version = build_analysis_version(
        settings.sentiment_model,
        settings.sentiment_model_revision,
        settings.sentiment_threshold,
    )
    run_id = repository.start_run(
        "pipeline",
        symbol=settings.symbol,
        analysis_version=analysis_version,
        max_messages=settings.max_messages,
        max_total_charge_usd=str(settings.max_total_charge_usd),
    )
    batch: CollectionBatch | None = None
    inserted = duplicates = analyzed = 0
    try:
        batch = collector(settings)
        raw_writer(batch.messages, symbol=settings.symbol, output_dir=output_dir)
        storage_result = repository.store_messages(batch.messages)
        inserted = storage_result.inserted
        duplicates = storage_result.duplicates

        pending = repository.get_unanalyzed_messages(
            limit=analysis_limit,
            analysis_version=analysis_version,
        )
        if pending:
            analyzer = analyzer_factory(
                model_name=settings.sentiment_model,
                model_revision=settings.sentiment_model_revision,
                confidence_threshold=settings.sentiment_threshold,
            )
            predictions = analyzer.analyze([message.body for message in pending])
            analyses = [
                MessageAnalysis(
                    message_id=message.message_id,
                    sentiment=prediction.sentiment,
                    confidence=prediction.confidence,
                    model_name=prediction.model_name,
                    model_revision=prediction.model_revision,
                    raw_label=prediction.raw_label,
                    low_confidence=prediction.low_confidence,
                    confidence_threshold=prediction.confidence_threshold,
                    analysis_version=prediction.analysis_version,
                )
                for message, prediction in zip(pending, predictions, strict=True)
            ]
            analyzed = repository.store_message_analyses(analyses)

        topic_candidates = repository.get_topic_candidates(
            topic_version=TOPIC_ANALYSIS_VERSION,
            analysis_version=analysis_version,
            limit=topic_limit,
        )
        assignments = [
            MessageTopic(
                message_id=candidate.message_id,
                topic=prediction.topic,
                score=prediction.score,
                matched_terms=prediction.matched_terms,
                rank=prediction.rank,
                topic_version=prediction.topic_version,
            )
            for candidate in topic_candidates
            for prediction in extract_topics(candidate.body)
        ]
        if assignments:
            repository.store_message_topics(assignments)

        metrics = repository.get_ai_daily_stats(analysis_version=analysis_version)
        if metrics:
            topic_metrics = repository.get_topic_daily_stats(
                topic_version=TOPIC_ANALYSIS_VERSION
            )
            repository.store_anomaly_results([
                evaluate_anomaly(
                    metrics,
                    topic_metrics=topic_metrics,
                    topic_version=TOPIC_ANALYSIS_VERSION,
                )
            ])

        repository.finish_run(
            run_id,
            RunResult(
                status="succeeded",
                message_count=len(batch.messages),
                inserted_count=inserted,
                duplicate_count=duplicates,
                analyzed_count=analyzed,
                external_run_id=batch.external_run_id,
                external_dataset_id=batch.external_dataset_id,
            ),
        )
        return run_id
    except Exception as error:
        repository.finish_run(
            run_id,
            RunResult(
                status="failed",
                message_count=len(batch.messages) if batch else 0,
                inserted_count=inserted,
                duplicate_count=duplicates,
                analyzed_count=analyzed,
                external_run_id=batch.external_run_id if batch else None,
                external_dataset_id=batch.external_dataset_id if batch else None,
                error_type=type(error).__name__,
                error_message=str(error),
            ),
        )
        raise
