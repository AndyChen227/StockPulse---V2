# StockPulse Documentation / StockPulse 文档中心

[English](#english) · [简体中文](#简体中文)

> Every explanatory document is complete in both languages: English first,
> Simplified Chinese second. Commands, identifiers, and source-of-truth values
> remain identical in both sections.

## English

> V1 documentation baseline — 2026-08-21: the production Dashboard, Pipeline
> v3, Gmail notifications, weekday Scheduler triggers, external Job-failure
> alert, and backup controls are live. The isolated Cloud SQL restore drill is
> the one explicitly deferred recovery exercise.

The documentation is grouped by the question a reader is trying to answer. Start with the product folder for context, then use architecture, analysis, operations, reference, or decisions for deeper detail.

### Directory map

| Category | One-sentence purpose | Index |
|---|---|---|
| `product/` | Explains what StockPulse is, what has been delivered, and what the Dashboard must provide. | [Product documents](product/README.md) |
| `architecture/` | Describes the API, data layer, containers, and technical runtime boundaries. | [Architecture documents](architecture/README.md) |
| `analysis/` | Defines how sentiment, topics, and anomalies are evaluated and interpreted. | [Analysis documents](analysis/README.md) |
| `operations/` | Provides the controlled procedure for deploying and operating StockPulse on Google Cloud. | [Operations documents](operations/README.md) |
| `reference/` | Helps contributors locate every important file and choose the correct place for a change. | [Reference documents](reference/README.md) |
| `decisions/` | Preserves durable architecture decisions and the alternatives that were considered. | [Decision records](decisions/README.md) |

### File catalog

| Document | One-sentence description |
|---|---|
| [`product/project-plan.md`](product/project-plan.md) | Tracks the current delivery stage, launch gates, priorities, and definition of done. |
| [`product/project-history.md`](product/project-history.md) | Records the engineering outcome of every merged pull request and current validation evidence. |
| [`product/dashboard.md`](product/dashboard.md) | Defines Dashboard views, responsive behavior, and the boundary around paid actions. |
| [`architecture/api.md`](architecture/api.md) | Documents REST endpoints, filters, pagination, errors, and guarded action contracts. |
| [`architecture/postgresql.md`](architecture/postgresql.md) | Explains the production repository, schema migrations, pooling, and history import. |
| [`architecture/cloud-run.md`](architecture/cloud-run.md) | Defines the lightweight service and pinned-model Job container/runtime contracts. |
| [`analysis/sentiment-evaluation.md`](analysis/sentiment-evaluation.md) | Describes the finance-direction benchmark, metrics, model comparison, and quality limits. |
| [`analysis/topic-analysis.md`](analysis/topic-analysis.md) | Defines the versioned TSLA topic taxonomy and representative-message ranking. |
| [`analysis/anomaly-detection.md`](analysis/anomaly-detection.md) | Defines the historical baseline, thresholds, topic shifts, explanations, and replay rules. |
| [`operations/google-cloud-runbook.md`](operations/google-cloud-runbook.md) | Gives the approved provisioning, cost, IAM, backup, deployment, validation, and rollback sequence. |
| [`reference/repository-guide.md`](reference/repository-guide.md) | Maps every runtime, test, deployment, evaluation, and documentation file to its responsibility. |
| [`decisions/0001-cloud-datastore.md`](decisions/0001-cloud-datastore.md) | Records why Cloud SQL for PostgreSQL was selected as the production source of truth. |

### Documentation rules

- Keep filenames lowercase with hyphens and place each document in one clear category.
- Keep every Markdown explanation complete in English first and Simplified
  Chinese second; preserve the same headings, commands, identifiers, and facts.
- Put user and operator explanations here; keep implementation details in code and pull requests.
- Update links, the category index, and tests whenever a document moves.
- Never include credentials, secret values, billing identifiers, or private account information.
- Do not rewrite an accepted decision record; supersede it with a new numbered decision.

---

## 简体中文

> 每份解释性文档都提供完整双语内容：英文在前，简体中文在后。命令、标识符
> 和事实来源值在两种语言中保持完全一致。

> V1 文档基线（2026-08-21）：生产 Dashboard、Pipeline v3、Gmail 通知、
> 两个工作日 Scheduler、外部 Job 失败告警和备份控制均已上线。Cloud SQL
> 独立恢复演练是唯一明确暂缓的恢复验证。

### 目录地图

| 分类 | 一句话用途 | 索引 |
|---|---|---|
| `product/` | 说明 StockPulse 是什么、已经交付什么，以及 Dashboard 必须提供什么。 | [产品文档](product/README.md) |
| `architecture/` | 说明 API、数据层、容器和技术运行边界。 | [架构文档](architecture/README.md) |
| `analysis/` | 定义情绪、话题和异常如何评估与解释。 | [分析文档](analysis/README.md) |
| `operations/` | 提供在 Google Cloud 上受控部署和运维 StockPulse 的步骤。 | [运维文档](operations/README.md) |
| `reference/` | 帮助贡献者找到每个重要文件，并判断改动应放在哪里。 | [参考文档](reference/README.md) |
| `decisions/` | 保存长期架构决策和曾经考虑过的替代方案。 | [决策记录](decisions/README.md) |

### 逐文件目录

| 文档 | 一句话说明 |
|---|---|
| [`product/project-plan.md`](product/project-plan.md) | 记录当前交付阶段、上线门槛、优先级和完成标准。 |
| [`product/project-history.md`](product/project-history.md) | 记录每个已合并 PR 的工程成果和当前验证证据。 |
| [`product/dashboard.md`](product/dashboard.md) | 定义 Dashboard 页面、响应式行为和付费操作安全边界。 |
| [`architecture/api.md`](architecture/api.md) | 记录 REST 接口、筛选、分页、错误和受保护操作契约。 |
| [`architecture/postgresql.md`](architecture/postgresql.md) | 说明生产仓库、模式迁移、连接池和历史导入。 |
| [`architecture/cloud-run.md`](architecture/cloud-run.md) | 定义轻量服务和固定模型 Job 的容器及运行时契约。 |
| [`analysis/sentiment-evaluation.md`](analysis/sentiment-evaluation.md) | 说明金融方向基准、指标、模型对比和质量限制。 |
| [`analysis/topic-analysis.md`](analysis/topic-analysis.md) | 定义版本化 TSLA 话题体系和代表消息排序。 |
| [`analysis/anomaly-detection.md`](analysis/anomaly-detection.md) | 定义历史基线、阈值、话题变化、解释和重放规则。 |
| [`operations/google-cloud-runbook.md`](operations/google-cloud-runbook.md) | 给出已批准的资源、成本、IAM、备份、部署、验证和回滚顺序。 |
| [`reference/repository-guide.md`](reference/repository-guide.md) | 把每个运行、测试、部署、评估和文档文件映射到对应职责。 |
| [`decisions/0001-cloud-datastore.md`](decisions/0001-cloud-datastore.md) | 记录选择 Cloud SQL for PostgreSQL 作为生产事实来源的原因。 |

### 文档维护规则

- 文件名统一使用小写连字符，并放入一个明确分类。
- 每份 Markdown 说明都必须英文在前、简体中文在后，并保持相同章节、命令、
  标识符和事实。
- 用户和运维说明放在这里；实现细节保留在代码和 PR 中。
- 文档移动时同时更新链接、分类索引和测试。
- 绝不记录凭证、真实 Secret、Billing 标识或私人账号信息。
- 不改写已经接受的决策记录；应创建新的编号决策取代旧记录。
