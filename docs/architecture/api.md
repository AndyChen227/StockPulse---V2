# Product API / 产品 API

[English](#english) · [简体中文](#简体中文)

---

# English

> Status: first-release read contract complete; guarded browser collection remains locked

## Purpose and safety boundary

The V1 API gives the deployed Dashboard access to versioned local or production
history. Its read endpoints intentionally expose no collection, reanalysis, overwrite, email,
or cloud-provisioning action. Opening or refreshing a Dashboard cannot spend
Apify credits through these endpoints.

All endpoints are under `/api/v1`. FastAPI also provides local interactive
OpenAPI documentation at `/docs` and the machine-readable schema at
`/openapi.json`.

## Local start

```powershell
$env:PYTHONPATH = "src"
stockpulse-api
```

The server listens on port `8080` by default and honors the Cloud Run `PORT`
environment variable.

## Current endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Stable service and API version health response |
| GET | `/api/v1/ready` | Database connectivity and supported-schema readiness |
| GET | `/api/v1/overview` | Latest metric, anomaly, run, top topics, and active versions |
| GET | `/api/v1/metrics/sentiment` | Daily AI sentiment and volume history with inclusive date filters |
| GET | `/api/v1/topics` | Current versioned topic summary |
| GET | `/api/v1/topics/history` | Date-bucketed topic history with inclusive date filters |
| GET | `/api/v1/messages` | Cursor-paginated message explorer with search and filters |
| GET | `/api/v1/anomalies` | Complete or anomaly-only evaluation history with a bounded limit |
| GET | `/api/v1/runs` | Bounded operational run history with date, action, and status filters |
| GET | `/api/v1/runs/{run_id}` | Complete run detail including limits, errors, and external IDs |

Collection endpoints return a `data` list and `meta` object. Date filters use
`YYYY-MM-DD`; an inverted range returns HTTP 422. Run limits are 1-100 and
anomaly limits are 1-500.

### Message explorer

`GET /api/v1/messages` returns newest messages first and accepts:

- `cursor`: opaque continuation value returned by the previous page
- `limit`: 1-100, default 50
- `start_date` and `end_date`: inclusive UTC calendar-date filters
- `query`: literal case-insensitive body or username search, 2-100 characters
- `stocktwits_sentiment`: `Bullish`, `Neutral`, or `Bearish`
- `ai_sentiment`: `Bullish`, `Neutral`, or `Bearish`
- `minimum_confidence`: 0-1
- `topic`: exact current-taxonomy topic name

The cursor is based on both `created_at` and `message_id`, so equal timestamps
remain deterministic and newly inserted messages do not shift later pages. The
response includes `has_more` and `next_cursor`. Each message exposes its source
link, author label, AI label and confidence, analysis version, and current topic
assignments. Raw source JSON is not exposed.

## Version behavior

The API reads the current pinned sentiment analysis version, topic taxonomy
version, and anomaly detector version. The overview response exposes all three
so the Dashboard can display exactly which analysis produced the current data.

## Response and error contracts

FastAPI response models describe health, readiness, overview, collection, and
single-item envelopes in OpenAPI. Collection endpoints use `data` and `meta`;
single-record endpoints use `data`.

HTTP errors have one stable shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

The process-liveness endpoint remains HTTP 200 while the process is running.
The separate readiness endpoint returns HTTP 503 until the configured database
exists, is reachable, and has a supported schema. Cloud Run can therefore stop
routing traffic without confusing a database failure with a crashed process.

## Post-V1 guarded action work

- propagate and verify the signed-in IAP identity at the application boundary
- add browser CSRF protection and a deployment-specific Cloud Run Jobs dispatcher
- provide distributed confirmation/idempotency storage for multiple instances

## Guarded manual action contract

The collection action API is implemented but disabled by default. It is enabled
only when both a separate 32+ character `STOCKPULSE_ACTION_API_TOKEN` and an
application-injected job dispatcher exist.

1. `GET /api/v1/actions/capabilities` reports availability and server limits.
2. `POST /api/v1/actions/collect/confirmation` requires bearer authentication
   and returns a five-minute signed confirmation containing the symbol, message
   limit, and maximum Actor charge.
3. `POST /api/v1/actions/collect` consumes the confirmation once, creates a
   durable running record, and hands the bounded payload to the dispatcher.
4. Dispatch failures finish that run as failed with a bounded error summary.

No production dispatcher exists yet, so the default service cannot start Apify
or a cloud job. Direct Cloud Run IAP protects the deployed read-only Dashboard,
while browser CSRF, verified identity propagation, and multi-instance
idempotency remain explicit requirements before the action can be unlocked.

---

# 简体中文

> 状态：首个版本的只读契约已完成；受保护的浏览器采集仍保持锁定

## 用途与安全边界

V1 API 让已部署 Dashboard 读取版本化的本地或生产历史。只读接口有意不暴露
采集、重新分析、覆盖写入、邮件或云资源配置操作。打开或刷新 Dashboard 不会
通过这些接口消耗 Apify 额度。

所有接口都位于 `/api/v1`。FastAPI 还在本地提供 `/docs` 交互式 OpenAPI
文档和 `/openapi.json` 机器可读模式。

## 本地启动

```powershell
$env:PYTHONPATH = "src"
stockpulse-api
```

服务器默认监听 `8080`，并遵循 Cloud Run 提供的 `PORT` 环境变量。

## 当前接口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/health` | 稳定的服务和 API 版本存活响应 |
| GET | `/api/v1/ready` | 数据库连接与受支持模式就绪检查 |
| GET | `/api/v1/overview` | 最新指标、异常、运行、热门话题和当前版本 |
| GET | `/api/v1/metrics/sentiment` | 带包含式日期筛选的每日情绪与讨论量历史 |
| GET | `/api/v1/topics` | 当前版本化话题摘要 |
| GET | `/api/v1/topics/history` | 带包含式日期筛选的按日话题历史 |
| GET | `/api/v1/messages` | 支持搜索与筛选的游标分页消息浏览器 |
| GET | `/api/v1/anomalies` | 有上限的完整或仅异常评估历史 |
| GET | `/api/v1/runs` | 带日期、操作和状态筛选的有界运行历史 |
| GET | `/api/v1/runs/{run_id}` | 包含限制、错误和外部 ID 的完整运行详情 |

集合接口返回 `data` 列表和 `meta` 对象。日期格式为 `YYYY-MM-DD`；起止日期
颠倒时返回 HTTP 422。运行记录限制为 1–100，异常记录限制为 1–500。

### 消息浏览器

`GET /api/v1/messages` 按从新到旧返回消息，并接受：

- `cursor`：上一页返回的不透明继续值；
- `limit`：1–100，默认 50；
- `start_date` 与 `end_date`：包含边界的 UTC 自然日筛选；
- `query`：对正文或用户名进行字面量、不区分大小写搜索，长度 2–100；
- `stocktwits_sentiment`：`Bullish`、`Neutral` 或 `Bearish`；
- `ai_sentiment`：`Bullish`、`Neutral` 或 `Bearish`；
- `minimum_confidence`：0–1；
- `topic`：当前分类体系中的精确话题名。

游标同时使用 `created_at` 与 `message_id`，因此相同时间戳仍能稳定排序，
新插入消息也不会移动后续页面。响应包含 `has_more` 和 `next_cursor`。每条消息
会暴露来源链接、作者标签、AI 标签与置信度、分析版本和当前话题分配，但不会
暴露原始来源 JSON。

## 版本行为

API 读取当前固定的情绪版本、话题体系版本和异常检测器版本。Overview 响应
同时返回三者，让 Dashboard 可以明确显示当前数据由哪个分析版本产生。

## 响应与错误契约

FastAPI 响应模型在 OpenAPI 中定义健康、就绪、概览、集合和单项封装。集合
接口使用 `data` 与 `meta`，单记录接口使用 `data`。

HTTP 错误保持一个稳定结构：

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

进程运行时，存活接口保持 HTTP 200。独立就绪接口会在数据库不存在、无法连接
或模式不受支持时返回 HTTP 503。Cloud Run 因而可以停止路由流量，而不会把
数据库故障误判为进程崩溃。

## V1 后受保护操作工作

- 在应用边界传播并验证登录后的 IAP 身份；
- 增加浏览器 CSRF 防护和部署专用 Cloud Run Jobs 调度器；
- 为多实例提供分布式确认与幂等存储。

## 受保护手动操作契约

采集操作 API 已实现，但默认禁用。只有同时存在 32 字符以上的独立
`STOCKPULSE_ACTION_API_TOKEN` 和应用注入的 Job 调度器时才会启用。

1. `GET /api/v1/actions/capabilities` 报告可用性和服务器限制；
2. `POST /api/v1/actions/collect/confirmation` 需要 Bearer 认证，并返回一个
   五分钟有效、包含 Symbol、消息上限和 Actor 最高费用的签名确认；
3. `POST /api/v1/actions/collect` 只使用该确认一次，创建持久运行记录，并把
   有界请求交给调度器；
4. 调度失败会把该运行标记为失败，并保存有上限的错误摘要。

目前没有生产调度器，所以默认服务无法启动 Apify 或云端 Job。Cloud Run 直接
IAP 保护已部署的只读 Dashboard；在解锁操作前，浏览器 CSRF、已验证身份传播
和多实例幂等性仍是明确要求。
