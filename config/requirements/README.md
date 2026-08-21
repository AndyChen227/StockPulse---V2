# Dependency sets / 依赖集合

[English](#english) · [简体中文](#简体中文)

## English

| File | Runtime it installs |
|---|---|
| `base.txt` | Lightweight collection, API, Dashboard, and SQLite runtime |
| `ai.txt` | Base runtime plus pinned PyTorch and Transformers |
| `postgres.txt` | Base runtime plus the PostgreSQL driver and connection pool |

Install from the repository root, for example:

```powershell
python -m pip install -r config/requirements/postgres.txt
```

Keep every pin synchronized with `pyproject.toml`.

---

## 简体中文

| 文件 | 安装的运行环境 |
|---|---|
| `base.txt` | 轻量采集、API、Dashboard 与 SQLite 运行环境 |
| `ai.txt` | 基础运行环境，加固定版本的 PyTorch 与 Transformers |
| `postgres.txt` | 基础运行环境，加 PostgreSQL 驱动和连接池 |

请从仓库根目录安装，例如：

```powershell
python -m pip install -r config/requirements/postgres.txt
```

所有固定版本都必须与 `pyproject.toml` 保持同步。
