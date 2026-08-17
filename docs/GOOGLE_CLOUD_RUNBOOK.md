# Google Cloud launch runbook

> Status: proposed; owner approval required before any console or provisioning step
> Last reviewed: 2026-08-17
> Current cloud state: no StockPulse Google Cloud resources have been created

This is the pre-console source of truth for the first StockPulse cloud release.
It records the proposed architecture, cost boundaries, permissions, deployment
order, validation, backup, and rollback. Checking this file into Git does not
authorize resource creation.

## 1. Recommended first-release architecture

```text
Allowed Google account
        |
        v
Cloud Run direct IAP
        |
        v
Cloud Run service: Dashboard + read API + guarded action API
        |                         |
        |                         v
        |                  Cloud Run Jobs API
        |                         |
        v                         v
Cloud SQL PostgreSQL <---- Cloud Run daily pipeline job
                                  ^
                                  |
                           Cloud Scheduler
```

Supporting resources are one Artifact Registry repository, Secret Manager,
Cloud Logging, and a Cloud Billing budget. Keep every regional resource in one
approved region.

### Browser authentication

Use IAP directly on Cloud Run and grant access only to the owner's Google
account. Direct Cloud Run IAP now protects the `run.app` URL without requiring
an external load balancer. The service must not also be configured for public
unauthenticated invocation.

The existing action bearer secret is a defense-in-depth/service contract, not a
good browser login experience. Before the action button is enabled, replace the
browser-facing shared secret with verified IAP identity plus CSRF protection.
Never place `STOCKPULSE_ACTION_API_TOKEN` in downloaded JavaScript or browser
storage.

References:

- https://docs.cloud.google.com/run/docs/authenticating/end-users
- https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run

### Web service

- Cloud Run service using request-based billing
- minimum instances: 0
- maximum instances: 1 for the first release
- concurrency: retain the platform default unless load tests justify a change
- CPU: 1; memory: start at 512 MiB and measure
- application database pool: 1-4 connections
- HTTPS only through the managed `run.app` endpoint
- liveness: `/api/v1/health`; readiness: `/api/v1/ready`

Maximum instance count is an initial database and cost guardrail, not a scaling
target. Cloud Run is pay-per-use and can scale to zero when minimum instances is
zero. The writable container filesystem is disposable.

References:

- https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
- https://cloud.google.com/run/pricing

### Daily pipeline job

- separate Cloud Run Job image that includes the pinned AI model runtime
- one task, parallelism 1
- maximum retries 0 for the paid collection step
- initial timeout 15 minutes, adjusted only after measured cold-start inference
- memory selected after a real container peak-memory measurement
- one daily Scheduler trigger
- a manual Dashboard trigger calls the Jobs API with the same fixed limits

The job must execute one idempotent pipeline: collect, validate, store, analyze
missing current-version records, extract topics, calculate daily metrics, and
evaluate anomalies. That single orchestration command and the AI job image are
not implemented yet and are launch blockers.

References:

- https://cloud.google.com/run/docs/create-jobs
- https://docs.cloud.google.com/run/docs/configuring/task-timeout

### Database

- Cloud SQL for PostgreSQL 17
- single-zone, non-HA first release
- smallest shared-core machine that passes migration and query smoke tests
- smallest allowed storage allocation; no read replicas
- same region as service and job
- deletion protection enabled
- private application database/user; never use the default administrative user
- Cloud Run integration over the managed Cloud SQL Unix socket
- bounded pools; no Serverless VPC Access connector for the initial public-IP
  managed-proxy path

The approved logical datastore is PostgreSQL. The exact edition, machine SKU,
storage type, and region-specific price must be copied from the authenticated
Pricing Calculator before creation.

References:

- https://docs.cloud.google.com/sql/docs/postgres/connect-run
- https://cloud.google.com/sql/pricing

## 2. Region decision

Choose exactly one before provisioning:

| Candidate | Advantage | Tradeoff |
|---|---|---|
| `us-west1` (Oregon) | Cost-oriented default near the US West Coast | Slightly farther from a Los Angeles user |
| `us-west2` (Los Angeles) | Lowest user-to-Dashboard latency | Verify whether Cloud SQL and build SKUs cost more |

Recommended default: `us-west1`, because this is a low-traffic daily analytics
product and database cost matters more than a small interactive latency
difference. Use `us-west2` if the final calculator difference is negligible and
the owner prefers locality.

Do not split Cloud Run, Cloud SQL, Artifact Registry, or Scheduler across
regions unless a documented product requirement justifies it.

## 3. Cost plan and guardrails

Current official examples show `db-f1-micro` shared-core compute at $0.0105 per
hour in the displayed default pricing context, roughly $7.67 for 730 hours,
before storage, backups, network, taxes, and region differences. Shared-core
instances have no Cloud SQL SLA. This number is a planning reference, not a
quote.

Expected first-release cost shape:

| Resource | Expected behavior |
|---|---|
| Cloud SQL | Main recurring cost; runs continuously |
| Cloud Run service | Likely very low at scale-to-zero usage |
| Cloud Run job | Once-daily CPU/RAM usage; AI model load dominates |
| Cloud Scheduler | One job; current billing-account free allowance covers up to three jobs |
| Artifact Registry / build | Small storage/build cost possible |
| Secret Manager / logging / backups | Low but non-zero usage possible |
| Apify | Separate external cost, still capped by application configuration |

Before creation:

1. Save a Pricing Calculator estimate for both candidate regions.
2. Approve a target monthly estimate and a maximum tolerated month.
3. Create a project-scoped $20 monthly alert budget with 50%, 80%, and 100%
   thresholds before sustained workloads.
4. Remember that alerts do not stop resources or cap spending.
5. Do not buy commitments, enable HA, add replicas, or keep minimum Cloud Run
   instances without separate approval.

References:

- https://docs.cloud.google.com/billing/docs/how-to/budgets
- https://cloud.google.com/scheduler/pricing

## 4. Identity and least privilege

Use separate service accounts; do not run the application as the default
Compute Engine service account.

| Identity | Minimum intended access |
|---|---|
| Human owner | Project administration during setup; IAP-secured app access |
| Dashboard service account | Cloud SQL Client, required secret versions, permission to execute only the StockPulse job, logging |
| Pipeline job service account | Cloud SQL Client, Apify/database secret versions, logging |
| Scheduler service account | Permission to execute only the StockPulse job |
| CI deploy identity (future) | Artifact upload and narrowly scoped service/job deployment; no database credentials |

Secrets:

- `stockpulse-database-url`
- `stockpulse-apify-token`
- action/confirmation secret only if retained after IAP integration

Grant access to individual secret versions only to the identity that consumes
them. Never store values in GitHub, image layers, deployment YAML, command
history, screenshots, or this runbook.

## 5. Backup and recovery policy

First release proposal:

- automated daily backup
- point-in-time recovery with seven-day initial log retention
- on-demand backup before every destructive schema or data migration
- deletion protection enabled
- final pre-migration SQLite file retained read-only outside the container
- logical PostgreSQL export after launch verification and on a documented
  schedule
- restore drill before declaring launch complete

Cloud SQL backups disappear with a deleted instance in some configurations;
portable exports provide an additional recovery path. Point-in-time recovery
creates a new instance rather than overwriting the damaged instance.

Reference: https://docs.cloud.google.com/sql/docs/postgres/best-practices

## 6. Provisioning and deployment order

No step below begins until the owner approves region, authentication, expected
monthly cost, and billing project.

1. Create or select a dedicated Google Cloud project and attach billing.
2. Create the budget and alerts.
3. Record the region and naming convention.
4. Enable only the required APIs.
5. Create dedicated service accounts and narrow IAM grants.
6. Create Artifact Registry and publish images by immutable digest.
7. Create Cloud SQL with deletion protection and backup/PITR policy.
8. Create the application database/user and Secret Manager values.
9. Deploy the private Dashboard service with PostgreSQL readiness verification.
10. Migrate a disposable copy of SQLite history; compare the verification
    report and Dashboard aggregates.
11. Deploy the pipeline job without a schedule; run one zero/lowest-cost manual
    validation.
12. Configure direct Cloud Run IAP and grant only the approved Google account.
13. Validate login, data reads, logs, failures, and rollback.
14. Create the once-daily Scheduler trigger.
15. Take the final SQLite snapshot, perform final idempotent migration, and
    verify counts and history.
16. Enable the guarded Dashboard action only after IAP identity and CSRF tests.

## 7. Launch verification

- unauthenticated Dashboard access is rejected
- the approved account can sign in and read all views
- liveness and PostgreSQL readiness behave independently
- every migrated source key is verified
- daily metrics, topics, anomalies, messages, and run history match the source
- one job completes within the timeout and memory limit
- duplicate job execution does not duplicate messages or versioned results
- paid collection limits remain 5 messages and $0.05 until explicitly changed
- secrets never appear in logs or service configuration output
- budget alerts have confirmed recipients
- backup exists and a restore drill has been completed

## 8. Rollback

### Application rollback

Route traffic back to the previous known-good Cloud Run revision. Images are
referenced by digest so rollback does not depend on a mutable tag.

### Job rollback

Pause Scheduler, stop manual dispatch, and redeploy the previous job image and
configuration. Do not retry a paid collection blindly; inspect the durable run
record and external Apify run identifier first.

### Database rollback

Prefer forward-compatible application rollback when the schema is backward
compatible. Before destructive changes, take an on-demand backup. For data
loss, restore to a new Cloud SQL instance, validate it privately, then switch
both service and job together. Keep the final SQLite snapshot read-only during
the rollback window.

### Cost emergency

Pause Scheduler and disable manual dispatch first. Scale-to-zero handles idle
Cloud Run service compute, but Cloud SQL continues to incur cost until stopped
or deleted. Export required data before any destructive cleanup.

## 9. Remaining engineering gates

These must be completed before console provisioning:

1. measure the implemented pinned-model Job image cold-start time and peak
   memory on its final container runtime
2. implement the Cloud Run Jobs dispatcher and distributed action idempotency
3. replace browser action-secret handling with verified IAP identity and CSRF
4. add deployment configuration using immutable image digests

## 10. Owner decisions required

- region: `us-west1` or `us-west2`
- direct Cloud Run IAP restricted to the owner's Google account: approve or
  choose a different login approach
- Cloud SQL shared-core, non-HA first release: approve or request HA
- initial budget alert amount: proposed $20/month
- backup/PITR proposal: daily backup plus seven-day recovery window

Until all five decisions are recorded, this runbook remains proposed and no
Google Cloud resources should be created.
