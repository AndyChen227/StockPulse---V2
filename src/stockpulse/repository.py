"""Storage contracts shared by local SQLite and future PostgreSQL backends."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from stockpulse.storage import (
    MessageAnalysis,
    PendingMessage,
    RunResult,
    StorageResult,
    finish_run,
    get_ai_daily_stats,
    get_daily_stats,
    get_run_history,
    get_unanalyzed_messages,
    start_run,
    store_message_analyses,
    store_messages,
)


class StockPulseRepository(Protocol):
    """Persistence operations required by current application workflows."""

    def store_messages(self, messages: list[dict[str, Any]]) -> StorageResult: ...

    def get_daily_stats(self) -> list[dict[str, Any]]: ...

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


@dataclass(frozen=True)
class SQLiteRepository:
    """Local repository backed by one SQLite database file."""

    database_path: Path

    def store_messages(self, messages: list[dict[str, Any]]) -> StorageResult:
        return store_messages(messages, database_path=self.database_path)

    def get_daily_stats(self) -> list[dict[str, Any]]:
        return get_daily_stats(database_path=self.database_path)

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
