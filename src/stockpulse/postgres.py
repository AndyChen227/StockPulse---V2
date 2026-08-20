"""PostgreSQL connection and ordered schema migration foundations."""

from dataclasses import dataclass
from typing import Any


POSTGRES_SCHEMA_VERSION = 7
MIGRATION_LOCK_ID = 7_389_241_106
PIPELINE_LOCK_ID = 7_389_241_107


@dataclass(frozen=True)
class PostgresMigration:
    """One immutable PostgreSQL schema migration."""

    version: int
    name: str
    sql: str


POSTGRES_MIGRATIONS = (
    PostgresMigration(
        1,
        "foundation_and_sentiment",
        """
        CREATE TABLE messages (
            message_id BIGINT PRIMARY KEY,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            stocktwits_sentiment TEXT,
            symbols_json JSONB NOT NULL,
            username TEXT,
            user_followers BIGINT,
            url TEXT,
            raw_json JSONB NOT NULL,
            collected_at TIMESTAMPTZ NOT NULL,
            ai_sentiment TEXT,
            ai_confidence DOUBLE PRECISION,
            ai_model TEXT,
            ai_model_revision TEXT,
            ai_raw_label TEXT,
            ai_low_confidence BOOLEAN,
            ai_confidence_threshold DOUBLE PRECISION,
            analysis_version TEXT,
            analyzed_at TIMESTAMPTZ
        );
        CREATE INDEX idx_messages_created_at ON messages(created_at);

        CREATE TABLE daily_stats (
            stat_date DATE PRIMARY KEY,
            total_messages INTEGER NOT NULL,
            bullish_count INTEGER NOT NULL,
            bearish_count INTEGER NOT NULL,
            unlabeled_count INTEGER NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );
        """,
    ),
    PostgresMigration(
        2,
        "run_history_and_daily_metrics",
        """
        CREATE TABLE daily_metrics (
            stat_date DATE NOT NULL,
            analysis_version TEXT NOT NULL,
            analyzed_count INTEGER NOT NULL,
            bullish_count INTEGER NOT NULL,
            neutral_count INTEGER NOT NULL,
            bearish_count INTEGER NOT NULL,
            average_confidence DOUBLE PRECISION NOT NULL,
            low_confidence_count INTEGER NOT NULL,
            author_labeled_count INTEGER NOT NULL,
            agreement_count INTEGER NOT NULL,
            sentiment_score DOUBLE PRECISION NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (stat_date, analysis_version)
        );

        CREATE TABLE runs (
            run_id UUID PRIMARY KEY,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            symbol TEXT NOT NULL,
            analysis_version TEXT,
            external_run_id TEXT,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ,
            message_count INTEGER NOT NULL DEFAULT 0,
            inserted_count INTEGER NOT NULL DEFAULT 0,
            duplicate_count INTEGER NOT NULL DEFAULT 0,
            analyzed_count INTEGER NOT NULL DEFAULT 0,
            error_type TEXT,
            error_message TEXT
        );
        CREATE INDEX idx_runs_started_at ON runs(started_at DESC);
        """,
    ),
    PostgresMigration(
        3,
        "run_limits_and_external_metadata",
        """
        ALTER TABLE runs ADD COLUMN invalid_count INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE runs ADD COLUMN external_dataset_id TEXT;
        ALTER TABLE runs ADD COLUMN max_messages INTEGER;
        ALTER TABLE runs ADD COLUMN max_total_charge_usd NUMERIC(10, 4);
        ALTER TABLE runs ADD COLUMN retry_of_run_id UUID REFERENCES runs(run_id);
        """,
    ),
    PostgresMigration(
        4,
        "versioned_message_topics",
        """
        CREATE TABLE message_topics (
            message_id BIGINT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
            topic TEXT NOT NULL,
            score DOUBLE PRECISION NOT NULL,
            matched_terms_json JSONB NOT NULL,
            rank INTEGER NOT NULL,
            topic_version TEXT NOT NULL,
            analyzed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (message_id, topic_version, topic)
        );
        CREATE INDEX idx_message_topics_version_topic
            ON message_topics(topic_version, topic, rank);
        """,
    ),
    PostgresMigration(
        5,
        "versioned_anomaly_results",
        """
        CREATE TABLE anomaly_results (
            fingerprint TEXT PRIMARY KEY,
            stat_date DATE NOT NULL,
            analysis_version TEXT NOT NULL,
            detector_version TEXT NOT NULL,
            status TEXT NOT NULL,
            severity TEXT NOT NULL,
            signals_json JSONB NOT NULL,
            explanation TEXT NOT NULL,
            history_days INTEGER NOT NULL,
            baseline_start_date DATE,
            baseline_end_date DATE,
            current_messages INTEGER NOT NULL,
            baseline_messages DOUBLE PRECISION,
            volume_ratio DOUBLE PRECISION,
            current_sentiment DOUBLE PRECISION NOT NULL,
            baseline_sentiment DOUBLE PRECISION,
            sentiment_shift DOUBLE PRECISION,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX idx_anomaly_results_date
            ON anomaly_results(stat_date DESC, status);
        """,
    ),
    PostgresMigration(
        6,
        "anomaly_topic_shift_metrics",
        """
        ALTER TABLE anomaly_results ADD COLUMN topic_version TEXT;
        ALTER TABLE anomaly_results ADD COLUMN shifted_topic TEXT;
        ALTER TABLE anomaly_results ADD COLUMN current_topic_share DOUBLE PRECISION;
        ALTER TABLE anomaly_results ADD COLUMN baseline_topic_share DOUBLE PRECISION;
        ALTER TABLE anomaly_results ADD COLUMN topic_share_shift DOUBLE PRECISION;
        """,
    ),
    PostgresMigration(
        7,
        "notification_delivery_deduplication",
        """
        CREATE TABLE notification_deliveries (
            dedupe_key TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            status TEXT NOT NULL,
            run_id UUID REFERENCES runs(run_id),
            claimed_at TIMESTAMPTZ NOT NULL,
            sent_at TIMESTAMPTZ,
            error_message TEXT
        );
        CREATE INDEX idx_notification_deliveries_status
            ON notification_deliveries(status, claimed_at);
        """,
    ),
)


def create_postgres_pool(
    database_url: str,
    *,
    min_size: int = 1,
    max_size: int = 4,
    open_pool: bool = False,
) -> Any:
    """Create a bounded Psycopg pool without exposing connection credentials."""

    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("database_url must be a PostgreSQL connection URL")
    if not 1 <= min_size <= max_size <= 10:
        raise ValueError("pool sizes must satisfy 1 <= minimum <= maximum <= 10")

    try:
        from psycopg_pool import ConnectionPool
        from psycopg.rows import dict_row
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL support is not installed. Install "
            "config/requirements/postgres.txt."
        ) from error

    return ConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        timeout=10,
        open=open_pool,
        kwargs={
            "connect_timeout": 10,
            "application_name": "stockpulse",
            "row_factory": dict_row,
        },
    )


def apply_postgres_migrations(connection: Any) -> int:
    """Apply pending migrations atomically and return the resulting version."""

    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        latest_row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
        ).fetchone()
        latest_version = int(
            latest_row["version"] if isinstance(latest_row, dict) else latest_row[0]
        )
        if latest_version > POSTGRES_SCHEMA_VERSION:
            raise ValueError(
                "PostgreSQL schema is newer than this StockPulse version supports."
            )

        for migration in POSTGRES_MIGRATIONS:
            if migration.version <= latest_version:
                continue
            connection.execute(migration.sql)
            connection.execute(
                """
                INSERT INTO schema_migrations (version, name)
                VALUES (%s, %s)
                """,
                (migration.version, migration.name),
            )
            latest_version = migration.version

    return latest_version
