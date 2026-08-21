# Architecture documents / 架构文档

[English](#english) · [简体中文](#简体中文)

## English

This folder explains how the application is built and how runtime boundaries
interact.

| File | Boundary it explains |
|---|---|
| [`api.md`](api.md) | FastAPI read endpoints, errors, pagination, and guarded actions |
| [`postgresql.md`](postgresql.md) | Production persistence, pooling, migrations, backup, and recovery |
| [`cloud-run.md`](cloud-run.md) | Dashboard service and pipeline Job container/runtime contracts |

---

## 简体中文

本目录说明应用如何构建，以及各运行边界如何协作。

| 文件 | 说明的边界 |
|---|---|
| [`api.md`](api.md) | FastAPI 只读接口、错误、分页和受保护操作 |
| [`postgresql.md`](postgresql.md) | 生产持久化、连接池、迁移、备份与恢复 |
| [`cloud-run.md`](cloud-run.md) | Dashboard 服务与流水线 Job 的容器和运行契约 |
