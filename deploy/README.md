# Reviewed deployment contracts

These files prepare the first Google Cloud release without creating or changing
any cloud resource. They follow the official Cloud Run service and Job YAML
schemas and the Cloud Scheduler Jobs API trigger pattern.

> Production status — 2026-08-20: the Dashboard and bounded pipeline Job are
> deployed with Cloud SQL; the first manual Job execution succeeded. Gmail
> notification delivery and the two Scheduler triggers are the remaining
> rollout work. These templates remain the reviewed contract for reproducible
> updates, audit, and rollback.

## Safety gate

Copy `config.example.json` to an untracked file outside the repository only
after the owner has approved the runbook decisions. Set the real project values,
numeric Secret Manager versions, and Artifact Registry image references by
immutable `@sha256:` digest. Finally set `approval_recorded` to `true`.

Render locally:

```powershell
python deploy/render.py C:\secure\stockpulse-deployment.json
```

Rendering is offline. It does not invoke `gcloud`, connect to Google Cloud,
create resources, read secret values, or incur charges. Output is written under
the ignored `build/deployment` directory:

- `service.yaml`: private IAP-protected Dashboard service, scale 0-1
- `job.yaml`: single-task daily pipeline, no automatic retries
- `create-scheduler-premarket.ps1`: weekdays at 9:15 AM Eastern
- `create-scheduler-afterhours.ps1`: weekdays at 6:00 PM Eastern
- both Scheduler commands remain separate and must not be run until the
  unscheduled Job has passed manual validation
- `manifest.json`: image digests and checksums for audit and rollback

The renderer rejects unapproved configuration, regions outside the reviewed
West Coast choices, cross-project service accounts, mutable image tags,
unversioned secrets, mismatched Cloud SQL names, and malformed schedules.

## First-release boundaries

- The Dashboard service receives the database secret only.
- The Job receives the database, Apify, and Gmail App Password secrets.
- Gmail delivery sends one later-run daily summary plus detailed anomaly and
  failure alerts, with durable duplicate suppression in PostgreSQL.
- Secret values never enter these files.
- Manual Dashboard collection remains disabled. Scheduler is the only deployed
  Job trigger until IAP identity propagation, CSRF protection, and distributed
  action idempotency are implemented and tested.
- The two Scheduler creation commands use OAuth because their target is the Google
  Cloud Run Jobs API on `run.googleapis.com`.

Applying any rendered file or running the Scheduler command is a separate,
explicitly approved deployment action. See `docs/operations/google-cloud-runbook.md` for
the required provisioning order, IAM, cost, backup, validation, and rollback.

## Notification smoke tests

After the image is deployed, an operator with permission to execute a Job with
overrides can validate the two detailed alert templates without contacting
Apify, opening the database, or changing the saved Job definition:

```powershell
gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,anomaly `
  --wait

gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,failure `
  --wait
```

Both messages start with `[TEST]` and state that no production incident
occurred. Each execution sends exactly one message through the configured SMTP
transport and exits without an Apify request or database write.
