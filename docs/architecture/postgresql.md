# PostgreSQL Implementation / PostgreSQL 实现

[English](#english) · [简体中文](#简体中文)

---

# English

StockPulse keeps SQLite as the zero-cost local backend and uses PostgreSQL as
the production system of record. The live Dashboard connects to Cloud SQL for
PostgreSQL 17 in `stockpulse-production` through the managed Cloud Run
integration and a bounded application pool.

## Current foundation

- PostgreSQL is an optional dependency, so ordinary local installation remains
  lightweight.
- The connection URL is treated as a secret and never appears in the settings
  representation.
- Pool size is bounded to 10 connections and defaults to 1–4 connections.
- The pool is created closed by default, so importing configuration cannot open
  a network connection.
- Six ordered migrations mirror the current SQLite schema history.
- A PostgreSQL advisory transaction lock prevents two service instances from
  applying migrations concurrently.
- PostgreSQL-native `TIMESTAMPTZ`, `DATE`, `JSONB`, `BIGINT`, `BOOLEAN`, UUID,
  and numeric types preserve stronger production constraints.
- A database created by a newer application version is rejected rather than
  silently downgraded.
- The Dashboard read repository supports readiness, overview metrics, stable
  message pagination and filters, topic summary/history, anomaly history, and
  run history/detail.
- GitHub Actions applies the migrations to an ephemeral PostgreSQL 17 service
  and runs the complete shared read/write repository contract.
- PostgreSQL now implements the complete shared repository contract: message
  deduplication, daily statistics, versioned sentiment metrics, topic writes,
  anomaly writes, and durable run lifecycle in addition to Dashboard reads.

## Configuration

The default remains:

```text
STOCKPULSE_DATABASE_BACKEND=sqlite
```

Production PostgreSQL deployments provide the following values through runtime
configuration and Secret Manager, not a committed `.env` file:

```text
STOCKPULSE_DATABASE_BACKEND=postgresql
STOCKPULSE_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/stockpulse
STOCKPULSE_DATABASE_POOL_MIN_SIZE=1
STOCKPULSE_DATABASE_POOL_MAX_SIZE=4
```

The production service image installs the `postgres` dependency group, while
ordinary local installation remains lightweight. The connection URL remains a
runtime secret and is never baked into the image.

The Dashboard service and command-line background workflows select PostgreSQL
when the backend and secret URL are configured. They apply pending migrations
before serving or processing data and close the bounded pool on shutdown.
SQLite remains the zero-cost default.

## Historical data migration

The migration tool remains available for any approved SQLite source. For the
first production launch, no local `stockpulse.db` snapshot was found, so this
step was intentionally skipped. Production history begins with new pipeline
runs; no placeholder data should be manufactured.

Preview the source inventory without connecting to or writing PostgreSQL:

```powershell
stockpulse-migrate --source data/stockpulse.db
```

After the PostgreSQL runtime secret is configured, explicitly apply the import:

```powershell
stockpulse-migrate --source data/stockpulse.db --apply
```

The importer requires SQLite schema version 6, reads the source in read-only
mode, imports all six business tables in foreign-key order, and restores run
retry relationships in a second pass. PostgreSQL writes and source-key
verification share one transaction, so a failed verification rolls back the
entire attempt. Primary-key conflicts are skipped, making a verified rerun
idempotent.

## Current production state and recovery follow-up

Completed:

- Cloud SQL PostgreSQL 17 Enterprise, `db-f1-micro`, single-zone, 10 GB SSD
- application database `stockpulse` and least-privilege role/user
- backups, PITR, deletion protection, and managed Cloud Run connectivity
- database URL secret access scoped to the service identities that require it
- Dashboard PostgreSQL readiness and live UI verification
- Pipeline v3 writes verified through a successful bounded production run
- successful on-demand backup `1787294067917`, daily backups at `22:00 UTC`,
  seven-day PITR, and deletion protection

Follow-up:

1. Complete an isolated restore to a separate temporary instance and validate
   the restored schema and data. The 2026-08-21 attempt was rejected by the
   Cloud SQL API with HTTP 403 before an instance was created, so this drill is
   explicitly deferred rather than represented as successful.
2. Continue verifying scheduled writes, backup health, storage growth, and
   connection-pool behavior during normal production operation.
3. Keep application and Job rollback coordinated whenever a future schema
   change is not backward compatible.

---

# 简体中文

StockPulse 保留 SQLite 作为零成本本地后端，并使用 PostgreSQL 作为生产事实
来源。线上 Dashboard 通过托管 Cloud Run 集成和有界应用连接池，连接
`stockpulse-production` 中的 Cloud SQL for PostgreSQL 17。

## 当前基础

- PostgreSQL 是可选依赖，普通本地安装仍保持轻量；
- 连接 URL 被视为 Secret，不会出现在配置对象的字符串表示中；
- 连接池硬上限为 10，默认使用 1–4 个连接；
- 连接池默认以关闭状态创建，因此导入配置不会打开网络连接；
- 六个有序迁移与当前 SQLite 模式历史对应；
- PostgreSQL Advisory Transaction Lock 防止两个服务实例并发应用迁移；
- 原生 `TIMESTAMPTZ`、`DATE`、`JSONB`、`BIGINT`、`BOOLEAN`、UUID 和
  数值类型提供更强生产约束；
- 由更高版本应用创建的数据库会被拒绝，而不是被静默降级；
- Dashboard 读仓库支持就绪、概览指标、稳定消息分页与筛选、话题摘要/历史、
  异常历史和运行历史/详情；
- GitHub Actions 会在临时 PostgreSQL 17 服务上应用迁移并运行完整共享读写
  契约；
- PostgreSQL 已实现消息去重、每日统计、版本化情绪指标、话题写入、异常写入
  和持久运行生命周期。

## 配置

默认设置仍为：

```text
STOCKPULSE_DATABASE_BACKEND=sqlite
```

生产 PostgreSQL 通过运行配置和 Secret Manager 提供以下值，不使用已提交
`.env`：

```text
STOCKPULSE_DATABASE_BACKEND=postgresql
STOCKPULSE_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/stockpulse
STOCKPULSE_DATABASE_POOL_MIN_SIZE=1
STOCKPULSE_DATABASE_POOL_MAX_SIZE=4
```

生产服务镜像安装 `postgres` 依赖组，普通本地安装仍保持轻量。连接 URL 始终是
运行时 Secret，不会写入镜像。

Dashboard 服务和后台命令会在配置后端与 Secret URL 时选择 PostgreSQL。
它们在提供服务或处理数据前应用待执行迁移，并在关闭时关闭有界连接池。
SQLite 仍是零成本默认值。

## 历史数据迁移

迁移工具仍可用于未来经过批准的 SQLite 来源。首个生产上线期间没有找到本地
`stockpulse.db` 快照，因此该步骤被有意跳过。生产历史从新的流水线运行开始，
不得制造占位数据。

不连接或写入 PostgreSQL，只预览来源清单：

```powershell
stockpulse-migrate --source data/stockpulse.db
```

配置 PostgreSQL 运行时 Secret 后，显式应用导入：

```powershell
stockpulse-migrate --source data/stockpulse.db --apply
```

导入器要求 SQLite 模式版本 6，以只读模式读取来源，按外键顺序导入全部六个
业务表，并在第二阶段恢复运行重试关系。PostgreSQL 写入与来源主键验证共享一个
事务，验证失败会回滚整个尝试。主键冲突会被跳过，因此验证后的重复运行保持
幂等。

## 当前生产状态与恢复后续

已完成：

- Cloud SQL PostgreSQL 17 Enterprise、`db-f1-micro`、单区、10 GB SSD；
- 应用数据库 `stockpulse` 和最小权限角色/用户；
- 备份、PITR、删除保护和托管 Cloud Run 连接；
- 数据库 URL Secret 只授权给需要它的服务身份；
- Dashboard PostgreSQL 就绪与线上 UI 验证；
- 通过一次成功有界生产运行验证 Pipeline v3 写入；
- 成功的按需备份 `1787294067917`、每日 `22:00 UTC` 备份、7 天 PITR 和
  删除保护。

后续：

1. 恢复到独立临时实例并私下验证模式与数据。2026-08-21 尝试在创建实例前
   被 Cloud SQL API 以 HTTP 403 拒绝，因此该演练被明确暂缓，不能描述为成功；
2. 在正常生产运行中继续验证定时写入、备份健康、存储增长和连接池行为；
3. 未来模式变化不向后兼容时，保持应用与 Job 回滚协调一致。
