"""Storage contracts shared by local SQLite and future PostgreSQL backends."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from stockpulse.storage import (
    MessageAnalysis,
    MessageTopic,
    PendingMessage,
    RunResult,
    StorageResult,
    TopicCandidate,
    finish_run,
    get_ai_daily_stats,
    get_anomaly_history,
    get_daily_stats,
    get_messages,
    get_run_history,
    get_representative_candidates,
    get_topic_candidates,
    get_topic_daily_stats,
    get_topic_summary,
    get_unanalyzed_messages,
    start_run,
    store_message_analyses,
    store_anomaly_results,
    store_messages,
    store_message_topics,
)
from stockpulse.anomaly import AnomalyResult
from stockpulse.topics import RepresentativeMessage


class StockPulseRepository(Protocol):
    """Persistence operations required by current application workflows."""

    def store_messages(self, messages: list[dict[str, Any]]) -> StorageResult: ...

    def get_daily_stats(self) -> list[dict[str, Any]]: ...

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
    ) -> list[dict[str, Any]]: ...

    def get_ai_daily_stats(
        self, *, analysis_version: str | None = None
    ) -> list[dict[str, Any]]: ...

    def get_unanalyzed_messages(
        self, *, limit: int, analysis_version: str, reanalyze: bool = False
    ) -> list[PendingMessage]: ...

    def store_message_analyses(
        self, analyses: list[MessageAnalysis], *, overwrite: bool = False
    ) -> int: ...

    def start_run(
        self,
        action: str,
        *,
        symbol: str,
        analysis_version: str | None = None,
        external_run_id: str | None = None,
        max_messages: int | None = None,
        max_total_charge_usd: str | None = None,
        retry_of_run_id: str | None = None,
    ) -> str: ...

    def finish_run(self, run_id: str, result: RunResult) -> None: ...

    def get_run_history(self, *, limit: int = 20) -> list[dict[str, Any]]: ...

    def get_topic_candidates(
        self,
        *,
        topic_version: str,
        analysis_version: str,
        limit: int,
        reanalyze: bool = False,
    ) -> list[TopicCandidate]: ...

    def store_message_topics(
        self, topics: list[MessageTopic], *, overwrite: bool = False
    ) -> int: ...

    def get_topic_summary(self, *, topic_version: str) -> list[dict[str, Any]]: ...

    def get_topic_daily_stats(
        self,
        *,
        topic_version: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def store_anomaly_results(self, results: list[AnomalyResult]) -> int: ...

    def get_anomaly_history(
        self,
        *,
        analysis_version: str | None = None,
        detector_version: str | None = None,
        anomalies_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    def get_representative_candidates(
        self, *, topic: str, topic_version: str, limit: int = 100
    ) -> list[RepresentativeMessage]: ...


@dataclass(frozen=True)
class SQLiteRepository:
    """Local repository backed by one SQLite database file."""

    database_path: Path

    def store_messages(self, messages: list[dict[str, Any]]) -> StorageResult:
        return store_messages(messages, database_path=self.database_path)

    def get_daily_stats(self) -> list[dict[str, Any]]:
        return get_daily_stats(database_path=self.database_path)

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
        return get_messages(
            database_path=self.database_path,
            limit=limit,
            before_created_at=before_created_at,
            before_message_id=before_message_id,
            start_date=start_date,
            end_date=end_date,
            query=query,
            stocktwits_sentiment=stocktwits_sentiment,
            ai_sentiment=ai_sentiment,
            minimum_confidence=minimum_confidence,
            topic=topic,
            topic_version=topic_version,
        )

    def get_ai_daily_stats(
        self, *, analysis_version: str | None = None
    ) -> list[dict[str, Any]]:
        return get_ai_daily_stats(
            database_path=self.database_path,
            analysis_version=analysis_version,
        )

    def get_unanalyzed_messages(
        self, *, limit: int, analysis_version: str, reanalyze: bool = False
    ) -> list[PendingMessage]:
        return get_unanalyzed_messages(
            database_path=self.database_path,
            limit=limit,
            analysis_version=analysis_version,
            reanalyze=reanalyze,
        )

    def store_message_analyses(
        self, analyses: list[MessageAnalysis], *, overwrite: bool = False
    ) -> int:
        return store_message_analyses(
            analyses,
            database_path=self.database_path,
            overwrite=overwrite,
        )

    def start_run(
        self,
        action: str,
        *,
        symbol: str,
        analysis_version: str | None = None,
        external_run_id: str | None = None,
        max_messages: int | None = None,
        max_total_charge_usd: str | None = None,
        retry_of_run_id: str | None = None,
    ) -> str:
        return start_run(
            action,
            database_path=self.database_path,
            symbol=symbol,
            analysis_version=analysis_version,
            external_run_id=external_run_id,
            max_messages=max_messages,
            max_total_charge_usd=max_total_charge_usd,
            retry_of_run_id=retry_of_run_id,
        )

    def finish_run(self, run_id: str, result: RunResult) -> None:
        finish_run(run_id, result, database_path=self.database_path)

    def get_run_history(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return get_run_history(database_path=self.database_path, limit=limit)

    def get_topic_candidates(
        self,
        *,
        topic_version: str,
        analysis_version: str,
        limit: int,
        reanalyze: bool = False,
    ) -> list[TopicCandidate]:
        return get_topic_candidates(
            database_path=self.database_path,
            topic_version=topic_version,
            analysis_version=analysis_version,
            limit=limit,
            reanalyze=reanalyze,
        )

    def store_message_topics(
        self, topics: list[MessageTopic], *, overwrite: bool = False
    ) -> int:
        return store_message_topics(
            topics, database_path=self.database_path, overwrite=overwrite
        )

    def get_topic_summary(self, *, topic_version: str) -> list[dict[str, Any]]:
        return get_topic_summary(
            database_path=self.database_path, topic_version=topic_version
        )

    def get_topic_daily_stats(
        self,
        *,
        topic_version: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        return get_topic_daily_stats(
            database_path=self.database_path,
            topic_version=topic_version,
            start_date=start_date,
            end_date=end_date,
        )

    def store_anomaly_results(self, results: list[AnomalyResult]) -> int:
        return store_anomaly_results(results, database_path=self.database_path)

    def get_anomaly_history(
        self,
        *,
        analysis_version: str | None = None,
        detector_version: str | None = None,
        anomalies_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return get_anomaly_history(
            database_path=self.database_path,
            analysis_version=analysis_version,
            detector_version=detector_version,
            anomalies_only=anomalies_only,
            limit=limit,
        )

    def get_representative_candidates(
        self, *, topic: str, topic_version: str, limit: int = 100
    ) -> list[RepresentativeMessage]:
        return get_representative_candidates(
            database_path=self.database_path,
            topic=topic,
            topic_version=topic_version,
            limit=limit,
        )
