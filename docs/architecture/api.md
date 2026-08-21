# Product API

> Status: first-release read contract complete; guarded browser collection remains locked

## Purpose and safety boundary

The V1 API gives the deployed Dashboard access to versioned local or production
history. Its read endpoints intentionally expose no collection, reanalysis, overwrite, email,
or cloud-provisioning action. Opening or refreshing a Dashboard cannot spend
Apify credits through these endpoints.

All endpoints are under `/api/v1`. FastAPI also provides local interactive
OpenAPI documentation at `/docs` and the machine-readable schema at
`/openapi.json`.

## Local start

```powershell
$env:PYTHONPATH = "src"
stockpulse-api
```

The server listens on port `8080` by default and honors the Cloud Run `PORT`
environment variable.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Stable service and API version health response |
| GET | `/api/v1/ready` | Database connectivity and supported-schema readiness |
| GET | `/api/v1/overview` | Latest metric, anomaly, run, top topics, and active versions |
| GET | `/api/v1/metrics/sentiment` | Daily AI sentiment and volume history with inclusive date filters |
| GET | `/api/v1/topics` | Current versioned topic summary |
| GET | `/api/v1/topics/history` | Date-bucketed topic history with inclusive date filters |
| GET | `/api/v1/messages` | Cursor-paginated message explorer with search and filters |
| GET | `/api/v1/anomalies` | Complete or anomaly-only evaluation history with a bounded limit |
| GET | `/api/v1/runs` | Bounded operational run history with date, action, and status filters |
| GET | `/api/v1/runs/{run_id}` | Complete run detail including limits, errors, and external IDs |

Collection endpoints return a `data` list and `meta` object. Date filters use
`YYYY-MM-DD`; an inverted range returns HTTP 422. Run limits are 1-100 and
anomaly limits are 1-500.

### Message explorer

`GET /api/v1/messages` returns newest messages first and accepts:

- `cursor`: opaque continuation value returned by the previous page
- `limit`: 1-100, default 50
- `start_date` and `end_date`: inclusive UTC calendar-date filters
- `query`: literal case-insensitive body or username search, 2-100 characters
- `stocktwits_sentiment`: `Bullish`, `Neutral`, or `Bearish`
- `ai_sentiment`: `Bullish`, `Neutral`, or `Bearish`
- `minimum_confidence`: 0-1
- `topic`: exact current-taxonomy topic name

The cursor is based on both `created_at` and `message_id`, so equal timestamps
remain deterministic and newly inserted messages do not shift later pages. The
response includes `has_more` and `next_cursor`. Each message exposes its source
link, author label, AI label and confidence, analysis version, and current topic
assignments. Raw source JSON is not exposed.

## Version behavior

The API reads the current pinned sentiment analysis version, topic taxonomy
version, and anomaly detector version. The overview response exposes all three
so the Dashboard can display exactly which analysis produced the current data.

## Response and error contracts

FastAPI response models describe health, readiness, overview, collection, and
single-item envelopes in OpenAPI. Collection endpoints use `data` and `meta`;
single-record endpoints use `data`.

HTTP errors have one stable shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

The process-liveness endpoint remains HTTP 200 while the process is running.
The separate readiness endpoint returns HTTP 503 until the configured database
exists, is reachable, and has a supported schema. Cloud Run can therefore stop
routing traffic without confusing a database failure with a crashed process.

## Post-V1 guarded action work

- propagate and verify the signed-in IAP identity at the application boundary
- add browser CSRF protection and a deployment-specific Cloud Run Jobs dispatcher
- provide distributed confirmation/idempotency storage for multiple instances

## Guarded manual action contract

The collection action API is implemented but disabled by default. It is enabled
only when both a separate 32+ character `STOCKPULSE_ACTION_API_TOKEN` and an
application-injected job dispatcher exist.

1. `GET /api/v1/actions/capabilities` reports availability and server limits.
2. `POST /api/v1/actions/collect/confirmation` requires bearer authentication
   and returns a five-minute signed confirmation containing the symbol, message
   limit, and maximum Actor charge.
3. `POST /api/v1/actions/collect` consumes the confirmation once, creates a
   durable running record, and hands the bounded payload to the dispatcher.
4. Dispatch failures finish that run as failed with a bounded error summary.

No production dispatcher exists yet, so the default service cannot start Apify
or a cloud job. Direct Cloud Run IAP protects the deployed read-only Dashboard,
while browser CSRF, verified identity propagation, and multi-instance
idempotency remain explicit requirements before the action can be unlocked.
