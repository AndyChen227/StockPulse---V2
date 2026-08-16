# StockPulse Product and Delivery Plan

> Last updated: 2026-08-16  
> Status: active development  
> Product target: Google Cloud deployment with a polished dashboard and complete historical records

This document is the durable source of truth for StockPulse's product scope, delivery sequence, and current progress. The README remains the project introduction and local usage guide. Pull requests and commits remain the detailed engineering history.

## 1. Product outcome

StockPulse will become a cost-aware TSLA investor-sentiment monitoring product that runs automatically on Google Cloud and can also be operated through a clear web interface.

The finished product must answer four questions:

1. What are investors discussing today?
2. How does today's sentiment compare with historical behavior?
3. Is the change unusual enough to require attention?
4. What messages and topics explain the change?

It is an informational monitoring product. It does not predict prices, execute trades, or provide financial advice.

## 2. Required dashboard capabilities

The dashboard is a committed product requirement, not a future idea.

### Overview

- Latest collection and analysis time
- Current Bullish, Neutral, and Bearish counts and percentages
- Discussion volume and sentiment score
- Current anomaly status and explanation
- Main discussion topics
- Data freshness and system health

### Historical views

- Daily sentiment and volume charts
- Configurable date range
- Historical anomaly timeline
- Topic history
- Model confidence and low-confidence counts
- Comparison with the selected historical baseline

### Message explorer

- Search and filter stored messages
- Filter by date, sentiment, author label, AI label, confidence, and topic
- Open the original Stocktwits message
- Show author and AI labels separately
- Show the exact analysis version used

### Run history

- Every collection and analysis run
- Start and finish times
- Success, partial success, or failure state
- New, duplicate, invalid, and analyzed message counts
- Apify run and dataset identifiers when available
- Model and pipeline versions
- Error summaries and retry information
- Recorded cost or cost-limit information where available

### Manual controls

- Start a cost-capped collection after explicit confirmation
- Analyze records missing the current analysis version
- Force a bounded reanalysis batch
- Refresh dashboard data
- Inspect run details and errors

Buttons that can spend money or overwrite analysis results must require clear confirmation and show their limits before execution.

## 3. Target cloud shape

The current working architecture is:

```text
Cloud Scheduler
      |
      v
Cloud Run job: collect -> validate -> store -> analyze -> calculate metrics
      |
      v
Durable managed datastore
      ^
      |
Cloud Run service: API + dashboard
      |
      v
Authenticated browser user
```

Supporting services are expected to include secret management, structured logging, error reporting, and budget alerts.

Cloud Run containers have disposable local filesystems. SQLite is therefore a local-development choice, not the planned source of truth for production history. The exact managed datastore will be selected after the query patterns, operating cost, backup needs, and migration path are documented.

## 4. Eight-stage delivery path

| Stage | Outcome | Status |
|---|---|---|
| 1. Foundation | Cost-capped collection, validation, deduplication, SQLite history, experimental versioned sentiment analysis, CI | Complete |
| 2. Durable data contract | Run history, daily metrics, schema versioning, stricter validation, storage abstraction, cloud migration plan | Complete |
| 3. Analysis quality | Finance-specific evaluation set, quality metrics, topic extraction, representative messages | In progress: engineering baseline complete; larger reviewed samples remain |
| 4. Baseline and anomaly detection | Historical baseline, explainable anomaly rules, replay tests, duplicate-alert prevention | In progress |
| 5. Product API | Read APIs, guarded action APIs, pagination, filters, run-status endpoints | In progress: Dashboard read contract complete; authenticated actions remain |
| 6. Dashboard UI | Polished responsive dashboard, charts, tables, controls, history, empty/error/loading states | In progress: initial responsive read-only dashboard implemented |
| 7. Cloud readiness | Docker images, production configuration, authentication, durable datastore, secrets, logs, backups, cost controls | In progress: container and complete PostgreSQL repository implemented; data migration remains |
| 8. Google Cloud launch | Deploy service and job, schedule daily runs, migrate data, verify operations, document rollback and maintenance | Pending |

Six major stages remain before the first complete Google Cloud release. Some work may overlap, but stages should not be skipped because later UI and cloud work depend on reliable data and operational history.

## 5. Definition of done for Google Cloud launch

The first cloud release is complete only when all of the following are true:

- Dashboard is reachable through HTTPS and protected by an agreed authentication method
- Historical data persists across service and job restarts
- Daily collection and analysis run automatically
- Manual actions are bounded, confirmed, and auditable
- Dashboard exposes full run history and useful failure details
- Sentiment, volume, topics, and anomaly history can be filtered by date
- Secrets are not stored in the repository or container image
- Logs identify each run and its outcome
- Cost limits and budget alerts are configured
- Database backup and migration procedures are documented and tested
- Deployment and rollback steps are documented
- CI passes before deployment

## 6. Current implementation

Completed:

- TSLA-only V1 scope
- Stocktwits collection through Apify
- Explicit cost, item, and runtime limits
- Raw JSON snapshots
- SQLite message storage and `messageId` deduplication
- Daily Stocktwits-label statistics
- Experimental local Twitter-RoBERTa sentiment adapter
- Pinned model revision and versioned analysis metadata
- Low-confidence tracking and safe reanalysis behavior
- Durable collection and analysis run records with bounded error summaries
- Versioned daily AI metrics and automatic backfill for existing analysis history
- Explicit schema migration records with protection against opening newer databases
- Shared message-contract validation and canonical UTC timestamps
- Cloud SQL for PostgreSQL selected for production history, with explicit cost approval required before provisioning
- Backend-neutral repository contract with a tested SQLite implementation
- Partial run status, validation counts, limits, retry relationships, and Apify run/dataset identifiers
- Reproducible 36-example finance-specific sentiment benchmark and pinned-model baseline
- ProsusAI FinBERT comparison completed; current Twitter-RoBERTa adapter retained after outperforming it on the tracked benchmark
- Explainable versioned TSLA topic taxonomy, multi-label storage, topic summaries, and source-linked representative-message ranking
- Local `--runs` history view for operational verification
- Python 3.11 and 3.12 GitHub Actions tests

Current limitations:

- Finance-direction evaluation is still provisional: the first balanced synthetic benchmark is too small for production acceptance
- Topic taxonomy quality is not yet measured on a representative real-message sample
- Experimental baseline and anomaly detection are implemented; thresholds still require calibration on representative history
- Actual Apify spend is not yet retrieved; runs currently preserve the configured cost ceiling
- SQLite is not suitable as persistent Cloud Run storage
- Initial read-only product API and responsive Dashboard exist, including
  overview, history charts, message exploration, run history, and explicit
  loading, empty, and error states
- Cost-spending and data-changing controls remain locked until authenticated,
  bounded action APIs are implemented
- Cloud Run service container exists and is smoke-tested in CI; production
  datastore, authentication, secrets, and operational configuration remain
- PostgreSQL secret configuration, bounded pool construction, and six ordered
  schema migrations exist; the shared read/write repository contract runs
  against ephemeral PostgreSQL, while data migration remains
- No Google Cloud resources exist yet

## 7. Immediate work

Stage 3 quality validation continues while Stage 4 begins with an explicitly
experimental anomaly baseline. Production notifications remain disabled until
representative historical replay results have been manually reviewed.

Planned work:

1. Create a finance-specific labeled evaluation set with difficult and mixed-direction examples.
2. Expand the initial 36-example benchmark to at least 150 reviewed examples with a held-out test split.
3. Expand model comparison only with candidates that have acceptable licensing and Stocktwits-relevant behavior.
4. Evaluate and expand the implemented topic taxonomy on a representative labeled sample.
5. Validate representative-message ranking against manually reviewed examples.
6. Add date-bucketed topic metrics for historical Dashboard charts. **Implemented:**
   the repository now returns UTC daily topic counts, sentiment breakdowns,
   confidence, topic strength, sentiment score, and optional date bounds.
7. Validate and refine the initial Dashboard against representative local data.
8. Add authenticated, confirmed, and auditable action APIs before enabling any
   cost-spending or reanalysis controls.

## 8. Documentation system

The project should keep the following records:

- `README.md`: purpose, current capabilities, quick start, concise roadmap, and links
- `docs/PROJECT_PLAN.md`: product requirements, delivery stages, status, and definitions of done
- Pull requests: scoped engineering decisions, validation evidence, and implementation history
- Future architecture decision records: important choices such as datastore, authentication, and frontend approach
- Future deployment runbook: provisioning, deployment, rollback, backup, and incident steps

Progress should be updated when a stage changes status or a product requirement changes. Routine code details belong in pull requests rather than being duplicated here.

Current architecture decisions:

- anomaly detection uses a versioned 28-day rolling median baseline with explicit
  minimum-history, minimum-volume, volume-ratio, and sentiment-shift thresholds;
  see [Anomaly Detection](ANOMALY_DETECTION.md)

- [ADR 0001: Use Cloud SQL for PostgreSQL as the production datastore](adr/0001-cloud-datastore.md)

Current analysis references:

- [Sentiment evaluation](SENTIMENT_EVALUATION.md)
- [Topic analysis and representative messages](TOPIC_ANALYSIS.md)
- [Anomaly detection and replay](ANOMALY_DETECTION.md)
- [Product API](API.md)
- [Dashboard](DASHBOARD.md)
- [Cloud Run service preparation](CLOUD_RUN.md)
- [PostgreSQL implementation](POSTGRESQL.md)

---

# 中文摘要：产品与交付计划

StockPulse 的最终目标是在 Google Cloud 上运行，并提供一个正式、清晰、可操作的 Dashboard。Dashboard 必须展示完整历史记录，包括情绪、帖子、每日指标、异常事件、模型版本和每次任务运行情况。

从现在到首个完整云端版本共有六个剩余阶段：

1. 完成金融方向质量评估与话题提取。
2. 建立历史基线和可解释异常检测。
3. 开发产品 API。
4. 开发正式 Dashboard UI。
5. 完成 Docker、持久化数据库、认证、Secrets、日志、备份和费用保护。
6. 部署 Google Cloud，配置每日调度并完成上线验证。

当前最重要的下一步是验证金融情绪方向质量，并加入话题与代表性帖子数据，让后续 Dashboard 不仅显示变化，还能可靠解释变化原因。
