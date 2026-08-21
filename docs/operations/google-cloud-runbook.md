# Google Cloud launch runbook

> Status: production launch accepted; Dashboard, Pipeline v3, Gmail notifications, and Scheduler live
> Last reviewed: 2026-08-21
> Current cloud state: production Dashboard, Pipeline v3 Job, Gmail notifications, and two weekday Scheduler triggers live in `stockpulse-production`

This is the source of truth for the first StockPulse cloud release. It records
the deployed state, remaining work, architecture, cost boundaries, permissions,
validation, backup, and rollback. Secret values and database credentials must
never be recorded here.

## 0. Deployment progress

Rollout completed across 2026-08-19 through 2026-08-21:

- created GCP project `stockpulse-production` under the `uw.edu` organization
- attached billing with the USD 300 trial credit and configured a USD 20 budget
  with alerts
- enabled the required Google Cloud APIs
- created dedicated service accounts `stockpulse-service`,
  `stockpulse-pipeline`, and `stockpulse-scheduler`
- created Artifact Registry repository `stockpulse` in `us-west1`
- provisioned Cloud SQL for PostgreSQL 17, Enterprise edition, `db-f1-micro`,
  single-zone, with 10 GB SSD storage, backups, point-in-time recovery, and
  deletion protection
- created application database `stockpulse` and a least-privilege application
  role/user
- created Secret Manager secrets `stockpulse-database-url` and
  `stockpulse-apify-token`, with access scoped to the service accounts that need
  each secret; no secret values are stored in this repository
- built the Dashboard image and deployed it to Cloud Run
- configured the managed Cloud SQL connection, runtime environment, and direct
  IAP requirement for the Dashboard
- verified that the Dashboard UI is live and accessible through the intended
  protected path
- skipped historical SQLite migration because no local database snapshot was
  found; production history will begin with new pipeline runs
- built and deployed `stockpulse-daily-pipeline` from the pinned AI Job image
- completed one bounded manual Job execution and verified five messages,
  sentiment analysis, PostgreSQL writes, run history, and successful exit
- created `stockpulse-gmail-app-password` version 1 and granted only the
  pipeline service account Secret Accessor permission
- verified daily-summary, anomaly-test, and failure-test Gmail delivery
- created and end-to-end validated both no-retry weekday Scheduler triggers
- deployed the PostgreSQL-schema-compatible Dashboard image and routed traffic
  to its accepted revision
- created an independent Cloud Monitoring email policy for Cloud Run Job errors
- verified automated backup/PITR settings and created a successful on-demand
  production-acceptance backup

**Current follow-up:** V1 is operationally accepted. Complete the isolated
restore-to-new-instance drill when the Cloud SQL authorization issue is
resolved; the failed 2026-08-21 attempt created no instance or ongoing cost.

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
- two weekday Scheduler triggers at 9:15 AM and 6:00 PM Eastern
- a manual Dashboard trigger calls the Jobs API with the same fixed limits

The job executes one idempotent pipeline: collect, validate, store, analyze
missing current-version records, extract topics, calculate daily metrics, and
evaluate anomalies. The orchestration command and pinned-model Job image are
implemented and validated in CI.

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
| Cloud Run job | Twice-weekday CPU/RAM usage; AI model load dominates |
| Cloud Scheduler | Two jobs; current billing-account free allowance covers up to three jobs |
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
- `stockpulse-gmail-app-password`
- action/confirmation secret only if retained after IAP integration

Grant access to individual secret versions only to the identity that consumes
them. Never store values in GitHub, image layers, deployment YAML, command
history, screenshots, or this runbook.

## 5. Backup and recovery policy

First release policy:

- automated daily backup
- point-in-time recovery with seven-day initial log retention
- on-demand backup before every destructive schema or data migration
- deletion protection enabled
- retain any future approved SQLite migration source read-only outside the
  container; this launch had no source snapshot
- logical PostgreSQL export after launch verification and on a documented
  schedule
- isolated restore drill before closing the recovery gate; V1 was accepted
  with this exercise explicitly deferred after the documented HTTP 403 attempt

Cloud SQL backups disappear with a deleted instance in some configurations;
portable exports provide an additional recovery path. Point-in-time recovery
creates a new instance rather than overwriting the damaged instance.

Reference: https://docs.cloud.google.com/sql/docs/postgres/best-practices

## 6. Provisioning and deployment order

1. [x] Create the dedicated `stockpulse-production` project under `uw.edu` and
   attach billing with the trial credit.
2. [x] Create the USD 20 budget and alerts.
3. [x] Select `us-west1` and record the naming convention.
4. [x] Enable the required APIs.
5. [x] Create dedicated service accounts and narrow IAM and secret grants.
6. [x] Create the `stockpulse` Artifact Registry repository and publish the
   Dashboard image.
7. [x] Create Cloud SQL with deletion protection and backup/PITR policy.
8. [x] Create the application database, least-privilege role/user, and scoped
   Secret Manager values.
9. [x] Deploy the IAP-protected Dashboard service with its Cloud SQL connection
   and production runtime configuration; verify the UI is live.
10. [x] Resolve historical migration: skipped because no local SQLite snapshot
    was found. Do not manufacture or migrate placeholder history.
11. [x] Build the AI pipeline image from
    `containers/job.Dockerfile`, deploy the Cloud Run Job without a schedule,
    and manually validate one bounded run.
12. [x] Validate the manual run's database writes, run record, logs, timeout,
    memory use, idempotency, and paid collection limits.
13. [x] Deploy and validate Gmail notification delivery, then create the two
    weekday Scheduler triggers after the email smoke test passes.
14. [x] Complete final access, data, backup configuration, observability, and
    application/Job rollback-procedure verification.
15. [ ] Complete and privately validate an isolated restore to a temporary
    Cloud SQL instance; explicitly deferred after the 2026-08-21 HTTP 403.
16. [ ] Enable the guarded Dashboard action only after IAP identity and CSRF
    tests; it remains locked for the first release.

## 7. Launch verification

- [x] unauthenticated Dashboard access is rejected
- [x] the approved account can sign in and read all views
- [x] liveness and PostgreSQL readiness behave independently
- [x] historical migration was resolved as not applicable because no source
  snapshot existed; no placeholder source keys were manufactured
- [x] daily metrics, topics, anomalies, messages, and run history were verified
- [x] one bounded Job completed within the configured timeout and memory limit
- [x] duplicate suppression protects messages, versioned results, and emails
- [x] paid collection limits remain 5 messages and $0.05 until explicitly changed
- [x] secrets do not appear in Git or inspected service/log output
- [x] budget alerts and the independent Job-failure notification have recipients
- [x] automated backup, PITR, deletion protection, and an on-demand backup exist
- [ ] an isolated restore has been completed and privately validated (deferred)

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
both service and job together. If a future migration uses a SQLite snapshot,
keep that source read-only during the rollback window.

### Cost emergency

Pause Scheduler and disable manual dispatch first. Scale-to-zero handles idle
Cloud Run service compute, but Cloud SQL continues to incur cost until stopped
or deleted. Export required data before any destructive cleanup.

## 9. Post-V1 operational follow-up

The production foundation, Dashboard, Pipeline v3, Gmail delivery, both
Scheduler triggers, monitoring alert, and backup controls are live and
validated. The isolated restore drill remains the only explicitly deferred
recovery gate. Complete it against a separate temporary instance, validate the
restored schema/data privately, and remove the temporary resource.

Manual Dashboard execution remains disabled in the first release; enabling it
later requires a Cloud Run Jobs dispatcher, distributed action idempotency,
verified IAP identity, and CSRF protection.

Deployment templates and role-specific production preflights are implemented
and tested. Rendering them is offline and does not authorize applying them.

## 10. Owner decisions recorded

Approved on 2026-08-17:

- region: `us-west1`
- direct Cloud Run IAP restricted to the owner's Google account
- Cloud SQL PostgreSQL 17, `db-f1-micro`, shared-core and non-HA
- $20/month budget with 50%, 80%, and 100% alerts
- daily backup, seven-day PITR, and deletion protection
- weekday collection at 9:15 AM and 6:00 PM in `America/New_York`
- two Scheduler jobs with no automatic retries
- manual Dashboard collection remains locked for the first release
- use the confirmed USD 300 trial credit while retaining all cost controls

The authenticated console confirmed the dedicated project, billing attachment,
and USD 300 trial credit during provisioning. The USD 20 budget alerts and all
other cost controls remain active. Deployment approval never authorizes secret
disclosure.

## 11. Production acceptance record — 2026-08-21

Production acceptance completed for project `stockpulse-production` in
`us-west1`.

Pinned release artifacts:

- Pipeline v3 image:
  `us-west1-docker.pkg.dev/stockpulse-production/stockpulse/job@sha256:77c9874838cae740e68f09748409dc4649e78c01d32adc5b2daacd16618bbab2`
- Dashboard source commit and image tag: `781d6760ae59`
- Dashboard image:
  `us-west1-docker.pkg.dev/stockpulse-production/stockpulse/stockpulse-service@sha256:26639af9174f3633137d495e3c18daf5c0d325aad2cd409accbd3f8fef3f4f6e`
- Active Dashboard revision at acceptance:
  `stockpulse-dashboard-00004-99r`

Acceptance evidence:

- execution `stockpulse-daily-pipeline-fdkln` completed successfully
- durable pipeline run ID:
  `8046cb618a2a4166a7c12919f95c558e`
- the bounded Apify run collected five TSLA messages within the configured
  `$0.05` maximum charge
- PostgreSQL writes, sentiment analysis, Dashboard reads, fixed Dashboard URL,
  Gmail notifications, and both weekday Scheduler triggers were validated
- the active Dashboard revision produced no error-level logs after live access
- the Dashboard action remains locked for the first release

Incident note:

- execution `stockpulse-daily-pipeline-4rc5h` failed before container startup
  with `Resource readiness deadline exceeded`
- `ResourcesAvailable`, `Started`, and `Completed` were false, with no container
  application logs
- one controlled retry succeeded; the failure was classified as transient
  Cloud Run resource provisioning rather than application or database failure
- the first Dashboard v3 deployment initially retained traffic on the old
  revision; `gcloud run services update-traffic stockpulse-dashboard
  --to-latest` moved traffic to the compatible revision

Recovery baseline:

- automated daily backups are enabled at `22:00 UTC`
- seven backups and seven days of transaction logs are retained
- point-in-time recovery is enabled
- successful on-demand backup ID: `1787294067917`
- backup description: `post-v3-production-acceptance-2026-08-21`
- a restore drill to a separate temporary instance remains required before
  recovery gate 15 can be marked complete

## 12. Operational follow-up — 2026-08-21

Infrastructure-level failure alerting is enabled independently of application
email:

- alert policy: `StockPulse Pipeline execution failure`
- alert policy ID: `15668922176435779223`
- notification channel: `StockPulse Operations Email`
- notification channel ID: `458967596138340345`
- the policy matches error-level Cloud Run Job logs for
  `stockpulse-daily-pipeline` in `us-west1`
- notifications are rate-limited to one per five minutes and incidents
  auto-close after 24 hours without another matching event

Restore drill status:

- an isolated restore from backup `1787294067917` was attempted with target
  `stockpulse-restore-drill-20260821`
- the Cloud SQL API rejected the restore with HTTP 403 before creating the
  target instance
- a follow-up instance listing confirmed that no temporary instance or ongoing
  restore-drill cost was created
- automated backups, seven-day point-in-time recovery, and the successful
  on-demand backup remain active
- the isolated restore drill is explicitly deferred; recovery gate 15 remains
  open until a restore to a separate instance is completed and validated
