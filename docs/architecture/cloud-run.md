# Cloud Run service preparation

StockPulse has separate container images for the Dashboard/read API and the
pinned-model analysis pipeline. Cloud readiness is implemented and validated;
these files do not provision or deploy Google Cloud resources.

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

## Production boundary

Do not deploy this image as the final production service with SQLite as its
source of truth. A Cloud Run instance filesystem is disposable and cannot hold
shared history. The image contains the complete PostgreSQL repository and
driver needed for the approved Cloud SQL direction. Production still requires:

1. verified SQLite export and PostgreSQL import
2. Secret Manager integration and a dedicated service account
3. authentication for the Dashboard and action endpoints
4. backup, restore, logging, and rollback procedures
5. explicit approval before provisioning resources with recurring cost

Apify credentials, local `.env` files, raw snapshots, SQLite files, tests, and
development artifacts are excluded from the container build context.

## Deployment gate

The first real Cloud Run deployment should happen only after migration and
authentication are verified and the user has approved the Google Cloud project,
region, access policy, and expected cost. Until then, this image is a
reproducible deployment artifact and CI smoke-test target.

Reviewed, offline-rendered service, Job, and Scheduler contracts now live under
[`deploy/`](../../deploy/README.md). The renderer rejects mutable image tags,
unversioned secrets, unapproved regions, and configurations without a recorded
owner decision. Rendering never contacts Google Cloud; applying the output is a
separate deployment action performed only after the full pre-console review.

PostgreSQL configuration, bounded pooling, ordered schema migrations, and the
full shared read/write repository contract are implemented and tested against
PostgreSQL 17 in CI. The service is not switched to PostgreSQL until historical
data migration verification passes. See [PostgreSQL implementation](postgresql.md).
