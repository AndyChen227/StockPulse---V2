# PostgreSQL implementation

StockPulse keeps SQLite as the zero-cost local backend and is adding PostgreSQL
as the production backend in controlled stages. No Cloud SQL resource is needed
to validate the configuration and schema foundation in this stage.

## Current foundation

- PostgreSQL is an optional dependency, so ordinary local installation remains
  lightweight.
- The connection URL is treated as a secret and never appears in the settings
  representation.
- Pool size is bounded to 10 connections and defaults to 1–4 connections.
- The pool is created closed by default, so importing configuration cannot open
  a network connection.
- Six ordered migrations mirror the current SQLite schema history.
- A PostgreSQL advisory transaction lock prevents two service instances from
  applying migrations concurrently.
- PostgreSQL-native `TIMESTAMPTZ`, `DATE`, `JSONB`, `BIGINT`, `BOOLEAN`, UUID,
  and numeric types preserve stronger production constraints.
- A database created by a newer application version is rejected rather than
  silently downgraded.
- The Dashboard read repository supports readiness, overview metrics, stable
  message pagination and filters, topic summary/history, anomaly history, and
  run history/detail.
- GitHub Actions applies the migrations to an ephemeral PostgreSQL 17 service,
  inserts representative records, and verifies API-safe query results.

## Configuration

The default remains:

```text
STOCKPULSE_DATABASE_BACKEND=sqlite
```

Future PostgreSQL deployments will provide the following values through runtime
configuration and Secret Manager, not a committed `.env` file:

```text
STOCKPULSE_DATABASE_BACKEND=postgresql
STOCKPULSE_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/stockpulse
STOCKPULSE_DATABASE_POOL_MIN_SIZE=1
STOCKPULSE_DATABASE_POOL_MAX_SIZE=4
```

The read-only Dashboard service selects PostgreSQL when the backend and secret
URL are configured. SQLite remains the default. Collection and analysis jobs
are not switched yet because PostgreSQL write operations are still pending.

## Remaining implementation sequence

1. Implement PostgreSQL collection, analysis, topic, anomaly, and run writes.
2. Run the complete shared repository contract against ephemeral PostgreSQL.
3. Add deterministic SQLite export and idempotent PostgreSQL import.
4. Compare row counts, identifiers, timestamps, versions, and aggregates.
5. Wire background jobs to select the repository from validated settings.
6. Add Secret Manager and Cloud SQL connector configuration.
7. Complete the pre-console architecture, cost, IAM, region, backup, and
   rollback review with the owner.
8. Only after explicit approval, provision Google Cloud resources.
