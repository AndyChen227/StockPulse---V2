# StockPulse Product and Delivery Plan / StockPulse 产品与交付计划

> Last updated: 2026-08-21
>
> Status: V1 operational launch accepted; isolated Cloud SQL restore drill explicitly deferred
> Product target: a private, cost-controlled Google Cloud Dashboard with complete history

This is the source of truth for present status, remaining priorities, and launch acceptance. Historical implementation detail belongs in [Project History](project-history.md). English appears first; Chinese follows.

---

# English

## 1. Product outcome

StockPulse will be a private, explainable TSLA investor-sentiment monitor running twice each weekday on Google Cloud. The Dashboard must show what investors are discussing, how sentiment compares with history, whether the change is unusual, and which messages and topics explain it.

The product does not predict prices, trade, or provide financial advice.

## 2. Delivery status

| Stage | Outcome | Status |
|---|---|---|
| 1. Foundation | Cost-capped collection, validation, deduplication, local history, sentiment, CI | Complete |
| 2. Durable data | Run history, metrics, migrations, repository contract | Complete |
| 3. Analysis | Benchmark, pinned sentiment, topics, representatives | Engineering complete; quality expansion remains |
| 4. Anomaly detection | Historical baseline, topic shift, explanations, replay safety | Engineering complete; production calibration remains |
| 5. Product API | Read APIs, filters, pagination, guarded actions | Read path complete; browser write action locked |
| 6. Dashboard | Responsive overview, trends, messages, and run history | Complete for first read-only release |
| 7. Cloud readiness | PostgreSQL, containers, pipeline, preflight, deployment contracts | Complete and CI-validated |
| 8. Google Cloud launch | Real resources, migration decision, IAP, schedule, operations | **V1 accepted; isolated restore drill deferred** |
| 9. Post-launch hardening | Observation, threshold calibration, alerts, action enablement | In progress: external failure alert live; calibration and action enablement remain |

## 3. First-release user experience

The owner signs in with an approved Google account and opens one private HTTPS Dashboard. It provides:

- Latest data freshness, run state, sentiment score, volume, confidence, and anomaly status
- Bullish/Neutral/Bearish distribution and historical charts
- Current and historical topic drivers
- Searchable and filterable source-message history
- Full run history, processing counts, versions, errors, retries, and external IDs
- Clear empty, loading, error, and readiness states

Manual collection remains visibly locked. The initial production system is operated by two weekday Scheduler jobs.

## 4. Approved launch boundaries

| Decision | First release |
|---|---|
| Region | `us-west1` |
| Access | Direct Cloud Run IAP; owner Google account only |
| Web service | Minimum 0, maximum 1 instance, 1 CPU, measure memory from 512 MiB |
| Pipeline | Separate pinned-model Cloud Run Job, one task, no retries, initial 15-minute timeout |
| Database | Cloud SQL PostgreSQL 17, `db-f1-micro`, single-zone, non-HA |
| Schedule | Weekdays 09:15 and 18:00 `America/New_York` |
| Recovery | Daily backup, seven-day PITR, deletion protection, successful on-demand backup; isolated restore drill deferred |
| Budget | USD 20 monthly alerts at 50%, 80%, and 100% |
| Credits | Use Welcome Credit only after console confirms eligibility |
| Manual actions | Disabled until identity, CSRF, dispatch, and distributed idempotency are complete |

## 5. Exact next steps

### Completed production foundation

1. [x] Created `stockpulse-production` under the `uw.edu` organization and attached billing with the USD 300 trial credit.
2. [x] Configured the USD 20 budget alerts, enabled required APIs, and created the service, pipeline, and Scheduler service accounts.
3. [x] Created the `stockpulse` Artifact Registry repository in `us-west1`.
4. [x] Provisioned Cloud SQL PostgreSQL 17 with the approved database, least-privilege role/user, backups, PITR, and deletion protection.
5. [x] Created narrowly scoped database and Apify secrets.
6. [x] Built and deployed the Dashboard image with Cloud SQL runtime settings and direct IAP, then verified that the UI is live.
7. [x] Closed the history-migration gate: no local SQLite snapshot was found, so migration was skipped and no placeholder history was manufactured.

### Completed V1 rollout and validation

8. [x] Built Pipeline v3 from `containers/job.Dockerfile`, published it, and deployed the Job by immutable digest.
9. [x] Completed one bounded five-message run and verified PostgreSQL writes, durable run history, logs, limits, and successful exit.
10. [x] Verified daily-summary, anomaly-test, and failure-test Gmail delivery with durable duplicate suppression.
11. [x] Created and end-to-end validated both no-retry weekday Scheduler jobs.
12. [x] Verified the live Dashboard, compatible image/revision, production data, error logs, backup controls, and external Job-failure alert.
13. [x] Recorded immutable image references and operating evidence without recording secret values.

### Open post-acceptance recovery exercise

14. [ ] Restore the accepted backup to a separate temporary Cloud SQL instance,
    validate it privately, then remove it. The 2026-08-21 attempt received HTTP
    403 before instance creation; no temporary resource or cost was left behind.

## 6. Launch definition of done

V1 operational launch is accepted with the isolated restore drill recorded as
an owner-approved exception. The accepted gates are:

- Owner-only HTTPS/IAP access is verified and anonymous access is denied
- Data survives service and Job restarts in PostgreSQL
- Both weekday schedules execute successfully without duplicate paid runs
- Dashboard shows messages, metrics, topics, anomalies, and full run history
- Every run is traceable through versions, counts, errors, and external IDs
- Secrets are absent from Git, images, logs, screenshots, and client JavaScript
- Budget alerts, structured logs, backups, PITR, and deletion protection are verified
- Backup creation, PITR configuration, and application/Job rollback procedures have evidence; the isolated restore drill remains an explicit open recovery gate
- The deployed image digests and configuration manifest are recorded
- The runbook reflects the actual resources and operating procedure

## 7. Work after first launch

Priority order after a stable observation period:

1. Expand the sentiment benchmark to at least 150 human-reviewed examples.
2. Evaluate topics and representative ranking on real messages.
3. Calibrate anomaly thresholds with twice-daily history.
4. Observe external failure-alert and application-email delivery, and tune notification signal after enough production history exists.
5. Retrieve actual Apify spend where supported and show it in run history.
6. Decide whether raw snapshots require durable cloud archival.
7. Add verified IAP identity propagation, CSRF protection, distributed idempotency, and Job dispatch before unlocking manual collection.
8. Consider more symbols or sources only after TSLA reliability and cost are understood.

## 8. Change-control rules

- No paid or state-changing cloud action without explicit owner approval.
- No automatic retry around paid collection in the first release.
- No public Dashboard access.
- No secret values in repository files or documentation.
- No mutable image tags in deployment artifacts.
- No schedule creation before an unscheduled Job succeeds.
- Update README, this plan, project history, and runbook when launch status changes.

---

# 中文

## 1. 产品结果

StockPulse 将成为一个私有、可解释的 TSLA 投资者情绪监测产品，每个工作日在 Google Cloud 上运行两次。Dashboard 必须展示投资者正在讨论什么、当前情绪与历史相比如何、变化是否异常，以及哪些消息和话题能够解释变化。

本产品不预测股价、不进行交易，也不构成投资建议。

## 2. 交付状态

| 阶段 | 成果 | 状态 |
|---|---|---|
| 1. 基础 | 成本受控采集、校验、去重、本地历史、情绪分析、CI | 已完成 |
| 2. 持久数据 | 运行历史、指标、迁移和仓库契约 | 已完成 |
| 3. 分析 | 基准、固定情绪模型、话题和代表消息 | 工程完成；质量扩展仍需进行 |
| 4. 异常检测 | 历史基线、话题变化、解释和重放安全 | 工程完成；生产校准仍需进行 |
| 5. 产品 API | 读取接口、筛选、分页和受保护操作 | 读取完成；浏览器写操作锁定 |
| 6. Dashboard | 响应式概览、趋势、消息和运行历史 | 首个只读版本已完成 |
| 7. 云端准备 | PostgreSQL、容器、流水线、预检和部署契约 | 已完成并通过 CI |
| 8. Google Cloud 上线 | 真实资源、迁移决策、IAP、计划任务和运维 | **V1 已验收；独立恢复演练暂缓** |
| 9. 上线后加固 | 观察、阈值校准、提醒和操作解锁 | 进行中：外部失败告警已上线；校准和操作解锁仍待完成 |

## 3. 首个版本的用户体验

所有者使用批准的 Google 账号登录一个私有 HTTPS Dashboard。页面提供：

- 最新数据时间、运行状态、情绪分数、讨论量、置信度和异常状态
- Bullish/Neutral/Bearish 分布与历史图表
- 当前和历史话题驱动因素
- 可搜索、筛选的原始消息历史
- 完整运行历史、处理计数、版本、错误、重试和外部 ID
- 清晰的空数据、加载、错误和就绪状态

手动采集继续显示为锁定。首个生产系统由两个工作日 Scheduler 任务运行。

## 4. 已批准的上线边界

| 决策 | 首个版本 |
|---|---|
| 区域 | `us-west1` |
| 访问 | Cloud Run 直接使用 IAP；仅允许所有者 Google 账号 |
| Web 服务 | 最小 0、最大 1 个实例；1 CPU；内存从 512 MiB 开始测量 |
| 流水线 | 独立固定模型 Cloud Run Job；单任务、不重试、初始超时 15 分钟 |
| 数据库 | Cloud SQL PostgreSQL 17、`db-f1-micro`、单区、非高可用 |
| 时间 | 工作日 `America/New_York` 09:15 与 18:00 |
| 恢复 | 每日备份、7 天 PITR、删除保护、成功的按需备份；独立恢复演练暂缓 |
| 预算 | 每月 20 美元，在 50%、80%、100% 提醒 |
| 赠金 | 只有控制台确认资格后才使用 Welcome Credit |
| 手动操作 | 身份、CSRF、任务触发和分布式幂等完成前保持禁用 |

## 5. 准确的下一步

### 已完成的生产基础设施

1. [x] 已在 `uw.edu` 组织下创建 `stockpulse-production`，关联 Billing 和 300 美元试用额度。
2. [x] 已配置 20 美元预算提醒、启用必要 API，并创建服务、流水线和 Scheduler 服务账号。
3. [x] 已在 `us-west1` 创建 `stockpulse` Artifact Registry 仓库。
4. [x] 已创建 Cloud SQL PostgreSQL 17、应用数据库、最小权限角色/用户，并启用备份、PITR 和删除保护。
5. [x] 已创建并按使用者范围授权数据库和 Apify Secret。
6. [x] 已构建并部署 Dashboard 镜像，配置 Cloud SQL、生产运行环境和直接 IAP，并验证 UI 已上线。
7. [x] 已关闭历史迁移门槛：未找到本地 SQLite 快照，因此跳过迁移，且不制造占位历史数据。

### 已完成的 V1 上线与验证

8. [x] 已从 `containers/job.Dockerfile` 构建 Pipeline v3，并通过不可变摘要部署 Job。
9. [x] 已完成一次五条消息的有界运行，验证 PostgreSQL 写入、持久运行历史、日志、限制和成功退出。
10. [x] 已验证每日摘要、异常 TEST、失败 TEST Gmail 投递和持久化去重。
11. [x] 已创建并端到端验证两个不自动重试的工作日 Scheduler。
12. [x] 已验证线上 Dashboard、兼容镜像与 revision、生产数据、错误日志、备份控制和外部 Job 失败告警。
13. [x] 已记录不可变镜像引用和运维证据，未记录任何 Secret 值。

### 验收后的开放恢复演练

14. [ ] 把验收备份恢复到独立临时 Cloud SQL 实例，私下验证后删除。
    2026-08-21 的尝试在创建实例前收到 HTTP 403，没有留下临时资源或费用。

## 6. 上线完成标准

V1 运维上线已在“独立恢复演练明确例外”的前提下通过验收。已通过的门槛为：

- 已验证仅所有者可通过 HTTPS/IAP 访问，匿名访问被拒绝
- 数据存储于 PostgreSQL，并在服务与 Job 重启后保留
- 两个工作日计划成功执行，且不会重复触发付费采集
- Dashboard 显示消息、指标、话题、异常和完整运行历史
- 每次运行均能通过版本、计数、错误和外部 ID 追踪
- Git、镜像、日志、截图和客户端 JavaScript 中均无 Secret
- 已验证预算提醒、结构化日志、备份、PITR 和删除保护
- 已验证备份创建、PITR 配置及应用/Job 回滚流程；独立恢复演练仍是明确开放的恢复门槛
- 已记录部署镜像摘要和配置 manifest
- 运行手册准确反映真实资源与操作方法

## 7. 首次上线后的工作

稳定观察一段时间后，按以下顺序推进：

1. 把情绪基准扩展到至少 150 条人工复核样本。
2. 使用真实消息评估话题和代表消息排序。
3. 使用每日两次的真实历史校准异常阈值。
4. 持续观察外部失败告警和应用邮件投递，并在积累足够生产历史后调整通知信号。
5. 在支持的情况下获取 Apify 实际支出并显示在运行历史。
6. 决定原始快照是否需要云端长期归档。
7. 在解锁手动采集前，实现 IAP 身份传递、CSRF、分布式幂等和 Job 调度。
8. 只有充分理解 TSLA 的可靠性与成本后，才考虑更多股票或数据源。

## 8. 变更控制规则

- 未经所有者明确批准，不执行付费或改变云端状态的操作。
- 首版付费采集不自动重试。
- Dashboard 不允许公开访问。
- 仓库文件和文档不保存真实 Secret。
- 部署文件不允许可变镜像 Tag。
- 未验证一次无计划 Job 成功前，不创建定时任务。
- 上线状态变化时，同时更新 README、本计划、项目历程和运行手册。
