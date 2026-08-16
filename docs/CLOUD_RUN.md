# Cloud Run service preparation

StockPulse now has a container image for the read-only Dashboard and API. This
is the first part of Stage 7 cloud readiness; it does not provision or deploy
Google Cloud resources.

## Service image

The root `Dockerfile`:

- uses Python 3.12 on a slim Linux base
- installs the base application without the optional local AI model stack
- runs as a dedicated non-root user
- listens on `0.0.0.0` using the `PORT` value supplied by Cloud Run
- exposes the independent `/api/v1/health` liveness endpoint
- includes the Dashboard assets in the installed Python package

GitHub Actions builds the image, starts it, and verifies both the health endpoint
and Dashboard on every pull request. Local Docker is optional for development.

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
shared history. The approved production direction is Cloud SQL for PostgreSQL,
which still requires:

1. a PostgreSQL repository implementation and migration tool
2. Secret Manager integration and a dedicated service account
3. bounded connection pooling and readiness checks
4. authentication for the Dashboard and action endpoints
5. explicit approval before provisioning resources with recurring cost

Apify credentials, local `.env` files, raw snapshots, SQLite files, tests, and
development artifacts are excluded from the container build context.

## Deployment gate

The first real Cloud Run deployment should happen only after the production
repository can connect to durable storage and the user has approved the Google
Cloud project, region, access policy, and expected cost. Until then, this image
is a reproducible deployment artifact and CI smoke-test target.

PostgreSQL configuration, bounded pooling, and ordered schema migrations are
now implemented as a local foundation. See [PostgreSQL implementation](POSTGRESQL.md).
The service is not switched to PostgreSQL until the full repository contract
and SQLite migration verification pass.
