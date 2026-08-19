# Cloud Run service preparation

StockPulse has separate container images for the Dashboard/read API and the
pinned-model analysis pipeline. The Dashboard image is deployed to Cloud Run;
the AI pipeline image and Cloud Run Job are the next deployment step. Container
definitions themselves do not provision Google Cloud resources.

## Service image

`containers/service.Dockerfile`:

- uses Python 3.12 on a slim Linux base
- installs the base application and PostgreSQL runtime without the optional
  local AI model stack
- runs as a dedicated non-root user
- listens on `0.0.0.0` using the `PORT` value supplied by Cloud Run
- exposes the independent `/api/v1/health` liveness endpoint
- includes the Dashboard assets in the installed Python package

GitHub Actions builds the image, starts it, and verifies both the health endpoint
and Dashboard on every pull request. Local Docker is optional for development.

The separate `containers/job.Dockerfile` builds the daily batch image. It installs both AI
and PostgreSQL dependencies, downloads the exact pinned sentiment model revision
during the image build, runs as a non-root user, and starts
`stockpulse --daily-pipeline`. CI verifies that the image can load the tokenizer
from its local cache without a runtime download.

The daily command creates one durable `pipeline` run and performs collection,
validation/storage, current-version sentiment analysis, topic extraction, daily
metric materialization, and anomaly evaluation. It uses the same server-side
item and Apify charge limits as manual collection. A failure records the bounded
error and preserves external Apify identifiers when they are already known.

## Production configuration preflight

Cloud Run must explicitly set `STOCKPULSE_ENVIRONMENT=production`. Before a
revision or Job is allowed to do real work, run the matching offline preflight:

```text
stockpulse --check-production-config service
stockpulse --check-production-config job
```

Both checks require the PostgreSQL backend and keep the initial connection pool
at four or fewer connections per instance. The Job check additionally requires
an Apify token and verifies that the configured sentiment model and revision
match the model cached in `containers/job.Dockerfile`. The command never opens the database,
contacts Apify, or prints secret values. Normal production service and Job
startup enforce the same role-specific contract automatically.

The Dashboard service does not need the Apify token. Only the daily Job receives
that secret. `STOCKPULSE_DATABASE_URL` is supplied to both runtimes through
Secret Manager; it must never be placed in an image or committed environment
file.

## Local container check

On a computer with Docker installed:

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker run --rm --publish 8080:8080 stockpulse-service
```

The Dashboard is then available at `http://localhost:8080`.

The default image has no historical database. Its liveness endpoint and UI can
start, while `/api/v1/ready` correctly reports that durable data is not ready.

## Production state and boundary

The production Dashboard uses Cloud SQL PostgreSQL rather than its disposable
container filesystem. It is deployed with a dedicated service account, scoped
database secret access, the managed Cloud SQL connection, production runtime
configuration, and direct IAP. The live UI has been verified.

Historical SQLite import was skipped because no local source snapshot was
found. The remaining production boundary is the pipeline Job: build the image
from `containers/job.Dockerfile`, deploy it with the pipeline identity and only
its required secrets, then validate one bounded run before enabling Scheduler.

Apify credentials, local `.env` files, raw snapshots, SQLite files, tests, and
development artifacts are excluded from the container build context.

## Deployment gate

The Dashboard deployment gate has passed: project, region, cost controls,
database, secrets, authentication, and service readiness are configured. The
Job gate remains open until its image is published, the unscheduled Job is
deployed, and one bounded manual run succeeds. Scheduler must not be enabled
before that evidence exists.

Reviewed, offline-rendered service, Job, and Scheduler contracts now live under
[`deploy/`](../../deploy/README.md). The renderer rejects mutable image tags,
unversioned secrets, unapproved regions, and configurations without a recorded
owner decision. Rendering never contacts Google Cloud; applying the output is a
separate deployment action performed only through the approved rollout.

PostgreSQL configuration, bounded pooling, ordered schema migrations, and the
full shared read/write repository contract are implemented and tested against
PostgreSQL 17 in CI. The deployed service now uses PostgreSQL. Historical data
migration was not applicable because no SQLite snapshot was available. See
[PostgreSQL implementation](postgresql.md).
