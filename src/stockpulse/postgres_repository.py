"""PostgreSQL repository used by Dashboard and background workflows."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from typing import Any
from uuid import UUID, uuid4

from stockpulse.anomaly import AnomalyResult
from stockpulse.postgres import POSTGRES_SCHEMA_VERSION
from stockpulse.storage import (
    MessageAnalysis,
    MessageTopic,
    PendingMessage,
    RUN_ACTIONS,
    RUN_STATUSES,
    RunResult,
    StorageResult,
    TopicCandidate,
)
from stockpulse.topics import RepresentativeMessage
from stockpulse.validation import normalize_created_at, validate_messages


@dataclass(frozen=True)
class PostgresRepository:
    """Complete repository implementation backed by a bounded Psycopg pool."""

    pool: Any

    def store_messages(self, messages: list[dict[str, Any]]) -> StorageResult:
        validate_messages(messages)
        collected_at = datetime.now(timezone.utc)
        inserted = 0
        affected: set[str] = set()
        with self.pool.connection() as connection:
            with connection.transaction():
                for index, message in enumerate(messages, start=1):
                    created_at = normalize_created_at(message["createdAt"], index=index)
                    affected.add(created_at[:10])
                    row = connection.execute(
                        """INSERT INTO messages (
                               message_id, body, created_at, stocktwits_sentiment,
                               symbols_json, username, user_followers, url, raw_json,
                               collected_at
                           ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
                           ON CONFLICT (message_id) DO NOTHING RETURNING message_id""",
                        (
                            int(message["messageId"]), str(message["body"]), created_at,
                            message.get("sentiment"), json.dumps(message.get("symbols", [])),
                            message.get("username"), message.get("userFollowers"),
                            message.get("url"), json.dumps(message), collected_at,
                        ),
                    ).fetchone()
                    inserted += int(row is not None)
                for stat_date in affected:
                    self._refresh_daily_stats(connection, stat_date, collected_at)
        return StorageResult(inserted, len(messages) - inserted, tuple(sorted(affected)))

    def get_unanalyzed_messages(
        self, *, limit: int, analysis_version: str, reanalyze: bool = False
    ) -> list[PendingMessage]:
        if limit <= 0:
            raise ValueError("Analysis limit must be greater than zero.")
        clause = "TRUE" if reanalyze else (
            "ai_sentiment IS NULL OR analysis_version IS NULL OR analysis_version <> %s"
        )
        params = (limit,) if reanalyze else (analysis_version, limit)
        rows = self._rows(
            f"""SELECT message_id, body, stocktwits_sentiment FROM messages
                WHERE {clause} ORDER BY created_at, message_id LIMIT %s""", params
        )
        return [PendingMessage(int(r["message_id"]), r["body"], r["stocktwits_sentiment"]) for r in rows]

    def store_message_analyses(
        self, analyses: list[MessageAnalysis], *, overwrite: bool = False
    ) -> int:
        if not analyses:
            return 0
        now = datetime.now(timezone.utc)
        updated = 0
        versions: set[str] = set()
        with self.pool.connection() as connection:
            with connection.transaction():
                for item in analyses:
                    guard = "" if overwrite else (
                        "AND (ai_sentiment IS NULL OR analysis_version IS NULL OR analysis_version <> %s)"
                    )
                    params: tuple[Any, ...] = (
                        item.sentiment, item.confidence, item.model_name,
                        item.model_revision, item.raw_label, item.low_confidence,
                        item.confidence_threshold, item.analysis_version, now,
                        item.message_id,
                    )
                    if not overwrite:
                        params += (item.analysis_version,)
                    cursor = connection.execute(
                        f"""UPDATE messages SET ai_sentiment=%s, ai_confidence=%s,
                                   ai_model=%s, ai_model_revision=%s, ai_raw_label=%s,
                                   ai_low_confidence=%s, ai_confidence_threshold=%s,
                                   analysis_version=%s, analyzed_at=%s
                            WHERE message_id=%s {guard}""", params
                    )
                    updated += cursor.rowcount
                    if cursor.rowcount:
                        versions.add(item.analysis_version)
                for version in versions:
                    dates = connection.execute(
                        "SELECT DISTINCT created_at::date AS stat_date FROM messages WHERE analysis_version=%s",
                        (version,),
                    ).fetchall()
                    for row in dates:
                        self._refresh_ai_metrics(connection, _value(row, "stat_date", 0), version, now)
        return updated

    def start_run(
        self, action: str, *, symbol: str, analysis_version: str | None = None,
        external_run_id: str | None = None, max_messages: int | None = None,
        max_total_charge_usd: str | None = None, retry_of_run_id: str | None = None,
    ) -> str:
        if action not in RUN_ACTIONS:
            raise ValueError(f"Unsupported run action: {action}")
        if max_messages is not None and max_messages <= 0:
            raise ValueError("Run message limit must be greater than zero.")
        run_id = uuid4()
        with self.pool.connection() as connection:
            connection.execute(
                """INSERT INTO runs (run_id, action, status, symbol, analysis_version,
                       external_run_id, started_at, max_messages, max_total_charge_usd,
                       retry_of_run_id) VALUES (%s,%s,'running',%s,%s,%s,%s,%s,%s,%s)""",
                (run_id, action, symbol, analysis_version, external_run_id,
                 datetime.now(timezone.utc), max_messages, max_total_charge_usd, retry_of_run_id),
            )
            connection.commit()
        return run_id.hex

    def finish_run(self, run_id: str, result: RunResult) -> None:
        if result.status not in RUN_STATUSES - {"running"}:
            raise ValueError("Run result status must be succeeded, partial, or failed.")
        counts = (result.message_count, result.inserted_count, result.duplicate_count,
                  result.analyzed_count, result.invalid_count)
        if any(value < 0 for value in counts):
            raise ValueError("Run result counts cannot be negative.")
        error = " ".join((result.error_message or "").split())[:1000] or None
        with self.pool.connection() as connection:
            cursor = connection.execute(
                """UPDATE runs SET status=%s, finished_at=%s, message_count=%s,
                       inserted_count=%s, duplicate_count=%s, analyzed_count=%s,
                       invalid_count=%s, external_run_id=COALESCE(%s,external_run_id),
                       external_dataset_id=COALESCE(%s,external_dataset_id),
                       error_type=%s, error_message=%s
                   WHERE run_id=%s AND status='running'""",
                (result.status, datetime.now(timezone.utc), *counts,
                 result.external_run_id, result.external_dataset_id,
                 result.error_type, error, run_id),
            )
            connection.commit()
        if cursor.rowcount != 1:
            raise ValueError(f"Run is missing or already finished: {run_id}")

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
            filters.append("(m.body ILIKE %s ESCAPE '!' OR COALESCE(m.username, '') ILIKE %s ESCAPE '!')")
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

    def get_topic_candidates(
        self, *, topic_version: str, analysis_version: str, limit: int,
        reanalyze: bool = False,
    ) -> list[TopicCandidate]:
        if limit <= 0:
            raise ValueError("Topic analysis limit must be greater than zero.")
        clause = "" if reanalyze else (
            "AND NOT EXISTS (SELECT 1 FROM message_topics mt WHERE "
            "mt.message_id=messages.message_id AND mt.topic_version=%s)"
        )
        params = (analysis_version, limit) if reanalyze else (
            analysis_version, topic_version, limit
        )
        rows = self._rows(
            f"""SELECT message_id, body, created_at, ai_sentiment, ai_confidence,
                       user_followers, url FROM messages
                WHERE ai_sentiment IS NOT NULL AND analysis_version=%s {clause}
                ORDER BY created_at, message_id LIMIT %s""", params
        )
        return [TopicCandidate(
            int(r["message_id"]), r["body"], r["created_at"], r["ai_sentiment"],
            float(r["ai_confidence"]), r["user_followers"], r["url"]
        ) for r in rows]

    def store_message_topics(
        self, topics: list[MessageTopic], *, overwrite: bool = False
    ) -> int:
        if not topics:
            return 0
        for item in topics:
            if not item.topic.strip() or not item.topic_version.strip():
                raise ValueError("Topic and topic version cannot be empty.")
            if not 0 <= item.score <= 1 or item.rank <= 0:
                raise ValueError("Topic score or rank is invalid.")
        inserted = 0
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction():
                if overwrite:
                    for key in sorted({(x.message_id, x.topic_version) for x in topics}):
                        connection.execute(
                            "DELETE FROM message_topics WHERE message_id=%s AND topic_version=%s",
                            key,
                        )
                for item in topics:
                    row = connection.execute(
                        """INSERT INTO message_topics (message_id,topic,score,
                               matched_terms_json,rank,topic_version,analyzed_at)
                           VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)
                           ON CONFLICT (message_id,topic_version,topic) DO NOTHING
                           RETURNING message_id""",
                        (item.message_id, item.topic, item.score,
                         json.dumps(item.matched_terms), item.rank,
                         item.topic_version, now),
                    ).fetchone()
                    inserted += int(row is not None)
        return inserted

    def store_anomaly_results(self, results: list[AnomalyResult]) -> int:
        if not results:
            return 0
        inserted = 0
        now = datetime.now(timezone.utc)
        with self.pool.connection() as connection:
            with connection.transaction():
                for r in results:
                    row = connection.execute(
                        """INSERT INTO anomaly_results (
                               fingerprint,stat_date,analysis_version,detector_version,
                               topic_version,status,severity,signals_json,explanation,
                               history_days,baseline_start_date,baseline_end_date,
                               current_messages,baseline_messages,volume_ratio,
                               current_sentiment,baseline_sentiment,sentiment_shift,
                               shifted_topic,current_topic_share,baseline_topic_share,
                               topic_share_shift,created_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,
                                   %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (fingerprint) DO NOTHING RETURNING fingerprint""",
                        (r.fingerprint, r.stat_date, r.analysis_version,
                         r.detector_version, r.topic_version, r.status, r.severity,
                         json.dumps(r.signals), r.explanation, r.history_days,
                         r.baseline_start_date, r.baseline_end_date,
                         r.current_messages, r.baseline_messages, r.volume_ratio,
                         r.current_sentiment, r.baseline_sentiment, r.sentiment_shift,
                         r.shifted_topic, r.current_topic_share, r.baseline_topic_share,
                         r.topic_share_shift, now),
                    ).fetchone()
                    inserted += int(row is not None)
        return inserted

    def get_representative_candidates(
        self, *, topic: str, topic_version: str, limit: int = 100
    ) -> list[RepresentativeMessage]:
        if limit <= 0 or limit > 500:
            raise ValueError("Representative candidate limit must be between 1 and 500.")
        rows = self._rows(
            """SELECT m.message_id,m.body,mt.topic,mt.score AS topic_score,
                      m.ai_sentiment,m.ai_confidence,m.user_followers,m.created_at,m.url
               FROM message_topics mt JOIN messages m ON m.message_id=mt.message_id
               WHERE mt.topic=%s AND mt.topic_version=%s
               ORDER BY m.created_at DESC,m.message_id DESC LIMIT %s""",
            (topic, topic_version, limit),
        )
        return [RepresentativeMessage(
            int(r["message_id"]), r["body"], r["topic"], float(r["topic_score"]),
            r["ai_sentiment"], float(r["ai_confidence"]), r["user_followers"],
            r["created_at"], r["url"]
        ) for r in rows]

    @staticmethod
    def _refresh_daily_stats(connection: Any, stat_date: str, updated_at: datetime) -> None:
        connection.execute(
            """INSERT INTO daily_stats
                   SELECT %s::date, COUNT(*),
                          COUNT(*) FILTER (WHERE stocktwits_sentiment='Bullish'),
                          COUNT(*) FILTER (WHERE stocktwits_sentiment='Bearish'),
                          COUNT(*) FILTER (WHERE stocktwits_sentiment IS NULL), %s
                   FROM messages WHERE created_at::date=%s::date
               ON CONFLICT (stat_date) DO UPDATE SET
                   total_messages=EXCLUDED.total_messages,
                   bullish_count=EXCLUDED.bullish_count,
                   bearish_count=EXCLUDED.bearish_count,
                   unlabeled_count=EXCLUDED.unlabeled_count,
                   updated_at=EXCLUDED.updated_at""",
            (stat_date, updated_at, stat_date),
        )

    @staticmethod
    def _refresh_ai_metrics(
        connection: Any, stat_date: Any, version: str, updated_at: datetime
    ) -> None:
        connection.execute(
            """INSERT INTO daily_metrics
                   SELECT %s::date,%s,COUNT(*),
                          COUNT(*) FILTER (WHERE ai_sentiment='Bullish'),
                          COUNT(*) FILTER (WHERE ai_sentiment='Neutral'),
                          COUNT(*) FILTER (WHERE ai_sentiment='Bearish'),
                          COALESCE(AVG(ai_confidence),0),
                          COUNT(*) FILTER (WHERE ai_low_confidence),
                          COUNT(*) FILTER (WHERE stocktwits_sentiment IS NOT NULL),
                          COUNT(*) FILTER (WHERE stocktwits_sentiment=ai_sentiment),
                          COALESCE(AVG(CASE ai_sentiment WHEN 'Bullish' THEN 1.0
                              WHEN 'Bearish' THEN -1.0 ELSE 0.0 END),0),%s
                   FROM messages WHERE created_at::date=%s::date AND analysis_version=%s
               ON CONFLICT (stat_date,analysis_version) DO UPDATE SET
                   analyzed_count=EXCLUDED.analyzed_count,bullish_count=EXCLUDED.bullish_count,
                   neutral_count=EXCLUDED.neutral_count,bearish_count=EXCLUDED.bearish_count,
                   average_confidence=EXCLUDED.average_confidence,
                   low_confidence_count=EXCLUDED.low_confidence_count,
                   author_labeled_count=EXCLUDED.author_labeled_count,
                   agreement_count=EXCLUDED.agreement_count,
                   sentiment_score=EXCLUDED.sentiment_score,updated_at=EXCLUDED.updated_at""",
            (stat_date, version, updated_at, stat_date, version),
        )

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
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    for key, value in row.items():
        if isinstance(value, datetime):
            row[key] = value.isoformat()
        elif isinstance(value, date):
            row[key] = value.isoformat()
        elif isinstance(value, UUID):
            row[key] = value.hex
        elif isinstance(value, Decimal):
            row[key] = format(value.normalize(), "f")
    return row


def _value(row: Any, key: str, index: int) -> Any:
    if isinstance(row, dict):
        return row[key]
    return row[index]


# Compatibility name retained for the already-published Dashboard integration.
PostgresDashboardRepository = PostgresRepository
