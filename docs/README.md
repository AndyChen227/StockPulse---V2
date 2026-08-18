# StockPulse Documentation / StockPulse 文档指南

This directory is the project knowledge base. English guidance appears first; Chinese guidance follows.

## English

### Start here

| If you want to… | Read |
|---|---|
| Understand the product quickly | [Repository README](../README.md) |
| See everything completed from PR #1 to #29 | [Project History](PROJECT_HISTORY.md) |
| Know the exact current stage and remaining work | [Product and Delivery Plan](PROJECT_PLAN.md) |
| Prepare or operate the first Google Cloud launch | [Google Cloud Launch Runbook](GOOGLE_CLOUD_RUNBOOK.md) |

### Product and interface

- [Dashboard](DASHBOARD.md) — views, responsive behavior, and safety boundary
- [Product API](API.md) — endpoints, filters, pagination, errors, and actions

### Analysis

- [Sentiment Evaluation](SENTIMENT_EVALUATION.md) — benchmark, metrics, and model comparison
- [Topic Analysis](TOPIC_ANALYSIS.md) — taxonomy, multi-label assignments, and representative messages
- [Anomaly Detection](ANOMALY_DETECTION.md) — baseline, thresholds, explanations, and replay behavior

### Data and cloud engineering

- [PostgreSQL](POSTGRESQL.md) — production schema, repository, and data migration
- [Cloud Run](CLOUD_RUN.md) — service and Job container contracts
- [ADR 0001](adr/0001-cloud-datastore.md) — why Cloud SQL for PostgreSQL was selected
- [Deployment Contracts](../deploy/README.md) — offline rendering and safety gates

### Source-of-truth rules

- README: concise product introduction and verified current status
- Project History: immutable milestone and PR record
- Product Plan: current priorities and definition of done
- Runbook: approved operational sequence and rollback
- Pull requests: detailed implementation evidence
- ADRs: durable architecture decisions

Update the status date and affected documents whenever a milestone, operating decision, or product boundary changes. Never store credentials, real secret values, billing identifiers, or private account information in documentation.

---

## 中文

### 建议从这里开始

| 如果你想…… | 阅读 |
|---|---|
| 快速理解产品 | [仓库 README](../README.md) |
| 查看 PR #1 到 #29 的全部成果 | [项目历程](PROJECT_HISTORY.md) |
| 确认当前阶段和剩余工作 | [产品与交付计划](PROJECT_PLAN.md) |
| 准备或执行首次 Google Cloud 上线 | [Google Cloud 上线运行手册](GOOGLE_CLOUD_RUNBOOK.md) |

### 产品与界面

- [Dashboard](DASHBOARD.md)：页面、响应式行为和安全边界
- [产品 API](API.md)：接口、筛选、分页、错误和操作契约

### 分析能力

- [情绪评估](SENTIMENT_EVALUATION.md)：基准、指标和模型对比
- [话题分析](TOPIC_ANALYSIS.md)：分类体系、多标签分配和代表消息
- [异常检测](ANOMALY_DETECTION.md)：基线、阈值、解释和历史重放

### 数据与云端工程

- [PostgreSQL](POSTGRESQL.md)：生产模式、仓库和数据迁移
- [Cloud Run](CLOUD_RUN.md)：服务与 Job 容器契约
- [ADR 0001](adr/0001-cloud-datastore.md)：选择 Cloud SQL for PostgreSQL 的原因
- [部署契约](../deploy/README.md)：离线渲染和安全门槛

### 事实来源规则

- README：简洁的产品介绍和已验证当前状态
- 项目历程：稳定的里程碑与 PR 档案
- 产品计划：当前优先级和完成标准
- 运行手册：已批准的操作顺序与回滚方法
- Pull Request：详细实现和验证证据
- ADR：长期有效的架构决策

每当里程碑、运维决策或产品边界发生变化时，应更新状态日期和受影响文档。文档中绝不能保存密码、真实 Secret、Billing 标识或私人账号信息。
