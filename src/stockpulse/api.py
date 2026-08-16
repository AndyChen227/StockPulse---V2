"""Read-only HTTP API for the StockPulse dashboard."""

from datetime import date
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from stockpulse import __version__
from stockpulse.anomaly import DETECTOR_VERSION
from stockpulse.config import load_settings
from stockpulse.repository import SQLiteRepository, StockPulseRepository
from stockpulse.sentiment import build_analysis_version
from stockpulse.topics import TOPIC_ANALYSIS_VERSION


API_VERSION = "v1"


def create_app(
    *,
    repository: StockPulseRepository | None = None,
    database_path: Path = Path("data/stockpulse.db"),
    analysis_version: str | None = None,
) -> FastAPI:
    """Build an injectable FastAPI application without starting a server."""

    settings = load_settings()
    current_analysis_version = analysis_version or build_analysis_version(
        settings.sentiment_model,
        settings.sentiment_model_revision,
        settings.sentiment_threshold,
    )
    storage = repository or SQLiteRepository(database_path)
    app = FastAPI(
        title="StockPulse API",
        version=__version__,
        description="Read-only dashboard API for versioned TSLA sentiment history.",
    )

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "stockpulse-api",
            "application_version": __version__,
            "api_version": API_VERSION,
        }

    @app.get("/api/v1/overview")
    def overview() -> dict[str, Any]:
        metrics = storage.get_ai_daily_stats(
            analysis_version=current_analysis_version
        )
        anomalies = storage.get_anomaly_history(
            analysis_version=current_analysis_version,
            detector_version=DETECTOR_VERSION,
            limit=1,
        )
        runs = storage.get_run_history(limit=1)
        topics = storage.get_topic_summary(topic_version=TOPIC_ANALYSIS_VERSION)
        return {
            "symbol": settings.symbol,
            "latest_metric": metrics[-1] if metrics else None,
            "latest_anomaly": anomalies[0] if anomalies else None,
            "latest_run": runs[0] if runs else None,
            "top_topics": topics[:5],
            "versions": {
                "analysis": current_analysis_version,
                "topics": TOPIC_ANALYSIS_VERSION,
                "anomaly_detector": DETECTOR_VERSION,
            },
        }

    @app.get("/api/v1/metrics/sentiment")
    def sentiment_metrics(
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        _validate_date_range(start_date, end_date)
        rows = storage.get_ai_daily_stats(
            analysis_version=current_analysis_version
        )
        filtered = _filter_dates(rows, start_date=start_date, end_date=end_date)
        return _collection_response(filtered, start_date, end_date)

    @app.get("/api/v1/topics")
    def topic_summary() -> dict[str, Any]:
        rows = storage.get_topic_summary(topic_version=TOPIC_ANALYSIS_VERSION)
        return {
            "data": rows,
            "meta": {"count": len(rows), "topic_version": TOPIC_ANALYSIS_VERSION},
        }

    @app.get("/api/v1/topics/history")
    def topic_history(
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        _validate_date_range(start_date, end_date)
        rows = storage.get_topic_daily_stats(
            topic_version=TOPIC_ANALYSIS_VERSION,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        response = _collection_response(rows, start_date, end_date)
        response["meta"]["topic_version"] = TOPIC_ANALYSIS_VERSION
        return response

    @app.get("/api/v1/anomalies")
    def anomaly_history(
        anomalies_only: bool = False,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        rows = storage.get_anomaly_history(
            analysis_version=current_analysis_version,
            detector_version=DETECTOR_VERSION,
            anomalies_only=anomalies_only,
            limit=limit,
        )
        return {
            "data": rows,
            "meta": {
                "count": len(rows),
                "limit": limit,
                "analysis_version": current_analysis_version,
                "detector_version": DETECTOR_VERSION,
            },
        }

    @app.get("/api/v1/runs")
    def run_history(
        limit: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        rows = storage.get_run_history(limit=limit)
        return {"data": rows, "meta": {"count": len(rows), "limit": limit}}

    return app


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date",
        )


def _filter_dates(
    rows: list[dict[str, Any]],
    *,
    start_date: date | None,
    end_date: date | None,
) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if (not start_date or str(row["stat_date"]) >= start_date.isoformat())
        and (not end_date or str(row["stat_date"]) <= end_date.isoformat())
    ]


def _collection_response(
    rows: list[dict[str, Any]],
    start_date: date | None,
    end_date: date | None,
) -> dict[str, Any]:
    return {
        "data": rows,
        "meta": {
            "count": len(rows),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
    }


app = create_app()


def run() -> None:
    """Run the local API server or Cloud Run container entry point."""

    import uvicorn

    uvicorn.run(
        "stockpulse.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
