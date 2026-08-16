"""Read-only HTTP API for the StockPulse dashboard."""

import base64
import binascii
from datetime import date, datetime
import json
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stockpulse import __version__
from stockpulse.anomaly import DETECTOR_VERSION
from stockpulse.config import load_settings
from stockpulse.postgres import create_postgres_pool
from stockpulse.postgres_repository import PostgresDashboardRepository
from stockpulse.repository import SQLiteRepository, StockPulseRepository
from stockpulse.sentiment import build_analysis_version
from stockpulse.topics import TOPIC_ANALYSIS_VERSION


API_VERSION = "v1"
WEB_DIRECTORY = Path(__file__).resolve().parent / "web"


class HealthResponse(BaseModel):
    status: str
    service: str
    application_version: str
    api_version: str


class ReadinessResponse(BaseModel):
    status: str
    database: str


class CollectionResponse(BaseModel):
    data: list[dict[str, Any]]
    meta: dict[str, Any]


class OverviewResponse(BaseModel):
    symbol: str
    latest_metric: dict[str, Any] | None
    latest_anomaly: dict[str, Any] | None
    latest_run: dict[str, Any] | None
    top_topics: list[dict[str, Any]]
    versions: dict[str, str]


class ItemResponse(BaseModel):
    data: dict[str, Any]


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
    postgres_pool = None
    if repository is not None:
        storage = repository
    elif settings.database_backend == "postgresql":
        postgres_pool = create_postgres_pool(
            settings.database_url or "",
            min_size=settings.database_pool_min_size,
            max_size=settings.database_pool_max_size,
            open_pool=True,
        )
        storage = PostgresDashboardRepository(postgres_pool)
    else:
        storage = SQLiteRepository(database_path)
    app = FastAPI(
        title="StockPulse API",
        version=__version__,
        description="Read-only dashboard API for versioned TSLA sentiment history.",
    )
    app.mount("/assets", StaticFiles(directory=WEB_DIRECTORY), name="assets")

    if postgres_pool is not None:
        @app.on_event("shutdown")
        def close_postgres_pool() -> None:
            postgres_pool.close()

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(WEB_DIRECTORY / "index.html")

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            "validation_error",
            "Request validation failed",
            jsonable_encoder(error.errors()),
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        message = error.detail if isinstance(error.detail, str) else "Request failed"
        details = None if isinstance(error.detail, str) else error.detail
        code = "not_found" if error.status_code == 404 else "request_error"
        return _error_response(error.status_code, code, message, details)

    @app.get("/api/v1/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(**{
            "status": "ok",
            "service": "stockpulse-api",
            "application_version": __version__,
            "api_version": API_VERSION,
        })

    @app.get(
        "/api/v1/ready",
        response_model=ReadinessResponse,
        responses={503: {"description": "Database is not ready"}},
    )
    def readiness() -> ReadinessResponse:
        if not storage.check_ready():
            raise HTTPException(status_code=503, detail="Database is not ready")
        return ReadinessResponse(status="ready", database="connected")

    @app.get("/api/v1/overview", response_model=OverviewResponse)
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

    @app.get("/api/v1/metrics/sentiment", response_model=CollectionResponse)
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

    @app.get("/api/v1/topics", response_model=CollectionResponse)
    def topic_summary() -> dict[str, Any]:
        rows = storage.get_topic_summary(topic_version=TOPIC_ANALYSIS_VERSION)
        return {
            "data": rows,
            "meta": {"count": len(rows), "topic_version": TOPIC_ANALYSIS_VERSION},
        }

    @app.get("/api/v1/messages", response_model=CollectionResponse)
    def messages(
        cursor: str | None = Query(default=None, max_length=500),
        limit: int = Query(default=50, ge=1, le=100),
        start_date: date | None = None,
        end_date: date | None = None,
        query: str | None = Query(default=None, min_length=2, max_length=100),
        stocktwits_sentiment: Literal["Bullish", "Neutral", "Bearish"] | None = None,
        ai_sentiment: Literal["Bullish", "Neutral", "Bearish"] | None = None,
        minimum_confidence: float | None = Query(default=None, ge=0, le=1),
        topic: str | None = Query(default=None, min_length=1, max_length=100),
    ) -> dict[str, Any]:
        _validate_date_range(start_date, end_date)
        before_created_at, before_message_id = _decode_message_cursor(cursor)
        rows = storage.get_messages(
            limit=limit + 1,
            before_created_at=before_created_at,
            before_message_id=before_message_id,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            query=query,
            stocktwits_sentiment=stocktwits_sentiment,
            ai_sentiment=ai_sentiment,
            minimum_confidence=minimum_confidence,
            topic=topic,
            topic_version=TOPIC_ANALYSIS_VERSION,
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            _encode_message_cursor(page[-1]["created_at"], page[-1]["message_id"])
            if has_more and page
            else None
        )
        return {
            "data": page,
            "meta": {
                "count": len(page),
                "limit": limit,
                "has_more": has_more,
                "next_cursor": next_cursor,
                "topic_version": TOPIC_ANALYSIS_VERSION,
            },
        }

    @app.get("/api/v1/topics/history", response_model=CollectionResponse)
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

    @app.get("/api/v1/anomalies", response_model=CollectionResponse)
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

    @app.get("/api/v1/runs", response_model=CollectionResponse)
    def run_history(
        limit: int = Query(default=20, ge=1, le=100),
        status: Literal["running", "succeeded", "partial", "failed"] | None = None,
        action: Literal[
            "collect", "resume", "analyze", "reanalyze", "topics", "anomalies"
        ] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        _validate_date_range(start_date, end_date)
        rows = storage.get_run_history(
            limit=limit,
            status=status,
            action=action,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        return {
            "data": rows,
            "meta": {
                "count": len(rows),
                "limit": limit,
                "status": status,
                "action": action,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        }

    @app.get("/api/v1/runs/{run_id}", response_model=ItemResponse)
    def run_detail(
        run_id: str = PathParam(min_length=1, max_length=100),
    ) -> dict[str, Any]:
        run_record = storage.get_run(run_id)
        if run_record is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return {"data": run_record}

    return app


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date",
        )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
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


def _encode_message_cursor(created_at: str, message_id: int) -> str:
    payload = json.dumps(
        {"created_at": created_at, "message_id": int(message_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_message_cursor(cursor: str | None) -> tuple[str | None, int | None]:
    if cursor is None:
        return None, None
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        )
        created_at = str(payload["created_at"])
        message_id = int(payload["message_id"])
        parsed = datetime.fromisoformat(created_at)
        if parsed.tzinfo is None or message_id <= 0:
            raise ValueError
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
        raise HTTPException(status_code=422, detail="Invalid message cursor") from None
    return created_at, message_id


app = create_app()


def run() -> None:
    """Run the local API server or Cloud Run container entry point."""

    import uvicorn

    uvicorn.run(
        "stockpulse.api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
    )
