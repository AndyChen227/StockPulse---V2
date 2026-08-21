# StockPulse Dashboard / StockPulse 数据看板

[English](#english) · [简体中文](#简体中文)

---

# English

The initial StockPulse Dashboard is a responsive, read-only interface served by
the existing FastAPI application at `/`. It uses the versioned `/api/v1` read
contract and does not require a separate frontend server or external browser
assets.

## Current views

- Overview cards for discussion volume, sentiment score, anomaly state, and the
  latest pipeline run
- Bullish, Neutral, and Bearish distribution with current analysis metadata
- Date-range sentiment and volume history
- Topic summary and historical topic filtering
- Latest anomaly explanation
- Cursor-paginated message explorer with text, sentiment, confidence, and topic
  filters
- Run history with a failed-only filter and recorded processing counts
- Database readiness and data-refresh status

Every major data surface has an explicit loading, empty, and error state. The
layout adapts to desktop, tablet, and mobile widths, supports keyboard focus,
and honors reduced-motion preferences.

## Safety boundary

Refreshing and filtering only read stored data. The collection control is
visible but disabled. It must remain locked until the backend provides an
authenticated action endpoint with a displayed cost cap, explicit user
confirmation, bounded execution, and an auditable run record.

The Dashboard never starts an Apify Actor by loading the page.

## Run locally

Install the base project dependencies, make `src` available on `PYTHONPATH`, and
run:

```powershell
stockpulse-api
```

Then open `http://localhost:8080`. API documentation remains available at
`http://localhost:8080/docs`.

An empty local database is supported and displays empty states rather than
invented sample data. Collection is still a separate, explicit command.

## Production state and post-V1 work

- The Dashboard is live on Cloud Run with direct IAP and Cloud SQL PostgreSQL.
- Historical migration was skipped because no local SQLite snapshot was found;
  visible production history now comes from successful Pipeline v3 runs.
- The compatible production image is pinned by digest, and the active revision
  passed live access and error-log verification during acceptance.
- Review the interface with representative production history and refine chart
  and table details after an observation period
- Add a focused run-detail view for error and retry information
- Continue observing the external Cloud Monitoring Job-failure alert. Backup,
  PITR, and rollback procedures are documented; the isolated restore drill is
  explicitly deferred after an HTTP 403 response before instance creation.
- Add verified IAP identity, CSRF protection, cloud Job dispatch, and distributed
  idempotency before unlocking bounded, confirmed collection actions

---

# 简体中文

StockPulse 初始 Dashboard 是由现有 FastAPI 应用在 `/` 直接提供的响应式只读
界面。它使用版本化 `/api/v1` 读取契约，不需要独立前端服务器或外部浏览器资源。

## 当前视图

- 讨论量、情绪分数、异常状态和最近流水线运行的概览卡片；
- Bullish、Neutral、Bearish 分布和当前分析元数据；
- 支持日期范围的情绪与讨论量历史；
- 话题摘要和历史话题筛选；
- 最新异常解释；
- 支持文本、情绪、置信度和话题筛选的游标分页消息浏览器；
- 支持“仅失败”筛选并显示处理计数的运行历史；
- 数据库就绪与数据刷新状态。

每个主要数据区域都有明确的加载、空数据和错误状态。布局适配桌面、平板和手机，
支持键盘焦点，并遵循“减少动态效果”偏好。

## 安全边界

刷新和筛选只读取已保存数据。采集控制可见但保持禁用；只有后端具备经过认证
的操作接口、展示的成本上限、明确用户确认、有界执行和可审计运行记录后，才能
考虑解锁。

加载 Dashboard 永远不会启动 Apify Actor。

## 本地运行

安装基础依赖，然后运行：

```powershell
stockpulse-api
```

打开 `http://localhost:8080`。API 文档位于 `http://localhost:8080/docs`。

空本地数据库是受支持状态，页面会显示空数据界面，而不是制造样例数据。采集
仍是独立、显式的命令。

## 生产状态与 V1 后工作

- Dashboard 已通过直接 IAP 和 Cloud SQL PostgreSQL 在 Cloud Run 上线；
- 因为没有找到本地 SQLite 快照，历史迁移被跳过；可见生产历史来自成功的
  Pipeline v3 运行；
- 兼容生产模式的镜像按摘要固定，活动 Revision 在验收时通过线上访问和错误
  日志检查；
- 观察到有代表性的生产历史后，再优化图表和表格细节；
- 增加聚焦错误与重试信息的运行详情视图；
- 继续观察外部 Cloud Monitoring Job 失败告警。备份、PITR 与回滚程序已有
  记录；独立恢复演练因创建实例前 HTTP 403 而明确暂缓；
- 解锁有界、确认式采集前，增加已验证 IAP 身份、CSRF 防护、云端 Job 调度和
  分布式幂等性。
