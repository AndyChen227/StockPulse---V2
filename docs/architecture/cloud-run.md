# Cloud Run Runtime / Cloud Run 运行架构

[English](#english) · [简体中文](#简体中文)

---

# English

StockPulse has separate container images for the Dashboard/read API and the
pinned-model analysis pipeline. Both images are deployed in `us-west1`: the
Dashboard runs as a Cloud Run service and Pipeline v3 runs as a Cloud Run Job.
Container definitions themselves do not provision Google Cloud resources.

## Service image

`containers/service.Dockerfile`:

- uses Python 3.12 on a slim Linux base
- installs the base application and PostgreSQL runtime without the optional
  local AI model stack
- runs as a dedicated non-root user
- listens on `0.0.0.0` using the `PORT` value supplied by Cloud Run
- exposes the independent `/api/v1/health` liveness endpoint
- includes the Dashboard assets in the installed Python package

GitHub Actions builds the image, starts it, and verifies both the health endpoint
and Dashboard on every pull request. Local Docker is optional for development.

The separate `containers/job.Dockerfile` builds the daily batch image. It installs both AI
and PostgreSQL dependencies, downloads the exact pinned sentiment model revision
during the image build, runs as a non-root user, and starts
`stockpulse --daily-pipeline`. CI verifies that the image can load the tokenizer
from its local cache without a runtime download.

The daily command creates one durable `pipeline` run and performs collection,
validation/storage, current-version sentiment analysis, topic extraction, daily
metric materialization, and anomaly evaluation. It uses the same server-side
item and Apify charge limits as manual collection. A failure records the bounded
error and preserves external Apify identifiers when they are already known.

## Production configuration preflight

Cloud Run must explicitly set `STOCKPULSE_ENVIRONMENT=production`. Before a
revision or Job is allowed to do real work, run the matching offline preflight:

```text
stockpulse --check-production-config service
stockpulse --check-production-config job
```

Both checks require the PostgreSQL backend and keep the initial connection pool
at four or fewer connections per instance. The Job check additionally requires
an Apify token and verifies that the configured sentiment model and revision
match the model cached in `containers/job.Dockerfile`. The command never opens the database,
contacts Apify, or prints secret values. Normal production service and Job
startup enforce the same role-specific contract automatically.

The Dashboard service does not need the Apify token. Only the daily Job receives
that secret. `STOCKPULSE_DATABASE_URL` is supplied to both runtimes through
Secret Manager; it must never be placed in an image or committed environment
file.

## Local container check

On a computer with Docker installed:

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker run --rm --publish 8080:8080 stockpulse-service
```

The Dashboard is then available at `http://localhost:8080`.

The default image has no historical database. Its liveness endpoint and UI can
start, while `/api/v1/ready` correctly reports that durable data is not ready.

## Production state and boundary

The production Dashboard uses Cloud SQL PostgreSQL rather than its disposable
container filesystem. It is deployed with a dedicated service account, scoped
database secret access, the managed Cloud SQL connection, production runtime
configuration, and direct IAP. The live UI has been verified.

Historical SQLite import was skipped because no local source snapshot was
found. Pipeline v3 is deployed by immutable digest with the pipeline identity
and only its required secrets. A bounded production run collected five TSLA
messages, completed the full analysis path, wrote PostgreSQL history, and exited
successfully. Daily-summary, anomaly-test, and failure-test Gmail delivery were
verified before the two no-retry weekday Scheduler triggers were enabled.

Apify credentials, local `.env` files, raw snapshots, SQLite files, tests, and
development artifacts are excluded from the container build context.

## Deployment gate

The V1 deployment gate has passed: project, region, cost controls, database,
secrets, authentication, service readiness, Pipeline v3, Gmail delivery, and
both Scheduler triggers are configured and validated. The Dashboard action
remains intentionally locked; scheduled Job execution is the only production
collection path in the first release.

Reviewed, offline-rendered service, Job, and Scheduler contracts now live under
[`deploy/`](../../deploy/README.md). The renderer rejects mutable image tags,
unversioned secrets, unapproved regions, and configurations without a recorded
owner decision. Rendering never contacts Google Cloud; applying the output is a
separate deployment action performed only through the approved rollout.

PostgreSQL configuration, bounded pooling, ordered schema migrations, and the
full shared read/write repository contract are implemented and tested against
PostgreSQL 17 in CI. The deployed service and Job both use PostgreSQL.
Historical data migration was not applicable because no SQLite snapshot was
available. Production acceptance evidence, immutable image digests, the
transient resource-readiness incident, and rollback instructions are recorded
in the [Google Cloud runbook](../operations/google-cloud-runbook.md). See also
[PostgreSQL implementation](postgresql.md).

---

# 简体中文

StockPulse 为 Dashboard/只读 API 和固定模型分析流水线使用两个独立容器镜像。
两者都部署在 `us-west1`：Dashboard 是 Cloud Run 服务，Pipeline v3 是
Cloud Run Job。容器定义本身不会配置任何 Google Cloud 资源。

## 服务镜像

`containers/service.Dockerfile`：

- 使用 Python 3.12 slim Linux 基础镜像；
- 安装基础应用和 PostgreSQL 运行依赖，不安装本地 AI 模型栈；
- 使用专用非 root 用户运行；
- 在 `0.0.0.0` 上监听 Cloud Run 提供的 `PORT`；
- 暴露独立的 `/api/v1/health` 存活接口；
- 把 Dashboard 资源包含在已安装 Python 包中。

GitHub Actions 会在每个 PR 上构建镜像、启动容器，并检查健康接口和 Dashboard。
本地开发不强制安装 Docker。

独立的 `containers/job.Dockerfile` 构建每日批处理镜像。它安装 AI 与 PostgreSQL
依赖，在构建时下载精确固定 revision 的情绪模型，使用非 root 用户运行，并以
`stockpulse --daily-pipeline` 启动。CI 会验证镜像能够从本地缓存加载 Tokenizer，
无需在运行时下载。

每日命令创建一个持久化 `pipeline` 运行，并执行采集、校验与存储、当前版本
情绪分析、话题提取、每日指标生成和异常评估。它使用与手动采集相同的服务端
条数与 Apify 费用上限。失败会保存有界错误，并在已知时保留外部 Apify ID。

## 生产配置预检

Cloud Run 必须明确设置 `STOCKPULSE_ENVIRONMENT=production`。在 Revision 或
Job 执行真实工作前，应运行相应的离线预检：

```text
stockpulse --check-production-config service
stockpulse --check-production-config job
```

两项检查都要求 PostgreSQL 后端，并把每实例初始连接池限制在最多四个连接。
Job 检查还要求 Apify Token，并验证配置的模型与 revision 是否匹配
`containers/job.Dockerfile` 中缓存的模型。命令不会打开数据库、联系 Apify，
也不会打印 Secret。正常生产启动会自动强制执行同一套角色契约。

Dashboard 服务不需要 Apify Token；只有每日 Job 接收该 Secret。
`STOCKPULSE_DATABASE_URL` 通过 Secret Manager 提供给两种运行环境，绝不能
写入镜像或提交的环境文件。

## 本地容器检查

在安装了 Docker 的电脑上：

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker run --rm --publish 8080:8080 stockpulse-service
```

然后在 `http://localhost:8080` 打开 Dashboard。默认镜像没有历史数据库，因此
存活接口与 UI 可以启动，而 `/api/v1/ready` 会正确报告持久数据未就绪。

## 生产状态与边界

生产 Dashboard 使用 Cloud SQL PostgreSQL，而不是可丢弃的容器文件系统。
它通过专用服务账号、限定范围的数据库 Secret、托管 Cloud SQL 连接、生产配置
和直接 IAP 部署，线上 UI 已完成验证。

由于没有本地 SQLite 来源快照，历史导入被跳过。Pipeline v3 按不可变摘要部署，
使用流水线身份及其必要 Secret。一次有界生产运行成功采集五条 TSLA 消息，
完成完整分析路径、写入 PostgreSQL 并成功退出。启用两个不自动重试的工作日
Scheduler 前，已验证每日摘要、异常 TEST 与失败 TEST 三类 Gmail 投递。

Apify 凭证、本地 `.env`、原始快照、SQLite 文件、测试和开发文件都被排除在
容器构建上下文之外。

## 部署门槛

V1 部署门槛已经通过：项目、区域、成本控制、数据库、Secret、认证、服务就绪、
Pipeline v3、Gmail 投递和两个 Scheduler 均已配置与验证。Dashboard 操作仍被
有意锁定；首个版本唯一生产采集路径是定时 Job。

经过审查的离线服务、Job 与 Scheduler 契约位于
[`deploy/`](../../deploy/README.md)。渲染器拒绝可变镜像标签、无版本 Secret、
未批准区域和没有所有者决策记录的配置。渲染不会联系 Google Cloud；应用输出
是另一个必须按已批准流程执行的部署动作。

PostgreSQL 配置、有界连接池、有序模式迁移和完整共享读写仓库契约均已实现，
并在 CI 中针对 PostgreSQL 17 测试。服务与 Job 均使用 PostgreSQL。因为没有
SQLite 快照，历史迁移不适用。生产验收证据、不可变镜像摘要、临时资源就绪
事件和回滚说明记录在 [Google Cloud 运行手册](../operations/google-cloud-runbook.md)。
另见 [PostgreSQL 实现](postgresql.md)。
