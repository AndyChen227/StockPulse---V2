# Google Cloud Launch Runbook / Google Cloud 上线运行手册

[English](#english) · [简体中文](#简体中文)

---

# English

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

Exact prices vary by region, edition, storage, backup usage, networking, and
time. Use the authenticated official Pricing Calculator for every cost review;
do not treat a number copied into this repository as a quote. The selected
shared-core, non-HA instance is a cost-oriented V1 choice and has no Cloud SQL
SLA.

Expected first-release cost shape:

| Resource | Expected behavior |
|---|---|
| Cloud SQL | Main recurring cost; runs continuously |
| Cloud Run service | Likely very low at scale-to-zero usage |
| Cloud Run job | Twice-weekday CPU/RAM usage; AI model load dominates |
| Cloud Scheduler | Two jobs; verify the then-current official allowance and price |
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

---

# 简体中文

> 状态：生产上线已验收；Dashboard、Pipeline v3、Gmail 通知与 Scheduler 均已上线
>
> 最近复核：2026-08-21
>
> 当前云端状态：生产 Dashboard、Pipeline v3 Job、Gmail 通知和两个工作日
> Scheduler 运行在 `stockpulse-production`

本手册是 StockPulse 首个云端版本的事实来源，记录已部署状态、剩余工作、架构、
成本边界、权限、验证、备份与回滚。绝不能在这里记录 Secret 值或数据库凭证。

## 0. 部署进度

2026-08-19 至 2026-08-21 已完成：

- 在 `uw.edu` 组织下创建 GCP 项目 `stockpulse-production`；
- 关联带 300 美元试用额度的 Billing，并设置 20 美元月度预算提醒；
- 启用所需 Google Cloud API；
- 创建专用服务账号 `stockpulse-service`、`stockpulse-pipeline` 和
  `stockpulse-scheduler`；
- 在 `us-west1` 创建 Artifact Registry 仓库 `stockpulse`；
- 配置 Cloud SQL for PostgreSQL 17 Enterprise、`db-f1-micro`、单区、10 GB
  SSD、备份、PITR 和删除保护；
- 创建应用数据库 `stockpulse` 及最小权限角色/用户；
- 创建 `stockpulse-database-url` 与 `stockpulse-apify-token` Secret，只给需要
  它们的服务账号访问权限；仓库不保存 Secret 值；
- 构建 Dashboard 镜像并部署到 Cloud Run；
- 为 Dashboard 配置托管 Cloud SQL 连接、生产运行环境和直接 IAP；
- 验证 Dashboard 可通过预期受保护路径访问；
- 因没有找到本地数据库快照而跳过 SQLite 历史迁移；
- 从固定 AI Job 镜像构建并部署 `stockpulse-daily-pipeline`；
- 完成一次有界手动 Job，验证五条消息、情绪分析、PostgreSQL 写入、运行历史和
  成功退出；
- 创建 `stockpulse-gmail-app-password` 版本 1，只给流水线服务账号 Secret
  Accessor 权限；
- 验证每日摘要、异常 TEST 和失败 TEST Gmail 投递；
- 创建并端到端验证两个不自动重试的工作日 Scheduler；
- 部署兼容 PostgreSQL 模式的 Dashboard 镜像，并把流量切到验收 Revision；
- 为 Cloud Run Job 错误创建独立 Cloud Monitoring 邮件策略；
- 验证自动备份/PITR，并创建一次成功的生产验收按需备份。

**当前后续：** V1 已通过运维验收。Cloud SQL 授权问题解决后，完成独立恢复到
新实例的演练。2026-08-21 失败尝试没有创建实例，也没有持续费用。

## 1. 首个版本架构

```text
获准 Google 账号
        |
        v
Cloud Run 直接 IAP
        |
        v
Cloud Run 服务：Dashboard + 只读 API + 受保护操作 API
        |                         |
        |                         v
        |                  Cloud Run Jobs API
        |                         |
        v                         v
Cloud SQL PostgreSQL <---- Cloud Run 每日流水线 Job
                                  ^
                                  |
                           Cloud Scheduler
```

支持资源包括一个 Artifact Registry 仓库、Secret Manager、Cloud Logging 和
Cloud Billing 预算。所有区域资源保持在一个已批准区域。

### 浏览器认证

直接在 Cloud Run 上使用 IAP，只向所有者 Google 账号授权。直接 Cloud Run
IAP 可以保护 `run.app` URL，不需要外部负载均衡器。服务不得同时允许公开匿名
调用。

现有操作 Bearer Secret 属于纵深防御/服务契约，不是良好的浏览器登录方案。
启用操作按钮前，必须以已验证 IAP 身份和 CSRF 防护替换浏览器共享 Secret。
绝不能把 `STOCKPULSE_ACTION_API_TOKEN` 放进下载的 JavaScript 或浏览器存储。

参考：

- https://docs.cloud.google.com/run/docs/authenticating/end-users
- https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run

### Web 服务

- 使用按请求计费的 Cloud Run 服务；
- 最小实例数 0；
- 首个版本最大实例数 1；
- 并发保持平台默认，除非负载测试支持调整；
- CPU 1；内存从 512 MiB 起并实测；
- 应用数据库连接池 1–4；
- 只通过托管 `run.app` HTTPS 端点访问；
- 存活：`/api/v1/health`；就绪：`/api/v1/ready`。

最大实例数是初始数据库与成本护栏，不是扩展目标。最小实例为零时，Cloud Run
可缩容到零并按使用量付费；可写容器文件系统可随时丢弃。

参考：

- https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run
- https://cloud.google.com/run/pricing

### 每日流水线 Job

- 独立 Cloud Run Job 镜像，包含固定 AI 模型运行环境；
- 一个任务，并行度 1；
- 付费采集步骤最大重试次数 0；
- 初始超时 15 分钟，只有实测冷启动推理后才调整；
- 内存根据真实容器峰值选择；
- 两个工作日 Scheduler：美东上午 9:15 和下午 6:00；
- 未来 Dashboard 手动触发也必须通过 Jobs API 使用相同固定上限。

Job 执行一个幂等流水线：采集、校验、存储、分析缺少当前版本的记录、提取话题、
计算每日指标和评估异常。编排命令与固定模型镜像已实现并通过 CI 与生产验证。

参考：

- https://cloud.google.com/run/docs/create-jobs
- https://docs.cloud.google.com/run/docs/configuring/task-timeout

### 数据库

- Cloud SQL for PostgreSQL 17；
- 首个版本单区、非 HA；
- 能通过迁移和查询冒烟测试的最小共享核机器；
- 最小允许存储，不使用只读副本；
- 与服务和 Job 同区域；
- 启用删除保护；
- 私有应用数据库/用户，绝不使用默认管理员用户；
- 通过托管 Cloud SQL Unix Socket 集成连接 Cloud Run；
- 有界连接池；初始公网托管代理路径不使用 Serverless VPC Access Connector。

已批准的逻辑数据存储是 PostgreSQL。创建前必须从登录后的 Pricing Calculator
取得准确 edition、机器 SKU、存储类型与区域价格。

参考：

- https://docs.cloud.google.com/sql/docs/postgres/connect-run
- https://cloud.google.com/sql/pricing

## 2. 区域决策

配置前只选择一个区域：

| 候选 | 优势 | 权衡 |
|---|---|---|
| `us-west1`（Oregon） | 靠近美国西海岸的成本导向默认值 | 距 Los Angeles 用户略远 |
| `us-west2`（Los Angeles） | 用户到 Dashboard 延迟最低 | 需要核对 Cloud SQL 与构建 SKU 是否更贵 |

最终选择 `us-west1`，因为这是低流量每日分析产品，数据库成本比少量交互延迟
更重要。除非有记录的产品需求，否则不要跨区域拆分 Cloud Run、Cloud SQL、
Artifact Registry 或 Scheduler。

## 3. 成本方案与护栏

具体价格随区域和时间变化，必须以登录后的官方 Pricing Calculator 为准。
首个版本的成本结构是：

| 资源 | 预期行为 |
|---|---|
| Cloud SQL | 主要持续成本；一直运行 |
| Cloud Run 服务 | 可缩容到零，低流量下通常很低 |
| Cloud Run Job | 工作日两次 CPU/内存；AI 模型加载占主导 |
| Cloud Scheduler | 两个 Job；是否免费以当前官方额度为准 |
| Artifact Registry / Build | 可能产生少量存储与构建费用 |
| Secret Manager / Logging / Backups | 可能产生低但非零费用 |
| Apify | 独立外部成本，仍由应用配置硬限制 |

创建前：

1. 为两个候选区域保存 Pricing Calculator 估算；
2. 批准目标月度估算和可容忍最高月度成本；
3. 持续负载前创建项目级 20 美元月度预算，阈值为 50%、80%、100%；
4. 记住预算提醒不会停止资源，也不会限制支出；
5. 未单独批准前，不购买承诺、不启用 HA 或副本，也不保留最小 Cloud Run 实例。

参考：

- https://docs.cloud.google.com/billing/docs/how-to/budgets
- https://cloud.google.com/scheduler/pricing

## 4. 身份与最小权限

使用独立服务账号，不要以默认 Compute Engine 服务账号运行应用。

| 身份 | 最小预期权限 |
|---|---|
| 人类所有者 | 配置期间项目管理；访问 IAP 保护应用 |
| Dashboard 服务账号 | Cloud SQL Client、所需 Secret 版本、只执行 StockPulse Job 的权限、日志 |
| Pipeline Job 服务账号 | Cloud SQL Client、Apify/数据库/Gmail Secret 版本、日志 |
| Scheduler 服务账号 | 只执行 StockPulse Job 的权限 |
| CI 部署身份（未来） | Artifact 上传与窄范围服务/Job 部署；不接触数据库凭证 |

Secret：

- `stockpulse-database-url`；
- `stockpulse-apify-token`；
- `stockpulse-gmail-app-password`；
- 只有 IAP 集成后仍保留时才使用操作/确认 Secret。

只把具体 Secret 版本授权给真正使用它的身份。绝不在 GitHub、镜像层、部署 YAML、
命令历史、截图或本手册中保存值。

## 5. 备份与恢复策略

首个版本策略：

- 每日自动备份；
- 时间点恢复，初始保留 7 天事务日志；
- 每次破坏性模式或数据迁移前创建按需备份；
- 启用删除保护；
- 未来如有获批 SQLite 来源，将其以只读方式保存在容器外；本次上线没有来源；
- 上线验证后按文档化计划进行 PostgreSQL 逻辑导出；
- 关闭恢复门槛前完成独立恢复演练；V1 对 2026-08-21 HTTP 403 尝试进行了
  明确暂缓记录。

某些配置下，删除实例也会删除 Cloud SQL 备份；可移植导出提供额外恢复路径。
PITR 会创建新实例，而不是覆盖受损实例。

参考：https://docs.cloud.google.com/sql/docs/postgres/best-practices

## 6. 配置与部署顺序

1. [x] 在 `uw.edu` 下创建 `stockpulse-production` 并关联试用额度 Billing；
2. [x] 创建 20 美元预算与提醒；
3. [x] 选择 `us-west1` 并记录命名规则；
4. [x] 启用所需 API；
5. [x] 创建专用服务账号和最小 IAM/Secret 授权；
6. [x] 创建 `stockpulse` Artifact Registry 并发布 Dashboard 镜像；
7. [x] 创建带删除保护与备份/PITR 的 Cloud SQL；
8. [x] 创建应用数据库、最小权限用户和限定范围 Secret；
9. [x] 部署连接 Cloud SQL 的 IAP Dashboard，并验证 UI；
10. [x] 处理历史迁移：因无 SQLite 快照而跳过，不制造占位历史；
11. [x] 构建 AI Job 镜像，无计划部署 Job，并手动验证一次有界运行；
12. [x] 验证写入、运行记录、日志、超时、内存、幂等与付费限制；
13. [x] 部署并验证 Gmail，再在冒烟测试通过后创建两个 Scheduler；
14. [x] 完成最终访问、数据、备份配置、可观测性和应用/Job 回滚程序验证；
15. [ ] 恢复到独立临时 Cloud SQL 实例并私下验证；因 2026-08-21 HTTP 403
    明确暂缓；
16. [ ] 通过 IAP 身份与 CSRF 测试后才启用 Dashboard 操作；首个版本保持锁定。

## 7. 上线验证

- [x] 匿名 Dashboard 访问被拒绝；
- [x] 获准账号可以登录并读取全部视图；
- [x] 存活与 PostgreSQL 就绪彼此独立；
- [x] 历史迁移因无来源快照而判定不适用，没有制造占位主键；
- [x] 每日指标、话题、异常、消息和运行历史已验证；
- [x] 一个有界 Job 在配置的超时和内存内完成；
- [x] 消息、版本化结果和邮件都受重复抑制保护；
- [x] 付费采集上限保持 5 条和 0.05 美元；
- [x] Secret 未出现在 Git 或已检查服务/日志输出中；
- [x] 预算提醒与独立 Job 失败通知都有收件人；
- [x] 自动备份、PITR、删除保护和按需备份均存在；
- [ ] 已完成并私下验证独立恢复（暂缓）。

## 8. 回滚

### 应用回滚

把流量路由回上一个已知正常 Cloud Run Revision。镜像按摘要引用，因此回滚不
依赖可变标签。

### Job 回滚

暂停 Scheduler、停止手动调度，并重新部署上一个 Job 镜像与配置。不要盲目
重试付费采集；先检查持久运行记录和外部 Apify 运行 ID。

### 数据库回滚

模式向后兼容时优先使用前向兼容应用回滚。破坏性变化前创建按需备份。发生数据
丢失时，恢复到新的 Cloud SQL 实例，私下验证，再一起切换服务与 Job。未来如
使用 SQLite 快照，在回滚窗口内保持只读。

### 成本紧急情况

先暂停 Scheduler 并禁用手动调度。Cloud Run 服务空闲时可缩容到零，但 Cloud
SQL 会持续产生费用，直到停止或删除。任何破坏性清理前先导出所需数据。

## 9. V1 后运维事项

生产基础、Dashboard、Pipeline v3、Gmail、两个 Scheduler、监控告警与备份控制
均已上线并验证。独立恢复演练是唯一明确暂缓的恢复门槛；应在独立临时实例上
完成，私下验证模式和数据，然后删除临时资源。

首个版本禁用 Dashboard 手动执行。未来启用需要 Cloud Run Jobs 调度器、
分布式操作幂等、已验证 IAP 身份和 CSRF 防护。

部署模板和按角色生产预检已经实现并测试。离线渲染不代表获得应用授权。

## 10. 已记录的所有者决策

2026-08-17 批准：

- 区域：`us-west1`；
- 直接 Cloud Run IAP，仅所有者 Google 账号；
- Cloud SQL PostgreSQL 17、`db-f1-micro`、共享核、非 HA；
- 每月 20 美元预算，阈值 50%、80%、100%；
- 每日备份、7 天 PITR 和删除保护；
- 工作日 `America/New_York` 上午 9:15 与下午 6:00 采集；
- 两个 Scheduler，不自动重试；
- 首个版本锁定 Dashboard 手动采集；
- 使用已确认的 300 美元试用额度，同时保留全部成本控制。

专用项目、Billing 关联和 300 美元试用额度已在登录后的控制台确认。20 美元
预算提醒和其他成本控制保持启用。部署批准永远不授权披露 Secret。

## 11. 生产验收记录 — 2026-08-21

项目 `stockpulse-production` 已在 `us-west1` 完成生产验收。

固定发布产物：

- Pipeline v3 镜像：
  `us-west1-docker.pkg.dev/stockpulse-production/stockpulse/job@sha256:77c9874838cae740e68f09748409dc4649e78c01d32adc5b2daacd16618bbab2`；
- Dashboard 来源 Commit 与镜像标签：`781d6760ae59`；
- Dashboard 镜像：
  `us-west1-docker.pkg.dev/stockpulse-production/stockpulse/stockpulse-service@sha256:26639af9174f3633137d495e3c18daf5c0d325aad2cd409accbd3f8fef3f4f6e`；
- 验收时活动 Dashboard Revision：`stockpulse-dashboard-00004-99r`。

验收证据：

- 执行 `stockpulse-daily-pipeline-fdkln` 成功完成；
- 持久流水线运行 ID：`8046cb618a2a4166a7c12919f95c558e`；
- 有界 Apify 运行在 0.05 美元最高费用内采集五条 TSLA 消息；
- PostgreSQL 写入、情绪分析、Dashboard 读取、固定 URL、Gmail 与两个 Scheduler
  已验证；
- 活动 Dashboard Revision 在线访问后没有 Error 级日志；
- Dashboard 操作在首个版本保持锁定。

事故记录：

- 执行 `stockpulse-daily-pipeline-4rc5h` 在容器启动前因
  `Resource readiness deadline exceeded` 失败；
- `ResourcesAvailable`、`Started`、`Completed` 都为 false，没有容器应用日志；
- 一次受控重试成功，因此被分类为临时 Cloud Run 资源配置问题，而不是应用或
  数据库故障；
- 第一次 Dashboard v3 部署最初仍把流量留在旧 Revision；
  `gcloud run services update-traffic stockpulse-dashboard --to-latest`
  把流量移到兼容 Revision。

恢复基线：

- 每日自动备份时间为 `22:00 UTC`；
- 保留 7 个备份和 7 天事务日志；
- PITR 已启用；
- 成功按需备份 ID：`1787294067917`；
- 备份说明：`post-v3-production-acceptance-2026-08-21`；
- 恢复门槛 15 关闭前，仍需恢复到独立临时实例。

## 12. 运维后续 — 2026-08-21

基础设施失败告警独立于应用邮件启用：

- 告警策略：`StockPulse Pipeline execution failure`；
- 策略 ID：`15668922176435779223`；
- 通知渠道：`StockPulse Operations Email`；
- 渠道 ID：`458967596138340345`；
- 匹配 `us-west1` 中 `stockpulse-daily-pipeline` 的 Error 级 Cloud Run Job 日志；
- 通知限速为每五分钟一次；24 小时没有新匹配事件后自动关闭事故。

恢复演练状态：

- 尝试从备份 `1787294067917` 恢复到
  `stockpulse-restore-drill-20260821`；
- Cloud SQL API 在创建目标实例前以 HTTP 403 拒绝请求；
- 后续实例列表确认没有临时实例或持续演练费用；
- 自动备份、7 天 PITR 与成功按需备份仍保持启用；
- 独立恢复演练被明确暂缓；在恢复到独立实例并验证前，恢复门槛 15 保持开放。
