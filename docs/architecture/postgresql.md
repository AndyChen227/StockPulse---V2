# PostgreSQL implementation

StockPulse keeps SQLite as the zero-cost local backend and uses PostgreSQL as
the production system of record. The live Dashboard connects to Cloud SQL for
PostgreSQL 17 in `stockpulse-production` through the managed Cloud Run
integration and a bounded application pool.

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

Production PostgreSQL deployments provide the following values through runtime
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

## Historical data migration

The migration tool remains available for any approved SQLite source. For the
first production launch, no local `stockpulse.db` snapshot was found, so this
step was intentionally skipped. Production history begins with new pipeline
runs; no placeholder data should be manufactured.

Preview the source inventory without connecting to or writing PostgreSQL:

```powershell
stockpulse-migrate --source data/stockpulse.db
```

After the PostgreSQL runtime secret is configured, explicitly apply the import:

```powershell
stockpulse-migrate --source data/stockpulse.db --apply
```

The importer requires SQLite schema version 6, reads the source in read-only
mode, imports all six business tables in foreign-key order, and restores run
retry relationships in a second pass. PostgreSQL writes and source-key
verification share one transaction, so a failed verification rolls back the
entire attempt. Primary-key conflicts are skipped, making a verified rerun
idempotent.

## Current production state and remaining sequence

Completed:

- Cloud SQL PostgreSQL 17 Enterprise, `db-f1-micro`, single-zone, 10 GB SSD
- application database `stockpulse` and least-privilege role/user
- backups, PITR, deletion protection, and managed Cloud Run connectivity
- database URL secret access scoped to the service identities that require it
- Dashboard PostgreSQL readiness and live UI verification

Remaining:

1. Deploy the pipeline Cloud Run Job and validate one bounded write path.
2. Verify the resulting messages, metrics, topics, anomalies, and run history.
3. Complete backup restore, rollback, and ongoing operational checks.
