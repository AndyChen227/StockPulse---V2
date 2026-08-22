"""One bounded, idempotent daily StockPulse workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from stockpulse.anomaly import evaluate_anomaly
from stockpulse.collector.apify_client import CollectionBatch, collect_messages
from stockpulse.config import Settings
from stockpulse.notifications import (
    EmailSender,
    SMTPEmailSender,
    anomaly_alert_email,
    daily_summary_email,
    failure_alert_email,
    should_send_daily_summary,
)
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
    notification_sender: EmailSender | None = None,
    now_factory: Callable[[], datetime] | None = None,
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
            notification_sender=notification_sender,
            now_factory=now_factory,
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
    notification_sender: EmailSender | None,
    now_factory: Callable[[], datetime] | None,
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
    sender = notification_sender
    if sender is None and settings.has_email_config:
        sender = SMTPEmailSender(settings)
    clock = now_factory or (
        lambda: datetime.now(ZoneInfo(settings.email_timezone))
    )
    batch: CollectionBatch | None = None
    anomaly_result = None
    inserted = duplicates = analyzed = 0
    stage = "data collection"
    try:
        batch = collector(settings)
        stage = "raw snapshot and database storage"
        raw_writer(batch.messages, symbol=settings.symbol, output_dir=output_dir)
        storage_result = repository.store_messages(batch.messages)
        inserted = storage_result.inserted
        duplicates = storage_result.duplicates

        stage = "sentiment analysis"
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

        stage = "topic analysis"
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

        stage = "metrics and anomaly detection"
        metrics = repository.get_ai_daily_stats(analysis_version=analysis_version)
        if metrics:
            topic_metrics = repository.get_topic_daily_stats(
                topic_version=TOPIC_ANALYSIS_VERSION
            )
            anomaly_result = evaluate_anomaly(
                metrics,
                topic_metrics=topic_metrics,
                topic_version=TOPIC_ANALYSIS_VERSION,
            )
            repository.store_anomaly_results([anomaly_result])

        stage = "run finalization"
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
        if sender is not None and anomaly_result is not None:
            if anomaly_result.status == "anomaly":
                subject, body, html_body = anomaly_alert_email(
                    settings=settings,
                    run_id=run_id,
                    result=anomaly_result,
                )
                _deliver_once(
                    repository,
                    sender,
                    dedupe_key=f"anomaly:{anomaly_result.fingerprint}",
                    kind="anomaly",
                    run_id=run_id,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                )
            if should_send_daily_summary(settings, clock()):
                subject, body, html_body = daily_summary_email(
                    settings=settings,
                    run_id=run_id,
                    run_counts=_run_counts(batch, inserted, duplicates, analyzed),
                    metric=metrics[-1],
                    anomaly=anomaly_result,
                )
                _deliver_once(
                    repository,
                    sender,
                    dedupe_key=(
                        f"daily:{settings.symbol}:{metrics[-1]['stat_date']}"
                    ),
                    kind="daily_summary",
                    run_id=run_id,
                    subject=subject,
                    body=body,
                    html_body=html_body,
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
        if sender is not None:
            subject, body = failure_alert_email(
                settings=settings,
                run_id=run_id,
                stage=stage,
                error=error,
                run_counts=_run_counts(batch, inserted, duplicates, analyzed),
                external_run_id=batch.external_run_id if batch else None,
            )
            _deliver_once(
                repository,
                sender,
                dedupe_key=f"failure:{run_id}",
                kind="failure",
                run_id=run_id,
                subject=subject,
                body=body,
            )
        raise


def _run_counts(
    batch: CollectionBatch | None,
    inserted: int,
    duplicates: int,
    analyzed: int,
) -> dict[str, int]:
    return {
        "messages": len(batch.messages) if batch else 0,
        "inserted": inserted,
        "duplicates": duplicates,
        "analyzed": analyzed,
    }


def _deliver_once(
    repository: StockPulseRepository,
    sender: EmailSender,
    *,
    dedupe_key: str,
    kind: str,
    run_id: str,
    subject: str,
    body: str,
    html_body: str | None = None,
) -> bool:
    """Send once per durable key; leave a failed send eligible for retry."""

    try:
        if not repository.claim_notification(dedupe_key, kind, run_id=run_id):
            return False
        try:
            sender.send(subject=subject, body=body, html_body=html_body)
        except Exception as error:
            repository.finish_notification(
                dedupe_key,
                delivered=False,
                error_message=f"{type(error).__name__}: {error}",
            )
            print(f"Email notification failed ({kind}): {type(error).__name__}")
            return False
        repository.finish_notification(dedupe_key, delivered=True)
        print(f"Email notification delivered: {kind}")
        return True
    except Exception as error:
        print(f"Email notification bookkeeping failed ({kind}): {type(error).__name__}")
        return False
