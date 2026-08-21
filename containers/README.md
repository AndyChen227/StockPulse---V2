# Container definitions / 容器定义

[English](#english) · [简体中文](#简体中文)

## English

| File | Purpose | Production role |
|---|---|---|
| `service.Dockerfile` | Lightweight Dashboard and read API image | Cloud Run service |
| `job.Dockerfile` | Pinned-model AI pipeline image | Cloud Run Job |

Build from the repository root so both definitions can copy `pyproject.toml`,
`README.md`, and `src/`:

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker build --file containers/job.Dockerfile --tag stockpulse-job .
```

Images must not contain `.env`, local databases, raw messages, or secrets.

---

## 简体中文

| 文件 | 用途 | 生产角色 |
|---|---|---|
| `service.Dockerfile` | 轻量 Dashboard 与只读 API 镜像 | Cloud Run 服务 |
| `job.Dockerfile` | 固定模型 AI 流水线镜像 | Cloud Run Job |

请始终从仓库根目录构建，这样两个定义都能读取 `pyproject.toml`、
`README.md` 和 `src/`：

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker build --file containers/job.Dockerfile --tag stockpulse-job .
```

镜像不得包含 `.env`、本地数据库、原始消息或 Secret。
