# StockPulse package / StockPulse 应用包

**English:** This package contains all runtime behavior. The main flow is `collector → validation → repository → sentiment/topics → metrics/anomaly → notifications → API/Dashboard`. `main.py` is the CLI entry, `api.py` is the web entry, and `pipeline.py` is the scheduled Job orchestration. Read the [repository guide](../../docs/reference/repository-guide.md) for every module's responsibility.

**中文：** 本包包含全部运行逻辑。主要流程是“采集 → 校验 → 仓库 → 情绪/话题 → 指标/异常 → 通知 → API/Dashboard”。`main.py` 是命令行入口，`api.py` 是 Web 入口，`pipeline.py` 是定时 Job 编排入口。每个模块的职责见[仓库指南](../../docs/reference/repository-guide.md)。

Keep external source adapters inside `collector/` and browser assets inside `web/`. Do not place secrets, generated data, or model files in the package.

外部来源适配器只放在 `collector/`，浏览器资源只放在 `web/`。不要在应用包中保存 Secret、生成数据或模型文件。
