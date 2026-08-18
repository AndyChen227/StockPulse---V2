# Dependency sets / 依赖集合

| File | Purpose / 用途 |
|---|---|
| `base.txt` | Lightweight collection, API, Dashboard, and SQLite runtime / 轻量采集、API、Dashboard 与 SQLite 运行环境 |
| `ai.txt` | Base plus pinned PyTorch and Transformers / 基础依赖加固定版本 PyTorch 与 Transformers |
| `postgres.txt` | Base plus PostgreSQL driver and pool / 基础依赖加 PostgreSQL 驱动和连接池 |

**English:** Install from the repository root, for example `python -m pip install -r config/requirements/postgres.txt`. Keep these pins synchronized with `pyproject.toml`.

**中文：** 请从仓库根目录安装，例如 `python -m pip install -r config/requirements/postgres.txt`。这些固定版本必须与 `pyproject.toml` 保持同步。
