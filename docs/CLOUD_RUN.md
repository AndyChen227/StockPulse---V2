# Cloud Run service preparation

StockPulse now has a container image for the Dashboard and read API. This
is the first part of Stage 7 cloud readiness; it does not provision or deploy
Google Cloud resources.

## Service image

The root `Dockerfile`:

- uses Python 3.12 on a slim Linux base
- installs the base application and PostgreSQL runtime without the optional
  local AI model stack
- runs as a dedicated non-root user
- listens on `0.0.0.0` using the `PORT` value supplied by Cloud Run
- exposes the independent `/api/v1/health` liveness endpoint
- includes the Dashboard assets in the installed Python package

GitHub Actions builds the image, starts it, and verifies both the health endpoint
and Dashboard on every pull request. Local Docker is optional for development.

The separate `Dockerfile.job` builds the daily batch image. It installs both AI
and PostgreSQL dependencies, downloads the exact pinned sentiment model revision
during the image build, runs as a non-root user, and starts
`stockpulse --daily-pipeline`. CI verifies that the image can load the tokenizer
from its local cache without a runtime download.

The daily command creates one durable `pipeline` run and performs collection,
validation/storage, current-version sentiment analysis, topic extraction, daily
metric materialization, and anomaly evaluation. It uses the same server-side
item and Apify charge limits as manual collection. A failure records the bounded
error and preserves external Apify identifiers when they are already known.

## Local container check

On a computer with Docker installed:

```powershell
docker build --tag stockpulse-service .
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

PostgreSQL configuration, bounded pooling, ordered schema migrations, and the
full shared read/write repository contract are implemented and tested against
PostgreSQL 17 in CI. The service is not switched to PostgreSQL until historical
data migration verification passes. See [PostgreSQL implementation](POSTGRESQL.md).
