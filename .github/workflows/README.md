# Continuous integration / 持续集成

**English:** `tests.yml` is the single CI workflow. It validates Python 3.11, Python 3.12, the Dashboard service image, the pinned-model Job image, and PostgreSQL 17 behavior. It reads dependencies from `config/requirements/` and container definitions from `containers/`. Keep workflow changes aligned with local commands and container contracts.

**中文：** `tests.yml` 是唯一的 CI 工作流，负责验证 Python 3.11、Python 3.12、Dashboard 服务镜像、固定模型 Job 镜像和 PostgreSQL 17 行为。依赖来自 `config/requirements/`，容器定义来自 `containers/`。修改时必须与本地命令和容器契约保持一致。
