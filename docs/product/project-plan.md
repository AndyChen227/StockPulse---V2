# StockPulse Product and Delivery Plan / StockPulse 产品与交付计划

> Last updated: 2026-08-18
>
> Status: pre-cloud engineering complete; Google Cloud deployment pending
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
| 8. Google Cloud launch | Real resources, migration, IAP, schedule, operations | **Next milestone** |
| 9. Post-launch hardening | Observation, threshold calibration, alerts, action enablement | Pending after stable launch |

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
| Recovery | Daily backup, seven-day PITR, deletion protection, restore drill |
| Budget | USD 20 monthly alerts at 50%, 80%, and 100% |
| Credits | Use Welcome Credit only after console confirms eligibility |
| Manual actions | Disabled until identity, CSRF, dispatch, and distributed idempotency are complete |

## 5. Exact next steps

### Gate A — account and cost

1. Confirm Google Cloud Welcome Credit and billing-account eligibility.
2. Create a dedicated project and attach billing.
3. Create budget alerts before sustained resources.
4. Confirm a region-specific Pricing Calculator estimate.

### Gate B — identity and data

5. Enable only required APIs.
6. Create separate service, pipeline, and Scheduler service accounts.
7. Create database and Apify secrets with narrow version access.
8. Create Cloud SQL with the approved recovery controls.

### Gate C — release

9. Build service and Job images and record immutable digests.
10. Render and review the deployment bundle.
11. Deploy the private service and an unscheduled Job.
12. Run production preflight and database readiness.
13. Preview and execute the history migration if source data is approved.
14. Execute one bounded pipeline run and inspect all outputs.

### Gate D — automation and operations

15. Create both Scheduler jobs only after manual Job validation.
16. Verify IAP allow/deny behavior and the complete Dashboard.
17. Verify logs, budget notifications, backup restore, and rollback.
18. Record the production URL, resource inventory, image digests, and operating notes.

## 6. Launch definition of done

Launch is complete only when:

- Owner-only HTTPS/IAP access is verified and anonymous access is denied
- Data survives service and Job restarts in PostgreSQL
- Both weekday schedules execute successfully without duplicate paid runs
- Dashboard shows messages, metrics, topics, anomalies, and full run history
- Every run is traceable through versions, counts, errors, and external IDs
- Secrets are absent from Git, images, logs, screenshots, and client JavaScript
- Budget alerts, structured logs, backups, PITR, and deletion protection are verified
- A restore drill and a rollback exercise have evidence
- The deployed image digests and configuration manifest are recorded
- The runbook reflects the actual resources and operating procedure

## 7. Work after first launch

Priority order after a stable observation period:

1. Expand the sentiment benchmark to at least 150 human-reviewed examples.
2. Evaluate topics and representative ranking on real messages.
3. Calibrate anomaly thresholds with twice-daily history.
4. Add production anomaly notification delivery with duplicate suppression.
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
| 8. Google Cloud 上线 | 真实资源、迁移、IAP、计划任务和运维 | **下一里程碑** |
| 9. 上线后加固 | 观察、阈值校准、提醒和操作解锁 | 稳定上线后进行 |

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
| 恢复 | 每日备份、7 天 PITR、删除保护和恢复演练 |
| 预算 | 每月 20 美元，在 50%、80%、100% 提醒 |
| 赠金 | 只有控制台确认资格后才使用 Welcome Credit |
| 手动操作 | 身份、CSRF、任务触发和分布式幂等完成前保持禁用 |

## 5. 准确的下一步

### 阶段 A：账号与成本

1. 确认 Google Cloud Welcome Credit 和 Billing 账号资格。
2. 创建专用项目并关联 Billing。
3. 在创建持续资源前设置预算提醒。
4. 确认对应区域的价格计算器估算。

### 阶段 B：身份与数据

5. 只启用必要 API。
6. 分别创建服务、流水线和 Scheduler 服务账号。
7. 创建数据库和 Apify Secret，并严格限制版本访问权限。
8. 按已批准的恢复策略创建 Cloud SQL。

### 阶段 C：发布

9. 构建服务与 Job 镜像，记录不可变摘要。
10. 渲染并审查部署包。
11. 部署私有服务和暂不定时的 Job。
12. 执行生产预检与数据库就绪检查。
13. 如果源数据获得批准，预览并执行历史迁移。
14. 执行一次有界流水线，并检查全部结果。

### 阶段 D：自动化与运维

15. 只有手动 Job 验证成功后才创建两个 Scheduler 任务。
16. 验证 IAP 允许/拒绝行为和完整 Dashboard。
17. 验证日志、预算通知、备份恢复和回滚。
18. 记录生产 URL、资源清单、镜像摘要和运维说明。

## 6. 上线完成标准

只有以下全部成立，才能宣布上线完成：

- 已验证仅所有者可通过 HTTPS/IAP 访问，匿名访问被拒绝
- 数据存储于 PostgreSQL，并在服务与 Job 重启后保留
- 两个工作日计划成功执行，且不会重复触发付费采集
- Dashboard 显示消息、指标、话题、异常和完整运行历史
- 每次运行均能通过版本、计数、错误和外部 ID 追踪
- Git、镜像、日志、截图和客户端 JavaScript 中均无 Secret
- 已验证预算提醒、结构化日志、备份、PITR 和删除保护
- 恢复演练和回滚演练均有证据
- 已记录部署镜像摘要和配置 manifest
- 运行手册准确反映真实资源与操作方法

## 7. 首次上线后的工作

稳定观察一段时间后，按以下顺序推进：

1. 把情绪基准扩展到至少 150 条人工复核样本。
2. 使用真实消息评估话题和代表消息排序。
3. 使用每日两次的真实历史校准异常阈值。
4. 增加生产异常通知，并防止重复提醒。
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
