# StockPulse Dashboard

The initial StockPulse Dashboard is a responsive, read-only interface served by
the existing FastAPI application at `/`. It uses the versioned `/api/v1` read
contract and does not require a separate frontend server or external browser
assets.

## Current views

- Overview cards for discussion volume, sentiment score, anomaly state, and the
  latest pipeline run
- Bullish, Neutral, and Bearish distribution with current analysis metadata
- Date-range sentiment and volume history
- Topic summary and historical topic filtering
- Latest anomaly explanation
- Cursor-paginated message explorer with text, sentiment, confidence, and topic
  filters
- Run history with a failed-only filter and recorded processing counts
- Database readiness and data-refresh status

Every major data surface has an explicit loading, empty, and error state. The
layout adapts to desktop, tablet, and mobile widths, supports keyboard focus,
and honors reduced-motion preferences.

## Safety boundary

Refreshing and filtering only read stored data. The collection control is
visible but disabled. It must remain locked until the backend provides an
authenticated action endpoint with a displayed cost cap, explicit user
confirmation, bounded execution, and an auditable run record.

The Dashboard never starts an Apify Actor by loading the page.

## Run locally

Install the base project dependencies, make `src` available on `PYTHONPATH`, and
run:

```powershell
stockpulse-api
```

Then open `http://localhost:8080`. API documentation remains available at
`http://localhost:8080/docs`.

An empty local database is supported and displays empty states rather than
invented sample data. Collection is still a separate, explicit command.

## Production state and post-V1 work

- The Dashboard is live on Cloud Run with direct IAP and Cloud SQL PostgreSQL.
- Historical migration was skipped because no local SQLite snapshot was found;
  visible production history now comes from successful Pipeline v3 runs.
- The compatible production image is pinned by digest, and the active revision
  passed live access and error-log verification during acceptance.
- Review the interface with representative production history and refine chart
  and table details after an observation period
- Add a focused run-detail view for error and retry information
- Continue observing the external Cloud Monitoring Job-failure alert. Backup,
  PITR, and rollback procedures are documented; the isolated restore drill is
  explicitly deferred after an HTTP 403 response before instance creation.
- Add verified IAP identity, CSRF protection, cloud Job dispatch, and distributed
  idempotency before unlocking bounded, confirmed collection actions
