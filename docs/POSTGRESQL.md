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
- GitHub Actions applies the migrations to an ephemeral PostgreSQL 17 service
  and runs the complete shared read/write repository contract.
- PostgreSQL now implements the complete shared repository contract: message
  deduplication, daily statistics, versioned sentiment metrics, topic writes,
  anomaly writes, and durable run lifecycle in addition to Dashboard reads.

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

The production service image installs the `postgres` dependency group, while
ordinary local installation remains lightweight. The connection URL remains a
runtime secret and is never baked into the image.

The Dashboard service and command-line background workflows select PostgreSQL
when the backend and secret URL are configured. They apply pending migrations
before serving or processing data and close the bounded pool on shutdown.
SQLite remains the zero-cost default.

## Remaining implementation sequence

1. Add deterministic SQLite export and idempotent PostgreSQL import.
2. Compare row counts, identifiers, timestamps, versions, and aggregates.
3. Add Secret Manager and Cloud SQL connector configuration.
4. Complete the pre-console architecture, cost, IAM, region, backup, and
   rollback review with the owner.
5. Only after explicit approval, provision Google Cloud resources.
