# StockPulse Repository Guide / StockPulse 仓库指南

> Purpose: make every tracked area discoverable without changing runtime paths
>
> Rule: keep standard tool entry points at the repository root; organize understanding through stable folders, local READMEs, and this file map

---

# English

## 1. Where should I start?

| Goal | Start here |
|---|---|
| Understand the product | [`README.md`](../README.md) |
| Run or change the command line | [`src/stockpulse/main.py`](../src/stockpulse/main.py) |
| Run or change the Dashboard/API | [`src/stockpulse/api.py`](../src/stockpulse/api.py) and [`src/stockpulse/web/`](../src/stockpulse/web/) |
| Change collection | [`src/stockpulse/collector/`](../src/stockpulse/collector/) |
| Change sentiment, topics, or anomalies | [`src/stockpulse/sentiment.py`](../src/stockpulse/sentiment.py), [`topics.py`](../src/stockpulse/topics.py), [`anomaly.py`](../src/stockpulse/anomaly.py) |
| Change storage | [`src/stockpulse/repository.py`](../src/stockpulse/repository.py), [`storage.py`](../src/stockpulse/storage.py), and PostgreSQL modules |
| Change the daily pipeline | [`src/stockpulse/pipeline.py`](../src/stockpulse/pipeline.py) |
| Change Google Cloud deployment | [`deploy/`](../deploy/) and [`GOOGLE_CLOUD_RUNBOOK.md`](GOOGLE_CLOUD_RUNBOOK.md) |
| Add or fix tests | [`tests/`](../tests/) |
| Review project decisions and progress | [`docs/`](./) |

## 2. Why some files remain at the root

The root contains standard entry points recognized by development and deployment tools. Moving them into arbitrary folders would make the repository look shorter but would add custom paths and break assumptions in CI, Docker, packaging, and contributor workflows.

| Root file | Purpose | Why it stays here |
|---|---|---|
| `README.md` | Product introduction, status, local start, and navigation | GitHub renders it on the repository home page |
| `LICENSE` | MIT license | Standard discovery location used by GitHub and package tools |
| `pyproject.toml` | Python package metadata, dependencies, console commands, and build configuration | Standard Python packaging entry point |
| `requirements.txt` | Locked lightweight/base runtime dependencies | Used by local setup and familiar to Python tooling |
| `requirements-ai.txt` | Locked optional AI runtime dependencies | Referenced by runtime guidance and dependency errors |
| `requirements-postgres.txt` | Locked optional PostgreSQL dependencies | Referenced by CI and runtime guidance |
| `Dockerfile` | Dashboard/API service container | Default Docker build entry point and CI contract |
| `Dockerfile.job` | Pinned-model pipeline Job container | Explicitly referenced by CI and deployment documentation |
| `.env.example` | Safe environment-variable template with no real secrets | Conventional local configuration template |
| `.gitignore` | Prevents local databases, secrets, caches, and build output from being committed | Git standard |
| `.dockerignore` | Keeps secrets, local data, tests, and development artifacts out of images | Docker standard |

## 3. Directory map

| Directory | Responsibility | Read first |
|---|---|---|
| `.github/` | GitHub automation and contributor-facing repository configuration | [`.github/README.md`](../.github/README.md) |
| `data/` | Ignored local runtime database and raw snapshots | [`data/README.md`](../data/README.md) |
| `deploy/` | Offline-reviewed Cloud Run, Job, and Scheduler deployment contracts | [`deploy/README.md`](../deploy/README.md) |
| `docs/` | Product, architecture, analysis, and operations knowledge base | [`docs/README.md`](README.md) |
| `evaluations/` | Reproducible sentiment benchmark input and result artifacts | [`evaluations/README.md`](../evaluations/README.md) |
| `src/` | Installable application source tree | [`src/README.md`](../src/README.md) |
| `tests/` | Unit, contract, integration, container, and deployment tests | [`tests/README.md`](../tests/README.md) |

## 4. Application file map

All installable code lives under `src/stockpulse/`.

| File or folder | Responsibility |
|---|---|
| `__init__.py` | Package identity and version-facing package boundary |
| `main.py` | CLI parser and user-facing command dispatch |
| `config.py` | Environment loading, limits, backend selection, and production preflight settings |
| `validation.py` | Shared source-message validation and canonical UTC normalization |
| `collector/` | External Apify collection adapter; the only source integration |
| `storage.py` | SQLite schema, migrations, local writes, metrics, and compatibility helpers |
| `repository.py` | Backend-neutral data models and repository contract |
| `postgres.py` | PostgreSQL connection pool, schema migrations, and backend lifecycle |
| `postgres_repository.py` | PostgreSQL implementation of the shared read/write contract |
| `migration.py` | Previewable and transactional SQLite-to-PostgreSQL history import |
| `sentiment.py` | Pinned model adapter, label mapping, confidence, and analysis versioning |
| `model_cache.py` | Pinned-model cache verification used by the Job image and preflight |
| `evaluation.py` | Reproducible finance-direction benchmark runner and metrics |
| `topics.py` | Versioned TSLA topic taxonomy, assignment, summaries, and representatives |
| `anomaly.py` | Versioned historical baseline, anomaly rules, replay, and explanations |
| `pipeline.py` | One bounded collect-to-anomaly orchestration path for the scheduled Job |
| `actions.py` | Guarded collection action request, confirmation, and idempotency contract |
| `api.py` | FastAPI application, REST endpoints, errors, and static Dashboard serving |
| `web/index.html` | Dashboard semantic page structure |
| `web/styles.css` | Responsive visual system, states, accessibility, and motion |
| `web/app.js` | Dashboard API client, rendering, filters, navigation, and interactions |

## 5. Test file map

Tests mirror product boundaries, so the filename tells contributors which behavior is protected.

| File | Protected behavior |
|---|---|
| `test_config.py` | Defaults, secrets, production role validation, and safe diagnostics |
| `test_collector.py` | Apify limits, records, failures, and paid-action boundaries |
| `test_storage.py` | SQLite validation, deduplication, migrations, and metrics |
| `test_repository.py` | Shared SQLite repository behavior |
| `test_postgres.py` | PostgreSQL configuration, pool, and migration contracts without a server |
| `test_postgres_integration.py` | Shared repository behavior against PostgreSQL 17 in CI |
| `test_migration.py` | SQLite inventory, import ordering, idempotency, links, and rollback |
| `test_sentiment.py` | Model adapter, versions, confidence, and reanalysis behavior |
| `test_evaluation.py` | Benchmark schema and metric calculation |
| `test_topics.py` | Topic assignment, history, and representative ranking |
| `test_anomaly.py` | Baseline, thresholds, replay identity, and topic-shift signals |
| `test_pipeline.py` | Complete bounded daily orchestration and failure recording |
| `test_actions.py` | Confirmation, limits, idempotency, and disabled action behavior |
| `test_api.py` | API responses, validation, filters, pagination, errors, and UI serving |
| `test_main.py` | CLI routing and mutually exclusive command behavior |
| `test_container_contract.py` | Service and Job Dockerfile safety and runtime contracts |
| `test_deployment.py` | Offline renderer validation, schedules, secrets, and manifest output |

## 6. Deployment file map

| File | Responsibility |
|---|---|
| `deploy/README.md` | Safety gate and reviewed deployment boundaries |
| `deploy/config.example.json` | Non-secret shape for approved project and resource identifiers |
| `deploy/render.py` | Offline validation and rendering; never calls Google Cloud |
| `deploy/service.yaml.tmpl` | Private Cloud Run Dashboard/API service template |
| `deploy/job.yaml.tmpl` | Single-task, no-retry pipeline Job template |
| `.github/workflows/tests.yml` | Five CI checks: two Python versions, service image, Job image, and PostgreSQL |

## 7. Evaluation and documentation file map

| File or area | Responsibility |
|---|---|
| `evaluations/finance_sentiment_v1.jsonl` | Reviewed V1 finance-direction examples |
| `evaluations/results/twitter-roberta-v1.json` | Retained pinned-model baseline output |
| `evaluations/results/prosus-finbert-v1.json` | Candidate comparison output |
| `docs/PROJECT_HISTORY.md` | PR-by-PR implementation record |
| `docs/PROJECT_PLAN.md` | Current delivery state, next gates, and definition of done |
| `docs/API.md` | API and error contracts |
| `docs/DASHBOARD.md` | Dashboard behavior and action safety boundary |
| `docs/SENTIMENT_EVALUATION.md` | Sentiment benchmark interpretation |
| `docs/TOPIC_ANALYSIS.md` | Topic taxonomy and representative evidence |
| `docs/ANOMALY_DETECTION.md` | Baseline, thresholds, and replay behavior |
| `docs/POSTGRESQL.md` | Production database and migration design |
| `docs/CLOUD_RUN.md` | Container and runtime contract |
| `docs/GOOGLE_CLOUD_RUNBOOK.md` | Owner-approved provisioning, cost, security, backup, validation, and rollback sequence |
| `docs/adr/` | Durable architecture decision records |

## 8. Change-placement rules

1. Put installable runtime code only under `src/stockpulse/`.
2. Add tests beside the corresponding boundary in `tests/test_<area>.py`.
3. Put user/operator explanations in `docs/`; keep low-level implementation detail in code and PRs.
4. Put reproducible labeled inputs and machine-readable benchmark outputs in `evaluations/`.
5. Put only reviewed, secret-free, offline deployment contracts in `deploy/`.
6. Treat `data/` as disposable local runtime state; never commit databases, raw messages, or credentials.
7. Keep secrets out of every tracked file.
8. Do not rename or move root tooling files without updating and testing every reference.

---

# 中文

## 1. 我应该从哪里开始？

| 目标 | 从这里开始 |
|---|---|
| 理解产品 | [`README.md`](../README.md) |
| 运行或修改命令行 | [`src/stockpulse/main.py`](../src/stockpulse/main.py) |
| 运行或修改 Dashboard/API | [`src/stockpulse/api.py`](../src/stockpulse/api.py) 与 [`src/stockpulse/web/`](../src/stockpulse/web/) |
| 修改采集 | [`src/stockpulse/collector/`](../src/stockpulse/collector/) |
| 修改情绪、话题或异常 | [`sentiment.py`](../src/stockpulse/sentiment.py)、[`topics.py`](../src/stockpulse/topics.py)、[`anomaly.py`](../src/stockpulse/anomaly.py) |
| 修改存储 | [`repository.py`](../src/stockpulse/repository.py)、[`storage.py`](../src/stockpulse/storage.py) 和 PostgreSQL 模块 |
| 修改每日流水线 | [`pipeline.py`](../src/stockpulse/pipeline.py) |
| 修改 Google Cloud 部署 | [`deploy/`](../deploy/) 与[上线运行手册](GOOGLE_CLOUD_RUNBOOK.md) |
| 增加或修复测试 | [`tests/`](../tests/) |
| 查看项目决策和进度 | [`docs/`](./) |

## 2. 为什么有些文件必须留在根目录

根目录保存开发和部署工具能够自动识别的标准入口。把它们随意移动虽然会让首页文件更少，却会增加自定义路径，并破坏 CI、Docker、Python 打包和贡献者的常规工作方式。

| 根目录文件 | 用途 | 保留原因 |
|---|---|---|
| `README.md` | 产品介绍、状态、本地启动和导航 | GitHub 仓库首页自动显示 |
| `LICENSE` | MIT 许可证 | GitHub 与打包工具的标准发现位置 |
| `pyproject.toml` | Python 包信息、依赖、命令和构建配置 | Python 标准打包入口 |
| `requirements.txt` | 锁定的轻量基础依赖 | 本地安装和 Python 工具常用入口 |
| `requirements-ai.txt` | 锁定的可选 AI 依赖 | 运行说明和错误提示会引用 |
| `requirements-postgres.txt` | 锁定的 PostgreSQL 依赖 | CI 和运行说明会引用 |
| `Dockerfile` | Dashboard/API 服务镜像 | Docker 默认入口与 CI 契约 |
| `Dockerfile.job` | 固定模型流水线 Job 镜像 | CI 与部署文档明确引用 |
| `.env.example` | 不包含真实 Secret 的环境变量模板 | 本地配置惯例 |
| `.gitignore` | 阻止本地数据库、Secret、缓存和构建输出进入 Git | Git 标准文件 |
| `.dockerignore` | 阻止 Secret、本地数据、测试和开发文件进入镜像 | Docker 标准文件 |

## 3. 目录地图

| 目录 | 职责 | 先读 |
|---|---|---|
| `.github/` | GitHub 自动化与仓库配置 | [`.github/README.md`](../.github/README.md) |
| `data/` | 被忽略的本地数据库与原始快照 | [`data/README.md`](../data/README.md) |
| `deploy/` | 离线审查的 Cloud Run、Job 与 Scheduler 契约 | [`deploy/README.md`](../deploy/README.md) |
| `docs/` | 产品、架构、分析与运维知识库 | [`docs/README.md`](README.md) |
| `evaluations/` | 可复现的情绪评估输入和结果 | [`evaluations/README.md`](../evaluations/README.md) |
| `src/` | 可安装的应用源代码 | [`src/README.md`](../src/README.md) |
| `tests/` | 单元、契约、集成、容器和部署测试 | [`tests/README.md`](../tests/README.md) |

## 4. 应用文件地图

所有可安装代码都位于 `src/stockpulse/`。

| 文件或目录 | 职责 |
|---|---|
| `__init__.py` | Python 包身份与版本边界 |
| `main.py` | CLI 参数与用户命令分发 |
| `config.py` | 环境配置、限制、后端选择和生产预检 |
| `validation.py` | 消息校验与标准 UTC 时间 |
| `collector/` | 外部 Apify 采集适配器；唯一来源集成 |
| `storage.py` | SQLite 模式、迁移、本地写入、指标和兼容辅助 |
| `repository.py` | 与后端无关的数据模型和仓库契约 |
| `postgres.py` | PostgreSQL 连接池、模式迁移和生命周期 |
| `postgres_repository.py` | 共享读写契约的 PostgreSQL 实现 |
| `migration.py` | 可预览、事务化的 SQLite 到 PostgreSQL 历史导入 |
| `sentiment.py` | 固定模型、标签映射、置信度和分析版本 |
| `model_cache.py` | Job 镜像与预检使用的固定模型缓存校验 |
| `evaluation.py` | 金融方向基准运行器与指标 |
| `topics.py` | TSLA 话题体系、分配、汇总和代表消息 |
| `anomaly.py` | 历史基线、异常规则、重放和解释 |
| `pipeline.py` | Scheduler Job 使用的有界端到端流水线 |
| `actions.py` | 受保护采集请求、确认和幂等契约 |
| `api.py` | FastAPI、REST 接口、错误和 Dashboard 静态资源 |
| `web/index.html` | Dashboard 语义页面结构 |
| `web/styles.css` | 响应式视觉、状态、无障碍和动画 |
| `web/app.js` | API 客户端、渲染、筛选、导航和交互 |

## 5. 测试文件地图

测试文件名与产品边界一一对应：配置、采集、存储、仓库、PostgreSQL、迁移、情绪、评估、话题、异常、流水线、操作、API、CLI、容器和部署。完整的逐文件保护范围见本页英文表格与 [`tests/README.md`](../tests/README.md)。

## 6. 修改位置规则

1. 可安装运行代码只放在 `src/stockpulse/`。
2. 测试放在 `tests/test_<领域>.py`，并与对应产品边界匹配。
3. 用户和运维说明放在 `docs/`；低层实现细节留在代码和 PR。
4. 可复现标注输入和机器可读结果放在 `evaluations/`。
5. `deploy/` 只保存经过审查、无 Secret、可离线验证的部署契约。
6. `data/` 是可丢弃的本地运行状态；绝不提交数据库、原始消息或凭证。
7. 所有受 Git 跟踪文件都禁止保存真实 Secret。
8. 移动根目录工具文件前，必须更新并测试所有引用。
