# StockPulse Project History / StockPulse 项目历程

[English](#english) · [简体中文](#简体中文)

> Snapshot: 2026-08-21
>
> Repository: [AndyChen227/StockPulse---V2](https://github.com/AndyChen227/StockPulse---V2)
>
> Scope: merged work through pull request #34 plus V1 production acceptance and operational follow-up records
>
> Cloud state: V1 Dashboard, Pipeline v3, Gmail notifications, both weekday Scheduler triggers, external failure alert, and backup controls live

This is the durable engineering record for StockPulse. It separates completed implementation, validation evidence, approved decisions, and remaining work. The English record appears first; the complete Chinese record follows.

---

# English

## 1. Why the project exists

StockPulse began as a small TSLA sentiment experiment and has developed into an operational cloud monitoring product. Its purpose is to collect bounded Stocktwits discussions, preserve a trustworthy history, analyze sentiment and topics reproducibly, detect unusual changes, and make the evidence understandable in a polished Dashboard.

The product is deliberately narrow: one symbol, one discussion source, controlled collection frequency, no trading, and no price prediction. This keeps operating cost, evaluation scope, and failure behavior understandable before expansion.

## 2. Current milestone

The repository has completed the V1 engineering and production rollout path:

- The local end-to-end application works with SQLite.
- The Dashboard and read API work against stored history.
- PostgreSQL production reads, writes, migrations, and SQLite import are implemented.
- Service and AI pipeline containers are validated in CI.
- Production configuration fails safely when incomplete.
- Deployment templates are rendered offline and reject mutable or unsafe inputs.
- Two weekday schedules are encoded for 09:15 and 18:00 Eastern.
- The project, cost controls, IAM, secrets, Artifact Registry, and Cloud SQL foundation are provisioned in `us-west1`.
- The Dashboard is live on Cloud Run with direct IAP and managed Cloud SQL connectivity.
- Historical SQLite migration was skipped because no local snapshot was found.
- The bounded pipeline Job is deployed and its first production execution
  completed successfully with five analyzed messages.
- Daily summary and detailed anomaly/failure Gmail delivery is production
  validated with durable duplicate suppression.
- Both no-retry weekday Scheduler triggers are live and end-to-end validated.
- Cloud Monitoring provides an independent email alert for Job errors that
  occur before application-level failure mail can be sent.
- Daily backups, seven-day PITR, deletion protection, and a successful
  on-demand acceptance backup are active.

The project has reached **V1 operational acceptance**. The isolated Cloud SQL
restore drill is the documented exception: the 2026-08-21 attempt received HTTP
403 before instance creation and is explicitly deferred.

## 3. Milestone timeline

| PR | Milestone | Delivered outcome |
|---:|---|---|
| [#1](https://github.com/AndyChen227/StockPulse---V2/pull/1) | Python foundation | Package layout, configuration, SQLite storage, CLI foundation, tests, and Python CI |
| [#2](https://github.com/AndyChen227/StockPulse---V2/pull/2) | Collection | Cost-capped Apify collection, validation, raw snapshots, deduplication, and explicit paid-action boundary |
| [#3](https://github.com/AndyChen227/StockPulse---V2/pull/3) | Sentiment | Local AI sentiment adapter, confidence metadata, versioned analysis, and safe reanalysis |
| [#4](https://github.com/AndyChen227/StockPulse---V2/pull/4) | Product direction | Dashboard requirements, Google Cloud destination, staged delivery plan, and documentation policy |
| [#5](https://github.com/AndyChen227/StockPulse---V2/pull/5) | Operational history | Durable collection/analysis run records and daily metrics |
| [#6](https://github.com/AndyChen227/StockPulse---V2/pull/6) | Storage contracts | Schema versions, stricter validation, retry relationships, partial status, external IDs, and repository abstraction |
| [#7](https://github.com/AndyChen227/StockPulse---V2/pull/7) | Evaluation baseline | Reproducible 36-example finance-direction benchmark and baseline metrics |
| [#8](https://github.com/AndyChen227/StockPulse---V2/pull/8) | Model comparison | FinBERT candidate comparison; retained the pinned Twitter-RoBERTa adapter based on tracked results |
| [#9](https://github.com/AndyChen227/StockPulse---V2/pull/9) | Topic analysis | Versioned, explainable, multi-label TSLA taxonomy and representative-message ranking |
| [#10](https://github.com/AndyChen227/StockPulse---V2/pull/10) | Topic history | Daily topic counts, sentiment breakdowns, strength, confidence, and date filtering |
| [#11](https://github.com/AndyChen227/StockPulse---V2/pull/11) | Anomaly baseline | Versioned 28-day rolling-median detector with minimum-history and minimum-volume safeguards |
| [#12](https://github.com/AndyChen227/StockPulse---V2/pull/12) | Topic-shift evidence | Added topic-share changes and representative evidence to anomaly explanations |
| [#13](https://github.com/AndyChen227/StockPulse---V2/pull/13) | Dashboard API | Health, readiness, overview, metrics, topics, anomalies, and run-history read endpoints |
| [#14](https://github.com/AndyChen227/StockPulse---V2/pull/14) | Message explorer API | Cursor pagination, search, filters, source links, AI metadata, and topic assignments |
| [#15](https://github.com/AndyChen227/StockPulse---V2/pull/15) | API completion | Stable envelopes, validation errors, run detail, pagination boundaries, and read-contract tests |
| [#16](https://github.com/AndyChen227/StockPulse---V2/pull/16) | Initial Dashboard | Responsive overview, trends, messages, run history, and explicit loading/empty/error states |
| [#17](https://github.com/AndyChen227/StockPulse---V2/pull/17) | Visual refinement | Wider responsive layout, improved visual hierarchy, updated color system, and motion with reduced-motion support |
| [#18](https://github.com/AndyChen227/StockPulse---V2/pull/18) | Service container | Cloud Run-compatible Dashboard/API image, health behavior, non-root runtime, and CI smoke test |
| [#19](https://github.com/AndyChen227/StockPulse---V2/pull/19) | PostgreSQL foundation | Cloud SQL choice, secret configuration, bounded pool, and ordered PostgreSQL schema migrations |
| [#20](https://github.com/AndyChen227/StockPulse---V2/pull/20) | PostgreSQL reads | Dashboard repository reads implemented for PostgreSQL with shared behavior contracts |
| [#21](https://github.com/AndyChen227/StockPulse---V2/pull/21) | PostgreSQL writes | Transactional message, run, analysis, topic, metric, and anomaly writes |
| [#22](https://github.com/AndyChen227/StockPulse---V2/pull/22) | Production image | Service container includes the PostgreSQL runtime and validates production database configuration |
| [#23](https://github.com/AndyChen227/StockPulse---V2/pull/23) | Data migration | Previewable, idempotent SQLite-to-PostgreSQL migration with retry links and source-key verification |
| [#24](https://github.com/AndyChen227/StockPulse---V2/pull/24) | Guarded actions | Bounded collection request contract, confirmation semantics, idempotency boundary, and disabled-by-default behavior |
| [#25](https://github.com/AndyChen227/StockPulse---V2/pull/25) | Launch architecture | Pre-cloud runbook covering region, IAP, IAM, Cloud SQL, cost, backups, rollout, rollback, and free-credit cautions |
| [#26](https://github.com/AndyChen227/StockPulse---V2/pull/26) | Daily pipeline Job | One idempotent collect-to-anomaly command and separate pinned-model Job image |
| [#27](https://github.com/AndyChen227/StockPulse---V2/pull/27) | Production preflight | Service/Job configuration validation with credential-safe diagnostics and local SQLite compatibility |
| [#28](https://github.com/AndyChen227/StockPulse---V2/pull/28) | Deployment contracts | Reviewed Cloud Run service/Job templates, offline renderer, immutable digests, numeric secrets, checksums, and approval gate |
| [#29](https://github.com/AndyChen227/StockPulse---V2/pull/29) | Twice-daily schedule | Separate no-retry weekday Scheduler contracts for 09:15 and 18:00 `America/New_York` |
| [#30](https://github.com/AndyChen227/StockPulse---V2/pull/30) | Documentation refresh | Rebuilt the English-first bilingual README, project plan, history, and documentation index |
| [#31](https://github.com/AndyChen227/StockPulse---V2/pull/31) | Repository navigation | Added the repository file map and local directory guides; the later layout correction removes the conflicting `.github/README.md` |
| [#32](https://github.com/AndyChen227/StockPulse---V2/pull/32) | Repository organization | Restored the product README, grouped configuration and container files, updated every runtime reference, and added layout regression tests |
| [#33](https://github.com/AndyChen227/StockPulse---V2/pull/33) | Documentation organization | Organized documentation by product, architecture, analysis, operations, reference, and decision domains |
| [#34](https://github.com/AndyChen227/StockPulse---V2/pull/34) | Dashboard redesign | Delivered the TSLA telemetry-inspired production Dashboard visual system |
| [`48bfb15`](https://github.com/AndyChen227/StockPulse---V2/commit/48bfb15) | Production deployment record | Recorded the live Dashboard, deployed Google Cloud foundation, skipped SQLite migration, and remaining Job/Scheduler work |
| [`762d487`](https://github.com/AndyChen227/StockPulse---V2/commit/762d487) | V1 production acceptance | Recorded Pipeline v3, Gmail and Scheduler validation, compatible Dashboard release, immutable artifacts, backup evidence, and the transient readiness incident |
| [`e3986e9`](https://github.com/AndyChen227/StockPulse---V2/commit/e3986e9) | Operational follow-up | Recorded the independent Cloud Monitoring failure alert and the explicitly deferred isolated restore drill |

## 4. End-to-end behavior today

### Local path that can run now

1. Load configuration and open/migrate SQLite.
2. Optionally start one explicitly requested, cost-capped Apify Actor run.
3. Validate records, canonicalize timestamps, reject invalid items, and deduplicate by `messageId`.
4. Store source messages and the operational run record.
5. Analyze records missing the current pinned sentiment version.
6. Assign versioned topics and representative-message scores.
7. Calculate daily sentiment, volume, confidence, and topic metrics.
8. Evaluate the date against the versioned historical anomaly baseline.
9. Read all stored results through the API and Dashboard.

The Dashboard alone is safe to open: page loads, refreshes, searches, and filters never invoke Apify.

### CI path that runs now

Each change is checked across five surfaces:

1. Python 3.11 tests
2. Python 3.12 tests
3. Dashboard service container build and smoke test
4. Pinned-model pipeline Job image build and model-load smoke test
5. PostgreSQL integration behavior

After the bilingual-documentation regression check was added, the 2026-08-21
local baseline ran 145 tests: 137 passed and 8 PostgreSQL integration tests were
intentionally skipped locally and are executed with PostgreSQL 17 in CI.

### Cloud path in production

The production project and supporting resources are live. The Dashboard and
Pipeline v3 are pinned by immutable image digests, Cloud SQL is the system of
record, Gmail notifications and both Scheduler triggers are validated, and an
independent Cloud Monitoring policy covers Cloud Run Job errors. Secret values
remain outside Git. No SQLite production import occurred because no local
source snapshot was available.

## 5. Major engineering decisions

### Cost is a product requirement

- TSLA only in the first release
- Five-item default collection cap
- 60-second Actor timeout
- USD 0.05 recorded run ceiling
- No automatic retry around paid collection
- Cloud Run service scales to zero
- One maximum service instance initially
- Small, single-zone PostgreSQL instance initially
- USD 20 monthly alert budget with three thresholds

### Reproducibility is explicit

Sentiment, topics, and anomaly outputs carry version metadata. The model repository revision and confidence threshold are pinned into the analysis version so a result can be explained and safely recomputed.

### History is part of the product

Runs preserve status, start/end time, limits, counts, bounded errors, retry relationships, and Apify identifiers. Message and metric history is not treated as a temporary by-product of the Dashboard.

### Cloud service and batch work are separated

The lightweight web service does not load the AI model. A separate Cloud Run Job image contains the pinned model runtime and executes the bounded pipeline. The service receives only its database secret; the Job receives database and Apify secrets.

### Destructive and paid actions fail closed

The browser collection control is visible but locked. Production configuration rejects incomplete settings, mutable image tags, unversioned secrets, mismatched projects, and unapproved rendering.

## 6. Validation evidence

| Area | Evidence |
|---|---|
| Sentiment | 36 balanced synthetic finance-direction examples; 88.9% accuracy and 89.2% macro F1 for the retained baseline; provisional, not production acceptance |
| Storage | Ordered SQLite and PostgreSQL migrations, backend contract tests, idempotent import, and source-key verification |
| API | Response models, stable error envelope, filters, pagination, readiness, and action-boundary tests |
| UI | Desktop/tablet/mobile layout, keyboard focus, reduced-motion handling, and explicit non-happy states |
| Containers | Service health smoke test and pinned-model Job load/inference smoke test |
| Deployment | Offline rendering, manifest checksums, immutable digests, numeric secret versions, region/project/schedule validation |
| CI | Python 3.11, Python 3.12, service image, Job image, and PostgreSQL checks |

## 7. Known limitations and technical debt

1. The sentiment benchmark is small and synthetic. Expand it to at least 150 human-reviewed, Stocktwits-relevant examples with a held-out split.
2. Topic taxonomy and representative ranking need a manually labeled real-message evaluation.
3. Anomaly thresholds need calibration after enough real twice-daily history exists.
4. The configured Apify cost ceiling is recorded, but actual settled spend is not retrieved into run history.
5. Raw JSON snapshots are local artifacts; durable cloud archival is not yet specified.
6. Browser-triggered collection still needs verified IAP identity, CSRF protection, distributed idempotency, and a Cloud Run Jobs dispatcher.
7. Notification delivery now needs ongoing observation and signal tuning as
   real twice-daily history accumulates.
8. The initial shared-core Cloud SQL plan has no SLA and is intentionally non-HA.
9. The isolated Cloud SQL restore drill remains open after an HTTP 403 response
   before target-instance creation; rollback procedures and backup/PITR controls
   are documented, but a restored instance still needs private validation.
10. Historical price correlation, additional symbols, and additional social sources are outside V1 scope.

## 8. Approved cloud plan

- Region: `us-west1`
- Authentication: direct Cloud Run IAP, owner account only
- Service: request billing, minimum 0, maximum 1
- Database: Cloud SQL PostgreSQL 17, `db-f1-micro`, single-zone, non-HA
- Recovery: daily backups, seven-day PITR, deletion protection, successful on-demand backup; isolated restore drill deferred
- Scheduling: weekdays 09:15 and 18:00 Eastern, two jobs, no retries
- Budget: USD 20 monthly alerts at 50%, 80%, and 100%
- Credits: USD 300 Google Cloud trial credit confirmed and attached
- First release: manual Dashboard collection remains locked

## 9. Post-V1 follow-up

1. Complete and validate an isolated restore to a temporary Cloud SQL instance.
2. Calibrate anomaly and notification thresholds with representative history.
3. Expand human-reviewed sentiment and topic evaluation data.
4. Decide whether raw Apify snapshots require durable cloud archival.
5. Keep manual Dashboard collection locked until IAP identity propagation,
   CSRF protection, distributed idempotency, and Job dispatch are complete.

---

# 简体中文

## 1. 项目为什么存在

StockPulse 最初是一个小型 TSLA 情绪实验，现在已经发展为正在生产环境运行的
云端监测产品。它的目标是：以明确上限采集 Stocktwits 讨论，可靠保存历史，
使用可复现的方式分析情绪和话题，检测异常变化，并在成熟的 Dashboard 中展示
可理解的证据。

产品范围有意保持克制：一个股票代码、一个讨论来源、受控的采集频率、不交易、不预测股价。这样在扩大范围前，成本、评估范围和故障行为都可以被充分理解。

## 2. 当前里程碑

仓库已经完成 V1 工程与生产上线流程：

- 使用 SQLite 的本地端到端应用可以运行。
- Dashboard 和只读 API 可以读取完整历史。
- PostgreSQL 生产读写、模式迁移和 SQLite 导入已经实现。
- Web 服务与 AI 流水线容器均在 CI 中验证。
- 生产配置不完整时会安全地提前失败。
- 部署模板完全离线渲染，并拒绝可变或不安全的输入。
- 已编码工作日美东 09:15 与 18:00 两个时间计划。
- 项目、成本控制、IAM、Secret、Artifact Registry 和 Cloud SQL 基础设施已在 `us-west1` 配置完成。
- Dashboard 已在 Cloud Run 上线，并配置直接 IAP 和托管 Cloud SQL 连接。
- 因未找到本地快照，历史 SQLite 迁移已跳过。
- Pipeline v3 已使用不可变摘要部署，并完成一次五条消息的生产运行。
- 每日摘要、异常 TEST、失败 TEST Gmail 通知和持久化去重已验证。
- 两个不自动重试的工作日 Scheduler 已完成端到端验证。
- Cloud Monitoring 已提供独立的 Job 错误邮件告警。
- 每日备份、7 天 PITR、删除保护和成功的按需验收备份均已启用。

项目已经达到 **V1 运维验收**。唯一记录的例外是 Cloud SQL 独立恢复演练：
2026-08-21 的尝试在创建实例前收到 HTTP 403，因此明确暂缓。

## 3. 里程碑时间线

| PR | 里程碑 | 交付成果 |
|---:|---|---|
| [#1](https://github.com/AndyChen227/StockPulse---V2/pull/1) | Python 基础 | 包结构、配置、SQLite、CLI、测试和 Python CI |
| [#2](https://github.com/AndyChen227/StockPulse---V2/pull/2) | 数据采集 | 带成本上限的 Apify 采集、校验、原始快照、去重和明确付费边界 |
| [#3](https://github.com/AndyChen227/StockPulse---V2/pull/3) | 情绪分析 | 本地 AI 适配器、置信度、版本化分析和安全重分析 |
| [#4](https://github.com/AndyChen227/StockPulse---V2/pull/4) | 产品方向 | Dashboard 要求、Google Cloud 目标、分阶段计划和文档规则 |
| [#5](https://github.com/AndyChen227/StockPulse---V2/pull/5) | 运行历史 | 持久化采集/分析运行记录与每日指标 |
| [#6](https://github.com/AndyChen227/StockPulse---V2/pull/6) | 存储契约 | 模式版本、严格校验、重试关系、部分成功状态、外部 ID 和仓库抽象 |
| [#7](https://github.com/AndyChen227/StockPulse---V2/pull/7) | 评估基线 | 可复现的 36 条金融方向基准和基线指标 |
| [#8](https://github.com/AndyChen227/StockPulse---V2/pull/8) | 模型对比 | 对比 FinBERT；依据记录结果保留固定版本 Twitter-RoBERTa |
| [#9](https://github.com/AndyChen227/StockPulse---V2/pull/9) | 话题分析 | 版本化、可解释、多标签 TSLA 话题体系和代表消息排序 |
| [#10](https://github.com/AndyChen227/StockPulse---V2/pull/10) | 话题历史 | 每日话题数量、情绪分布、强度、置信度和日期筛选 |
| [#11](https://github.com/AndyChen227/StockPulse---V2/pull/11) | 异常基线 | 28 天滚动中位数检测器，包含最少历史和最少讨论量保护 |
| [#12](https://github.com/AndyChen227/StockPulse---V2/pull/12) | 话题变化证据 | 在异常解释中加入话题占比变化和代表消息证据 |
| [#13](https://github.com/AndyChen227/StockPulse---V2/pull/13) | Dashboard API | 健康、就绪、概览、指标、话题、异常和运行历史接口 |
| [#14](https://github.com/AndyChen227/StockPulse---V2/pull/14) | 消息浏览 API | 游标分页、搜索、筛选、来源链接、AI 元数据和话题分配 |
| [#15](https://github.com/AndyChen227/StockPulse---V2/pull/15) | API 完成 | 稳定封装、校验错误、运行详情、分页边界和契约测试 |
| [#16](https://github.com/AndyChen227/StockPulse---V2/pull/16) | 初始 Dashboard | 响应式概览、趋势、消息、运行历史及加载/空数据/错误状态 |
| [#17](https://github.com/AndyChen227/StockPulse---V2/pull/17) | 视觉优化 | 更宽的响应式布局、视觉层次、新配色和兼容减少动态效果的动画 |
| [#18](https://github.com/AndyChen227/StockPulse---V2/pull/18) | 服务容器 | Cloud Run 兼容镜像、健康行为、非 root 运行和 CI 冒烟测试 |
| [#19](https://github.com/AndyChen227/StockPulse---V2/pull/19) | PostgreSQL 基础 | Cloud SQL 决策、Secret 配置、受控连接池和有序模式迁移 |
| [#20](https://github.com/AndyChen227/StockPulse---V2/pull/20) | PostgreSQL 读取 | Dashboard 所需 PostgreSQL 读取及共享行为契约 |
| [#21](https://github.com/AndyChen227/StockPulse---V2/pull/21) | PostgreSQL 写入 | 消息、运行、分析、话题、指标和异常的事务写入 |
| [#22](https://github.com/AndyChen227/StockPulse---V2/pull/22) | 生产镜像 | 服务容器加入 PostgreSQL 运行时并验证生产数据库配置 |
| [#23](https://github.com/AndyChen227/StockPulse---V2/pull/23) | 数据迁移 | 可预览、幂等的 SQLite 到 PostgreSQL 迁移，恢复重试关系并校验源键 |
| [#24](https://github.com/AndyChen227/StockPulse---V2/pull/24) | 受保护操作 | 有界采集请求、确认语义、幂等边界和默认禁用行为 |
| [#25](https://github.com/AndyChen227/StockPulse---V2/pull/25) | 上线架构 | 区域、IAP、IAM、Cloud SQL、成本、备份、发布、回滚和赠金额度说明 |
| [#26](https://github.com/AndyChen227/StockPulse---V2/pull/26) | 每日流水线 Job | 从采集到异常检测的幂等命令和独立固定模型 Job 镜像 |
| [#27](https://github.com/AndyChen227/StockPulse---V2/pull/27) | 生产预检 | 服务/Job 配置校验、安全诊断，并保持本地 SQLite 兼容 |
| [#28](https://github.com/AndyChen227/StockPulse---V2/pull/28) | 部署契约 | Cloud Run 模板、离线渲染、不可变摘要、数字 Secret、校验和与批准门槛 |
| [#29](https://github.com/AndyChen227/StockPulse---V2/pull/29) | 每日两次计划 | 工作日美东 09:15 与 18:00 两个独立、不重试的 Scheduler 契约 |
| [#30](https://github.com/AndyChen227/StockPulse---V2/pull/30) | 文档更新 | 重建英语在前的双语 README、项目计划、项目历程和文档导航 |
| [#31](https://github.com/AndyChen227/StockPulse---V2/pull/31) | 仓库导航 | 增加文件地图和目录说明；后续布局修复会删除冲突的 `.github/README.md` |
| [#32](https://github.com/AndyChen227/StockPulse---V2/pull/32) | 仓库整理 | 恢复产品 README，归类配置与容器文件，更新所有运行引用，并加入布局回归测试 |
| [#33](https://github.com/AndyChen227/StockPulse---V2/pull/33) | 文档整理 | 按产品、架构、分析、运维、参考和决策领域整理文档 |
| [#34](https://github.com/AndyChen227/StockPulse---V2/pull/34) | Dashboard 重构 | 交付 TSLA 遥测风格的生产 Dashboard 视觉系统 |
| [`48bfb15`](https://github.com/AndyChen227/StockPulse---V2/commit/48bfb15) | 生产部署记录 | 记录已上线 Dashboard、Google Cloud 基础设施、跳过的 SQLite 迁移和待完成的 Job/Scheduler |
| [`762d487`](https://github.com/AndyChen227/StockPulse---V2/commit/762d487) | V1 生产验收 | 记录 Pipeline v3、Gmail 与 Scheduler 验证、兼容 Dashboard 版本、不可变制品、备份证据和临时 readiness 事故 |
| [`e3986e9`](https://github.com/AndyChen227/StockPulse---V2/commit/e3986e9) | 运维收尾 | 记录独立 Cloud Monitoring 失败告警和明确暂缓的独立恢复演练 |

## 4. 当前端到端能力

### 现在可以运行的本地流程

1. 加载配置并打开或迁移 SQLite。
2. 在用户明确要求时，启动一次带成本上限的 Apify Actor。
3. 校验记录、统一 UTC 时间、拒绝无效数据并按 `messageId` 去重。
4. 保存原始消息和运行记录。
5. 分析尚未使用当前固定版本处理的记录。
6. 分配版本化话题并计算代表消息分数。
7. 计算每日情绪、讨论量、置信度和话题指标。
8. 使用版本化历史异常基线评估当天数据。
9. 通过 API 和 Dashboard 读取全部结果。

单独打开 Dashboard 是安全的：加载页面、刷新、搜索和筛选都不会调用 Apify。

### 现在可以运行的 CI 流程

每次变更检查五个方面：Python 3.11、Python 3.12、Dashboard 服务容器、固定模型流水线 Job 容器，以及 PostgreSQL 集成行为。

增加双语文档回归检查后，2026-08-21 的本地基线共运行 145 项测试：137 项通过，
8 项 PostgreSQL 集成测试按设计在本地跳过，并由 CI 使用 PostgreSQL 17 执行。

### 已投入生产的云端流程

生产项目及配套资源已经上线。Dashboard 与 Pipeline v3 均由不可变镜像摘要固定，
Cloud SQL 是线上事实来源，Gmail 通知和两个 Scheduler 已验证，独立 Cloud Monitoring
策略覆盖 Cloud Run Job 错误。Secret 值仍保留在 Git 之外。因为没有可用的本地源快照，
本次没有执行 SQLite 生产导入。

## 5. 主要工程决策

### 成本是产品要求

首版仅 TSLA、默认最多 5 条、Actor 超时 60 秒、每次记录上限 0.05 美元、
付费采集不自动重试、服务缩容到零、初期最多一个实例、使用小型单区数据库，
并设置每月 20 美元预算提醒。

### 结果必须可复现

情绪、话题和异常均保留版本；模型 revision、置信度阈值和检测参数都进入分析
版本，避免相同名称在不同时间代表不同逻辑。

### 历史本身就是产品

运行状态、时间、限制、计数、错误、重试关系和 Apify ID 都会持久化。历史不仅
用于图表，也用于故障诊断、重复预防和异常重放。

### Web 与批处理分离

轻量 Web 服务不加载 AI 模型；独立 Job 镜像执行完整流水线，并使用更少、更
明确的 Secret 权限。读取 Dashboard 与付费采集因而保持不同风险边界。

### 破坏性或付费行为默认关闭

浏览器采集按钮保持锁定；生产配置拒绝不完整设置、可变镜像、无版本 Secret、
项目不匹配和未批准渲染。涉及费用、数据或基础设施的行为都需要显式入口。

## 6. 验证证据

| 领域 | 证据 |
|---|---|
| 情绪 | 36 条平衡的合成金融方向样本；保留基线准确率 88.9%、Macro F1 89.2%；属于临时基线，不是生产验收 |
| 存储 | SQLite/PostgreSQL 有序迁移、后端契约测试、幂等导入和源键校验 |
| API | 响应模型、稳定错误格式、筛选、分页、就绪和操作边界测试 |
| UI | 桌面/平板/手机布局、键盘焦点、减少动态效果支持和完整非正常状态 |
| 容器 | 服务健康冒烟测试，以及固定模型 Job 加载/推理冒烟测试 |
| 部署 | 离线渲染、manifest 校验和、不可变摘要、数字 Secret 版本和区域/项目/时间校验 |
| CI | Python 3.11、Python 3.12、服务镜像、Job 镜像和 PostgreSQL 检查 |

## 7. 已知限制与技术债

1. 情绪基准较小且为合成数据，需要扩展到至少 150 条人工复核、贴近 Stocktwits 的样本并保留测试集。
2. 话题体系和代表消息排序需要真实消息的人工标注评估。
3. 异常阈值需要在积累足够的每日两次真实历史后校准。
4. 当前记录配置的 Apify 成本上限，但尚未回收实际结算成本。
5. 原始 JSON 快照目前是本地文件，云端长期归档尚未定义。
6. 浏览器采集仍需要 IAP 身份验证、CSRF、防重复执行和 Cloud Run Jobs 调度器。
7. 通知投递已经实现，后续需要随每日两次真实历史积累观察并调整信号。
8. 首版共享核心 Cloud SQL 没有 SLA，并且有意选择非高可用。
9. Cloud SQL 独立恢复演练在创建目标实例前收到 HTTP 403，仍需完成私下恢复验证；
   回滚流程和备份/PITR 控制已经记录。
10. 股价相关性、更多股票和更多社交来源不属于 V1。

## 8. 已批准的云端方案

- 区域：`us-west1`
- 认证：Cloud Run 直接使用 IAP，仅允许所有者账号
- 服务：按请求计费，最小实例 0、最大实例 1
- 数据库：Cloud SQL PostgreSQL 17、`db-f1-micro`、单区、非高可用
- 恢复：每日备份、7 天时间点恢复、删除保护、成功的按需备份；独立恢复演练暂缓
- 时间：工作日美东 09:15 与 18:00，两个任务、不重试
- 预算：每月 20 美元，在 50%、80%、100% 提醒
- 赠金：已确认并关联 300 美元 Google Cloud 试用额度
- 首版：Dashboard 手动采集继续锁定

## 9. V1 后续工作

1. 完成并验证恢复到独立临时 Cloud SQL 实例的演练。
2. 使用有代表性的历史校准异常和通知阈值。
3. 扩大人工复核的情绪与话题评估数据。
4. 决定 Apify 原始快照是否需要云端长期归档。
5. 在 IAP 身份传递、CSRF、分布式幂等和 Job 调度完成前，继续锁定 Dashboard 手动采集。
