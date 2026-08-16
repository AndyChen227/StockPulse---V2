"""Read-only PostgreSQL repository used by the Dashboard service."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from stockpulse.postgres import POSTGRES_SCHEMA_VERSION
from stockpulse.storage import RUN_ACTIONS, RUN_STATUSES


@dataclass(frozen=True)
class PostgresDashboardRepository:
    """Dashboard query implementation backed by a bounded Psycopg pool."""

    pool: Any

    def check_ready(self) -> bool:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
                ).fetchone()
            return int(_value(row, "version", 0)) == POSTGRES_SCHEMA_VERSION
        except Exception:
            return False

    def get_daily_stats(self) -> list[dict[str, Any]]:
        return self._rows(
            """SELECT stat_date, total_messages, bullish_count, bearish_count,
                      unlabeled_count, updated_at
               FROM daily_stats ORDER BY stat_date"""
        )

    def get_ai_daily_stats(
        self, *, analysis_version: str | None = None
    ) -> list[dict[str, Any]]:
        where = "" if analysis_version is None else "WHERE analysis_version = %s"
        params = () if analysis_version is None else (analysis_version,)
        return self._rows(
            f"""SELECT stat_date, analyzed_count, bullish_count, neutral_count,
                       bearish_count, average_confidence, low_confidence_count,
                       author_labeled_count, agreement_count, sentiment_score,
                       analysis_version, updated_at
                FROM daily_metrics {where} ORDER BY stat_date""",
            params,
        )

    def get_messages(
        self,
        *,
        limit: int = 51,
        before_created_at: str | None = None,
        before_message_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        query: str | None = None,
        stocktwits_sentiment: str | None = None,
        ai_sentiment: str | None = None,
        minimum_confidence: float | None = None,
        topic: str | None = None,
        topic_version: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 101:
            raise ValueError("Message query limit must be between 1 and 101.")
        if (before_created_at is None) != (before_message_id is None):
            raise ValueError("Message cursor time and ID must be provided together.")
        if before_created_at:
            cursor_time = datetime.fromisoformat(before_created_at)
            if cursor_time.tzinfo is None or not before_message_id or before_message_id <= 0:
                raise ValueError("Message cursor must contain an aware time and positive ID.")
        if minimum_confidence is not None and not 0 <= minimum_confidence <= 1:
            raise ValueError("Minimum confidence must be between zero and one.")
        if topic and not topic_version:
            raise ValueError("Topic filtering requires a topic version.")
        _validate_dates(start_date, end_date, "Message")

        filters = ["TRUE"]
        params: list[Any] = []
        if before_created_at and before_message_id:
            filters.append("(m.created_at, m.message_id) < (%s::timestamptz, %s)")
            params.extend((before_created_at, before_message_id))
        if start_date:
            filters.append("m.created_at::date >= %s::date")
            params.append(start_date)
        if end_date:
            filters.append("m.created_at::date <= %s::date")
            params.append(end_date)
        if query:
            filters.append("(m.body ILIKE %s ESCAPE '\\\\' OR COALESCE(m.username, '') ILIKE %s ESCAPE '\\\\')")
            pattern = f"%{_escape_like(query.strip())}%"
            params.extend((pattern, pattern))
        if stocktwits_sentiment:
            filters.append("LOWER(m.stocktwits_sentiment) = LOWER(%s)")
            params.append(stocktwits_sentiment)
        if ai_sentiment:
            filters.append("LOWER(m.ai_sentiment) = LOWER(%s)")
            params.append(ai_sentiment)
        if minimum_confidence is not None:
            filters.append("m.ai_confidence >= %s")
            params.append(minimum_confidence)
        if topic:
            filters.append("EXISTS (SELECT 1 FROM message_topics selected_topic WHERE selected_topic.message_id = m.message_id AND selected_topic.topic = %s AND selected_topic.topic_version = %s)")
            params.extend((topic, topic_version))
        params.append(limit)
        messages = self._rows(
            f"""SELECT m.message_id, m.body, m.created_at,
                       m.stocktwits_sentiment, m.username, m.user_followers, m.url,
                       m.ai_sentiment, m.ai_confidence, m.ai_low_confidence,
                       m.ai_model, m.ai_model_revision, m.analysis_version, m.analyzed_at
                FROM messages m WHERE {' AND '.join(filters)}
                ORDER BY m.created_at DESC, m.message_id DESC LIMIT %s""",
            tuple(params),
        )
        if not messages or not topic_version:
            for message in messages:
                message["topics"] = []
            return messages
        ids = [item["message_id"] for item in messages]
        topic_rows = self._rows(
            """SELECT message_id, topic, score, rank FROM message_topics
               WHERE topic_version = %s AND message_id = ANY(%s)
               ORDER BY message_id, rank, topic""",
            (topic_version, ids),
        )
        grouped: dict[int, list[dict[str, Any]]] = {}
        for row in topic_rows:
            grouped.setdefault(int(row["message_id"]), []).append(
                {key: row[key] for key in ("topic", "score", "rank")}
            )
        for message in messages:
            message["topics"] = grouped.get(int(message["message_id"]), [])
        return messages

    def get_topic_summary(self, *, topic_version: str) -> list[dict[str, Any]]:
        return self._rows(
            """SELECT topic, COUNT(DISTINCT message_id) AS message_count,
                      ROUND(AVG(score)::numeric, 4)::double precision AS average_score
               FROM message_topics WHERE topic_version = %s GROUP BY topic
               ORDER BY message_count DESC, average_score DESC, topic""",
            (topic_version,),
        )

    def get_topic_daily_stats(
        self,
        *,
        topic_version: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        _validate_dates(start_date, end_date, "Topic history")
        filters = ["mt.topic_version = %s"]
        params: list[Any] = [topic_version]
        if start_date:
            filters.append("m.created_at::date >= %s::date")
            params.append(start_date)
        if end_date:
            filters.append("m.created_at::date <= %s::date")
            params.append(end_date)
        return self._rows(
            f"""SELECT m.created_at::date AS stat_date, mt.topic,
                       COUNT(DISTINCT m.message_id) AS message_count,
                       COUNT(*) FILTER (WHERE m.ai_sentiment = 'Bullish') AS bullish_count,
                       COUNT(*) FILTER (WHERE m.ai_sentiment = 'Neutral') AS neutral_count,
                       COUNT(*) FILTER (WHERE m.ai_sentiment = 'Bearish') AS bearish_count,
                       ROUND(AVG(m.ai_confidence)::numeric, 4)::double precision AS average_confidence,
                       ROUND(AVG(mt.score)::numeric, 4)::double precision AS average_topic_score,
                       ROUND(AVG(CASE m.ai_sentiment WHEN 'Bullish' THEN 1.0 WHEN 'Bearish' THEN -1.0 ELSE 0.0 END)::numeric, 4)::double precision AS sentiment_score
                FROM message_topics mt JOIN messages m ON m.message_id = mt.message_id
                WHERE {' AND '.join(filters)} GROUP BY m.created_at::date, mt.topic
                ORDER BY stat_date, mt.topic""",
            tuple(params),
        )

    def get_anomaly_history(
        self,
        *,
        analysis_version: str | None = None,
        detector_version: str | None = None,
        anomalies_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 500:
            raise ValueError("Anomaly history limit must be between 1 and 500.")
        filters = ["TRUE"]
        params: list[Any] = []
        if analysis_version:
            filters.append("analysis_version = %s")
            params.append(analysis_version)
        if detector_version:
            filters.append("detector_version = %s")
            params.append(detector_version)
        if anomalies_only:
            filters.append("status = 'anomaly'")
        params.append(limit)
        rows = self._rows(
            f"""SELECT * FROM anomaly_results WHERE {' AND '.join(filters)}
                ORDER BY stat_date DESC, created_at DESC LIMIT %s""",
            tuple(params),
        )
        for row in rows:
            row["signals"] = tuple(row.pop("signals_json"))
        return rows

    def get_run_history(
        self,
        *,
        limit: int = 20,
        status: str | None = None,
        action: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit <= 0 or limit > 500:
            raise ValueError("Run history limit must be between 1 and 500.")
        _validate_dates(start_date, end_date, "Run history")
        if status and status not in RUN_STATUSES:
            raise ValueError(f"Unsupported run status: {status}")
        if action and action not in RUN_ACTIONS:
            raise ValueError(f"Unsupported run action: {action}")
        filters = ["TRUE"]
        params: list[Any] = []
        for column, value in (("status", status), ("action", action)):
            if value:
                filters.append(f"{column} = %s")
                params.append(value)
        if start_date:
            filters.append("started_at::date >= %s::date")
            params.append(start_date)
        if end_date:
            filters.append("started_at::date <= %s::date")
            params.append(end_date)
        params.append(limit)
        return self._rows(
            f"""SELECT * FROM runs WHERE {' AND '.join(filters)}
                ORDER BY started_at DESC, run_id DESC LIMIT %s""",
            tuple(params),
        )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self._rows("SELECT * FROM runs WHERE run_id = %s", (run_id,))
        return rows[0] if rows else None

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.pool.connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_serialize_row(dict(row)) for row in rows]


def _validate_dates(start: str | None, end: str | None, label: str) -> None:
    try:
        parsed_start = date.fromisoformat(start) if start else None
        parsed_end = date.fromisoformat(end) if end else None
    except ValueError as error:
        raise ValueError(f"{label} dates must use YYYY-MM-DD.") from error
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise ValueError(f"{label} start date cannot be after end date.")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    for key, value in row.items():
        if isinstance(value, datetime):
            row[key] = value.isoformat()
        elif isinstance(value, date):
            row[key] = value.isoformat()
        elif isinstance(value, UUID):
            row[key] = value.hex
        elif isinstance(value, Decimal):
            row[key] = str(value)
    return row


def _value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict):
        return row[key]
    return row[index]
