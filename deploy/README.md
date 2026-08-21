# Reviewed Deployment Contracts / 已审查部署契约

[English](#english) · [简体中文](#简体中文)

---

# English

These files prepare the first Google Cloud release without creating or changing
any cloud resource. They follow the official Cloud Run service and Job YAML
schemas and the Cloud Scheduler Jobs API trigger pattern.

> Production status — 2026-08-21: the Dashboard, Pipeline v3, Gmail
> notifications, and both no-retry weekday Scheduler triggers are live and
> production-validated with Cloud SQL. These templates remain the reviewed
> contract for reproducible updates, audit, and rollback.

## Safety gate

Copy `config.example.json` to an untracked file outside the repository only
after the owner has approved the runbook decisions. Set the real project values,
numeric Secret Manager versions, and Artifact Registry image references by
immutable `@sha256:` digest. Finally set `approval_recorded` to `true`.

Render locally:

```powershell
python deploy/render.py C:\secure\stockpulse-deployment.json
```

Rendering is offline. It does not invoke `gcloud`, connect to Google Cloud,
create resources, read secret values, or incur charges. Output is written under
the ignored `build/deployment` directory:

- `service.yaml`: private IAP-protected Dashboard service, scale 0-1
- `job.yaml`: single-task daily pipeline, no automatic retries
- `create-scheduler-premarket.ps1`: weekdays at 9:15 AM Eastern
- `create-scheduler-afterhours.ps1`: weekdays at 6:00 PM Eastern
- both Scheduler commands remain separate; their original safety gate was
  satisfied by the bounded manual Job and email smoke tests before deployment
- `manifest.json`: image digests and checksums for audit and rollback

The renderer rejects unapproved configuration, regions outside the reviewed
West Coast choices, cross-project service accounts, mutable image tags,
unversioned secrets, mismatched Cloud SQL names, and malformed schedules.

## First-release boundaries

- The Dashboard service receives the database secret only.
- The Job receives the database, Apify, and Gmail App Password secrets.
- Gmail delivery sends one later-run daily summary plus detailed anomaly and
  failure alerts, with durable duplicate suppression in PostgreSQL.
- Secret values never enter these files.
- Manual Dashboard collection remains disabled. Scheduler is the only deployed
  Job trigger until IAP identity propagation, CSRF protection, and distributed
  action idempotency are implemented and tested.
- The two Scheduler creation commands use OAuth because their target is the Google
  Cloud Run Jobs API on `run.googleapis.com`.

Applying any rendered file or running the Scheduler command is a separate,
explicitly approved deployment action. See `docs/operations/google-cloud-runbook.md` for
the required provisioning order, IAM, cost, backup, validation, and rollback.

## Notification smoke tests

After the image is deployed, an operator with permission to execute a Job with
overrides can validate the two detailed alert templates without contacting
Apify, opening the database, or changing the saved Job definition:

```powershell
gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,anomaly `
  --wait

gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,failure `
  --wait
```

Both messages start with `[TEST]` and state that no production incident
occurred. Each execution sends exactly one message through the configured SMTP
transport and exits without an Apify request or database write. Both smoke
tests, plus the normal daily-summary path, were verified in production before
Scheduler enablement.

---

# 简体中文

这些文件用于准备首个 Google Cloud 版本，但本身不会创建或修改任何云资源。
它们遵循官方 Cloud Run 服务、Cloud Run Job YAML 模式和 Cloud Scheduler
触发 Cloud Run Jobs API 的方式。

> 生产状态（2026-08-21）：Dashboard、Pipeline v3、Gmail 通知和两个不自动
> 重试的工作日 Scheduler 已上线，并与 Cloud SQL 一起通过生产验证。这些模板
> 继续作为可复现更新、审计和回滚的已审查契约。

## 安全门槛

只有所有者批准运行手册决策后，才把 `config.example.json` 复制到仓库外不受
跟踪的位置。填写真实项目值、数字化 Secret Manager 版本和使用不可变
`@sha256:` 摘要的 Artifact Registry 镜像，最后把 `approval_recorded` 设置为
`true`。

本地渲染：

```powershell
python deploy/render.py C:\secure\stockpulse-deployment.json
```

渲染完全离线：不会调用 `gcloud`、连接 Google Cloud、创建资源、读取 Secret
值或产生费用。输出写入被忽略的 `build/deployment`：

- `service.yaml`：受私有 IAP 保护、规模 0–1 的 Dashboard 服务；
- `job.yaml`：单任务每日流水线，不自动重试；
- `create-scheduler-premarket.ps1`：工作日美东上午 9:15；
- `create-scheduler-afterhours.ps1`：工作日美东下午 6:00；
- 两条 Scheduler 命令保持独立；部署前已通过有界手动 Job 与邮件冒烟测试满足
  原始安全门槛；
- `manifest.json`：用于审计与回滚的镜像摘要和校验和。

渲染器会拒绝未批准配置、审查范围外区域、跨项目服务账号、可变镜像标签、
无版本 Secret、不匹配的 Cloud SQL 名称和格式错误的计划。

## 首个版本边界

- Dashboard 服务只接收数据库 Secret；
- Job 接收数据库、Apify 和 Gmail App Password Secret；
- Gmail 会发送稍后一次运行的每日摘要，以及详细异常与失败告警；PostgreSQL
  提供持久化去重；
- Secret 值绝不会进入这些文件；
- Dashboard 手动采集保持禁用。在 IAP 身份传播、CSRF 防护和分布式操作幂等性
  实现并测试前，Scheduler 是唯一部署的 Job 触发器；
- 两条 Scheduler 创建命令使用 OAuth，因为目标是 `run.googleapis.com` 上的
  Google Cloud Run Jobs API。

应用任何渲染文件或运行 Scheduler 命令都是独立、需明确批准的部署动作。所需
配置顺序、IAM、成本、备份、验证与回滚见
[`docs/operations/google-cloud-runbook.md`](../docs/operations/google-cloud-runbook.md)。

## 通知冒烟测试

镜像部署后，具有“带覆盖参数执行 Job”权限的操作员可以验证两种详细告警模板，
而不联系 Apify、不打开数据库，也不修改保存的 Job 定义：

```powershell
gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,anomaly `
  --wait

gcloud run jobs execute stockpulse-daily-pipeline `
  --project stockpulse-production `
  --region us-west1 `
  --args=--test-notification,failure `
  --wait
```

两封邮件都以 `[TEST]` 开头，并明确说明没有发生生产事故。每次执行通过已配置
SMTP 只发送一封邮件，不请求 Apify、不写数据库，然后退出。这两个冒烟测试和
正常每日摘要路径都已在启用 Scheduler 前通过生产验证。
