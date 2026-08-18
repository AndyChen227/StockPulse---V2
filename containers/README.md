# Container definitions / 容器定义

| File | Purpose / 用途 |
|---|---|
| `service.Dockerfile` | Lightweight Cloud Run Dashboard and API image / 轻量 Cloud Run Dashboard 与 API 镜像 |
| `job.Dockerfile` | Pinned-model Cloud Run pipeline Job image / 固定模型 Cloud Run 流水线 Job 镜像 |

Build from the repository root so both definitions can copy `pyproject.toml`, `README.md`, and `src/`:

```powershell
docker build --file containers/service.Dockerfile --tag stockpulse-service .
docker build --file containers/job.Dockerfile --tag stockpulse-job .
```

请始终从仓库根目录构建，这样两个定义都能读取 Python 包和应用源代码。镜像不得包含 `.env`、本地数据库、原始消息或 Secret。
