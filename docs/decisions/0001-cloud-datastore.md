# ADR 0001: Use Cloud SQL for PostgreSQL as the production datastore

- Status: Accepted for implementation; provisioning requires owner approval
- Date: 2026-08-16
- Scope: First Google Cloud release

## Context

StockPulse needs one durable source of truth shared by a Cloud Run job and a Cloud Run service. Cloud Run's writable container filesystem is in-memory and does not persist when an instance stops, so the local SQLite file cannot be the production database ([Cloud Run container runtime contract](https://docs.cloud.google.com/run/docs/container-contract)).

The product must support:

- idempotent writes keyed by Stocktwits message ID
- atomic collection, analysis, metric, and run-status updates
- date-range charts and daily aggregations
- message pagination and combinations of date, author label, AI label, confidence, topic, and analysis-version filters
- relationships among messages, runs, metrics, analysis versions, topics, and anomalies
- schema migrations, backups, restore testing, and auditable operational history
- access from both Cloud Run services and Cloud Run jobs

The initial workload is small: one TSLA collection per day and a low-traffic authenticated dashboard. Predictable behavior and migration safety matter more than extreme horizontal scale.

## Decision

Use **Cloud SQL for PostgreSQL** as the production system of record.

Keep SQLite as the zero-cost local development and test backend. Application code will move behind repository interfaces before the cloud migration so domain workflows do not depend directly on SQLite SQL or connection handling.

Cloud Run will connect using the supported Cloud SQL integration and a dedicated service account with the Cloud SQL Client role. Connections must use a small bounded pool because each Cloud Run service or job instance can open database connections as it scales ([Cloud Run to Cloud SQL connection guidance](https://docs.cloud.google.com/sql/docs/postgres/connect-run)).

## Why PostgreSQL fits StockPulse

1. The current data is relational and already modeled as messages, daily metrics, and runs.
2. SQL naturally supports Dashboard aggregations, flexible filters, stable cursor pagination, joins, and future anomaly replay queries.
3. PostgreSQL preserves a straightforward path from the existing SQLite schema and tests.
4. Cloud SQL supports standard PostgreSQL connectors, SQL import/export, automated and on-demand backups, point-in-time recovery, encryption, monitoring, and Cloud Run integration ([Cloud SQL PostgreSQL features](https://docs.cloud.google.com/sql/docs/postgres/features)).
5. A relational schema provides explicit constraints and migrations for long-lived historical records.

## Alternatives considered

### Firestore Standard edition

Firestore is serverless and attractive for a very small workload because its free quota currently includes one eligible database, 1 GiB stored data, 50,000 document reads per day, and 20,000 document writes per day. Billing also includes document operations, index-entry reads, storage, and network usage; backups and point-in-time recovery are outside the free quota ([Firestore billing](https://firebase.google.com/docs/firestore/pricing)).

It was not selected because StockPulse requires evolving combinations of filters, sorting, aggregation, and related records. Firestore requires indexes for queries, and compound range/sort patterns often require manually managed composite indexes ([Firestore index overview](https://firebase.google.com/docs/firestore/query-data/index-overview)). This would push relational and aggregation complexity into denormalized documents, duplicated writes, and index planning.

Firestore remains a fallback if later evidence shows that the product is mostly fixed-key document reads and the Cloud SQL cost floor is unacceptable.

### SQLite on Cloud Run filesystem

Rejected for production because Cloud Run container filesystem data does not persist when an instance stops. It also cannot safely serve as a shared writable database across independently scaling service and job instances.

### Cloud Storage-hosted SQLite file

Rejected because an object store is not a transactional shared filesystem for concurrent SQLite access. It may be used for exported snapshots and backups, not as the live database.

### AlloyDB

Rejected for the first release because its scale and operational profile exceed this project's small workload. It can be reconsidered only if measured PostgreSQL demand outgrows Cloud SQL.

## Cost and safety guardrails

Cloud SQL charges for provisioned CPU and memory plus storage and networking ([Cloud SQL pricing](https://cloud.google.com/sql/pricing)). Unlike a scale-to-zero Cloud Run service, the database introduces an ongoing cost floor.

Therefore:

- no Cloud SQL instance will be provisioned without the owner's explicit approval
- choose the region together with the Cloud Run service and job to reduce latency and avoid unnecessary network charges
- start with the smallest supported non-HA development configuration that passes measured workload tests
- do not enable high availability, replicas, or extended retention until their need and monthly impact are approved
- configure a Google Cloud budget and alerts before sustained operation
- record the chosen edition, machine size, storage, backup retention, and estimated monthly cost in the deployment runbook
- use separate development and production data only when the additional fixed cost is approved

## Backup and recovery policy

For the first production release:

- enable automated backups and point-in-time recovery
- choose retention based on measured storage cost and recovery requirements
- create an on-demand backup before every destructive migration
- test restoration before launch and after material schema changes
- export a portable logical backup on a documented schedule

Cloud SQL supports automated and on-demand backups and point-in-time recovery; backup retention is configurable ([Cloud SQL backup FAQ](https://docs.cloud.google.com/sql/docs/postgres/faq)).

## Migration path from SQLite

1. Introduce repository protocols for messages, analyses, daily metrics, and runs.
2. Preserve current SQLite implementations for local development and unit tests.
3. Add PostgreSQL implementations with equivalent contract tests.
4. Express schema changes as ordered migrations; never infer production schema only from `CREATE TABLE IF NOT EXISTS`.
5. Write an export command that reads SQLite records in deterministic primary-key order.
6. Import into PostgreSQL using idempotent upserts inside bounded transactions.
7. Verify row counts, primary keys, nullability, timestamps, analysis versions, daily aggregates, and run totals.
8. Run the API against PostgreSQL in a staging environment.
9. Take a final SQLite snapshot, perform the final import, and switch the service and job together.
10. Keep the final SQLite snapshot read-only until the rollback window closes.

## Consequences

Positive consequences:

- Dashboard queries remain clear and adaptable
- current relational data maps naturally to production
- migrations and constraints can be explicit and testable
- backup, recovery, and Cloud Run connectivity have supported managed paths

Tradeoffs:

- there is a monthly database cost even when Dashboard traffic is low
- connection pooling and Cloud SQL IAM configuration must be handled carefully
- local SQLite and production PostgreSQL can behave differently, so shared repository contract tests are required
- provisioning, backup retention, and production sizing remain manual approval gates

## Revisit triggers

Re-evaluate this decision if:

- the approved monthly budget cannot support the smallest acceptable Cloud SQL configuration
- query patterns stabilize into simple document reads with little relational aggregation
- measured scale or availability requirements exceed the selected Cloud SQL configuration
- Google Cloud materially changes relevant pricing or product capabilities before provisioning
