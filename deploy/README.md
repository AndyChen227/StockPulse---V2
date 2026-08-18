# Reviewed deployment contracts

These files prepare the first Google Cloud release without creating or changing
any cloud resource. They follow the official Cloud Run service and Job YAML
schemas and the Cloud Scheduler Jobs API trigger pattern.

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
- `create-scheduler.ps1`: a deliberately separate, billable command that must
  not be run until the unscheduled Job has passed manual validation
- `manifest.json`: image digests and checksums for audit and rollback

The renderer rejects unapproved configuration, regions outside the reviewed
West Coast choices, cross-project service accounts, mutable image tags,
unversioned secrets, mismatched Cloud SQL names, and malformed schedules.

## First-release boundaries

- The Dashboard service receives the database secret only.
- The Job receives the database and Apify secrets.
- Secret values never enter these files.
- Manual Dashboard collection remains disabled. Scheduler is the only deployed
  Job trigger until IAP identity propagation, CSRF protection, and distributed
  action idempotency are implemented and tested.
- The Scheduler creation command uses OAuth because its target is the Google
  Cloud Run Jobs API on `run.googleapis.com`.

Applying any rendered file or running the Scheduler command is a separate,
explicitly approved deployment action. See `docs/GOOGLE_CLOUD_RUNBOOK.md` for
the required provisioning order, IAM, cost, backup, validation, and rollback.
