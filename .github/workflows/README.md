# Continuous integration / 持续集成

[English](#english) · [简体中文](#简体中文)

## English

`tests.yml` is the repository's single CI workflow. It protects five release
paths: Python 3.11, Python 3.12, the Dashboard service image, the pinned-model
Job image, and the PostgreSQL 17 integration contract. Dependencies come from
`config/requirements/`; container definitions come from `containers/`.

Keep workflow changes aligned with the local test commands and the two
production container contracts. CI may validate code and build artifacts, but
it never receives production credentials or deploys infrastructure.

---

## 简体中文

`tests.yml` 是仓库唯一的 CI 工作流，保护五条发布路径：Python 3.11、
Python 3.12、Dashboard 服务镜像、固定模型 Job 镜像，以及 PostgreSQL 17
集成契约。依赖来自 `config/requirements/`，容器定义来自 `containers/`。

修改工作流时，必须与本地测试命令和两个生产容器契约保持一致。CI 只验证
代码与构建产物，不接收生产凭证，也不会部署基础设施。
