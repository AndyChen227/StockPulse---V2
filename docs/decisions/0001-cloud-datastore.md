# ADR 0001: Use Cloud SQL for PostgreSQL as the Production Datastore / 使用 Cloud SQL for PostgreSQL 作为生产数据存储

[English](#english) · [简体中文](#简体中文)

---

# English

- Status: Accepted and implemented in V1 production
- Date: 2026-08-16
- Scope: First Google Cloud release

> Implementation note — 2026-08-21: Cloud SQL for PostgreSQL 17 is live as the
> shared Dashboard and Pipeline v3 source of truth. Automated backups, seven-day
> PITR, deletion protection, and an on-demand acceptance backup are enabled. The
> isolated restore-to-new-instance drill is explicitly deferred after an HTTP
> 403 response before resource creation.

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

Firestore is serverless and can be attractive for a very small, fixed-key read
workload. Its billing model includes document operations, index-entry reads,
storage, networking, and optional recovery features, so any future comparison
must use the then-current official pricing rather than values copied into this
ADR ([Firestore billing](https://firebase.google.com/docs/firestore/pricing)).

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
- Google Cloud materially changes relevant pricing or product capabilities

---

# 简体中文

- 状态：已接受，并已在 V1 生产环境实现
- 日期：2026-08-16
- 范围：首次 Google Cloud 上线

> 实施记录（2026-08-21）：Cloud SQL for PostgreSQL 17 已成为 Dashboard 与
> Pipeline v3 共享的生产事实来源。自动备份、7 天 PITR、删除保护和一次按需
> 验收备份均已启用。独立恢复到新实例的演练在创建资源前收到 HTTP 403，因此
> 被明确暂缓。

## 背景

StockPulse 需要一个可由 Cloud Run Job 和 Cloud Run 服务共享的持久事实来源。
Cloud Run 可写容器文件系统不会在实例停止后持久保存，因此本地 SQLite 文件
不能作为生产数据库（见 [Cloud Run 容器运行契约](https://docs.cloud.google.com/run/docs/container-contract)）。

产品必须支持：

- 按 Stocktwits 消息 ID 进行幂等写入；
- 原子化的采集、分析、指标和运行状态更新；
- 日期范围图表与每日聚合；
- 结合日期、来源标签、AI 标签、置信度、话题和分析版本的消息分页筛选；
- 消息、运行、指标、分析版本、话题和异常之间的关系；
- 模式迁移、备份、恢复测试和可审计运维历史；
- Cloud Run 服务与 Cloud Run Job 共同访问。

初始负载很小：每天一到两次 TSLA 采集和低流量认证 Dashboard。可预测行为与
迁移安全比极端横向扩展更重要。

## 决策

使用 **Cloud SQL for PostgreSQL** 作为生产事实来源。

保留 SQLite 作为零成本本地开发和测试后端。在云迁移前把应用逻辑移到仓库
接口之后，让领域工作流不直接依赖 SQLite SQL 或连接处理。

Cloud Run 使用受支持的 Cloud SQL 集成和具备 Cloud SQL Client 角色的专用
服务账号连接。由于每个扩展后的服务或 Job 实例都可能打开数据库连接，必须
使用小型有界连接池（见 [Cloud Run 连接 Cloud SQL 指南](https://docs.cloud.google.com/sql/docs/postgres/connect-run)）。

## PostgreSQL 为什么适合 StockPulse

1. 当前数据天然是消息、每日指标和运行记录等关系结构；
2. SQL 适合 Dashboard 聚合、灵活筛选、稳定游标分页、Join 和未来异常重放；
3. PostgreSQL 可以直接承接现有 SQLite 模式与测试；
4. Cloud SQL 提供标准 PostgreSQL 连接、导入导出、自动与按需备份、时间点恢复、
   加密、监控和 Cloud Run 集成（见 [Cloud SQL PostgreSQL 功能](https://docs.cloud.google.com/sql/docs/postgres/features)）；
5. 关系模式为长期历史提供明确约束和迁移。

## 曾考虑的替代方案

### Firestore Standard edition

Firestore 是 Serverless 文档数据库，对非常小的固定键读取负载有吸引力。但其
计费涉及文档操作、索引读取、存储、网络和备份能力，使用前必须以当时官方价格
为准（见 [Firestore 计费](https://firebase.google.com/docs/firestore/pricing)）。

未选择它的原因是 StockPulse 需要不断演进的组合筛选、排序、聚合和关联记录。
Firestore 查询依赖索引，复合范围与排序往往需要人工管理组合索引（见
[Firestore 索引概览](https://firebase.google.com/docs/firestore/query-data/index-overview)）。
这会把关系与聚合复杂度转移到反规范化文档、重复写入和索引规划中。

如果未来证据表明产品主要是固定键文档读取，而 Cloud SQL 成本底线无法接受，
可以重新评估 Firestore。

### Cloud Run 文件系统上的 SQLite

生产环境拒绝此方案，因为 Cloud Run 容器文件系统不会在实例停止后持久化，
也无法安全地成为独立扩展服务和 Job 的共享可写数据库。

### Cloud Storage 中的 SQLite 文件

拒绝此方案，因为对象存储不是支持并发 SQLite 访问的事务共享文件系统。它可
用于导出快照与备份，但不能作为在线数据库。

### AlloyDB

首个版本拒绝此方案，因为其规模和运维特征超过本项目的小负载。只有实测需求
超过 Cloud SQL 时才重新考虑。

## 成本与安全护栏

Cloud SQL 按配置的 CPU、内存、存储与网络计费（见
[Cloud SQL 价格](https://cloud.google.com/sql/pricing)）。与可缩容到零的 Cloud
Run 服务不同，数据库带来持续成本底线。

因此：

- 任何 Cloud SQL 实例都需要所有者明确批准；
- 数据库与 Cloud Run 服务和 Job 选择同一区域，以降低延迟和不必要网络费用；
- 从能够通过实测负载的最小非 HA 配置开始；
- 未批准需求和月度影响前，不启用 HA、副本或延长保留；
- 持续运行前配置 Google Cloud 预算与提醒；
- 在运行手册记录 edition、机器、存储、备份保留和月度估算；
- 只有额外固定成本获批时才维护独立开发与生产数据库。

## 备份与恢复策略

首次生产版本：

- 启用自动备份与时间点恢复；
- 根据存储成本和恢复需求选择保留期；
- 每次破坏性迁移前创建按需备份；
- 上线后及重大模式变化后测试恢复；
- 按文档化计划导出可移植逻辑备份。

Cloud SQL 支持自动与按需备份和时间点恢复，保留期可配置（见
[Cloud SQL 备份 FAQ](https://docs.cloud.google.com/sql/docs/postgres/faq)）。

V1 已启用自动备份、PITR、删除保护与按需验收备份；独立新实例恢复演练仍是
明确暂缓的后续项，不能标记为成功。

## 从 SQLite 迁移的路径

1. 为消息、分析、每日指标和运行引入仓库协议；
2. 保留 SQLite 实现供本地开发与单元测试；
3. 增加 PostgreSQL 实现和等价契约测试；
4. 用有序迁移表达模式变化；生产模式不能只依赖 `CREATE TABLE IF NOT EXISTS`；
5. 按确定性主键顺序读取 SQLite；
6. 在有界事务中幂等导入 PostgreSQL；
7. 验证行数、主键、Null、时间戳、分析版本、每日聚合和运行总数；
8. 在 PostgreSQL 环境中运行 API；
9. 如存在获批来源，保留最终只读 SQLite 快照并协调切换服务与 Job；
10. 回滚窗口结束前保持来源快照只读。

V1 实际没有找到本地 SQLite 快照，因此导入被明确判定为不适用，没有制造
占位历史。

## 后果

正面后果：

- Dashboard 查询清晰且可扩展；
- 当前关系数据自然映射到生产；
- 迁移与约束可以显式测试；
- 备份、恢复和 Cloud Run 连接都有受支持的托管路径。

权衡：

- 即使 Dashboard 流量很低，数据库仍有月度成本；
- 连接池和 Cloud SQL IAM 必须谨慎配置；
- SQLite 与 PostgreSQL 行为可能不同，因此必须共享仓库契约测试；
- 配置、备份保留和生产规格仍需要人工批准。

## 重新评估条件

以下情况应重新评估本决策：

- 已批准月度预算无法支持最小可接受 Cloud SQL 配置；
- 查询稳定为简单文档读取，几乎没有关系聚合；
- 实测规模或可用性要求超过当前 Cloud SQL 配置；
- Google Cloud 相关价格或产品能力发生重大变化。
