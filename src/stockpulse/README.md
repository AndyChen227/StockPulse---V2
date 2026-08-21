# StockPulse package / StockPulse 应用包

[English](#english) · [简体中文](#简体中文)

## English

This package contains all runtime behavior:

```text
collector → validation → repository → sentiment/topics
          → metrics/anomaly → notifications → API/Dashboard
```

`main.py` is the CLI entry point, `api.py` is the web entry point, and
`pipeline.py` orchestrates the scheduled Job. Read the
[repository guide](../../docs/reference/repository-guide.md) for every module's
responsibility.

Keep external-source adapters inside `collector/` and browser assets inside
`web/`. Do not place secrets, generated data, or model files in the package.

---

## 简体中文

本应用包包含全部运行逻辑：

```text
采集 → 校验 → 仓库 → 情绪/话题
     → 指标/异常 → 通知 → API/Dashboard
```

`main.py` 是命令行入口，`api.py` 是 Web 入口，`pipeline.py` 负责编排定时
Job。每个模块的职责见[仓库指南](../../docs/reference/repository-guide.md)。

外部来源适配器只放在 `collector/`，浏览器资源只放在 `web/`。不要在应用包中
保存 Secret、生成数据或模型文件。
