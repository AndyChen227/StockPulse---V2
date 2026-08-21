# Local runtime data / 本地运行数据

[English](#english) · [简体中文](#简体中文)

## English

StockPulse writes the local SQLite database to `data/stockpulse.db` and raw
collection snapshots to `data/raw/`. Git ignores both runtime artifacts; they
are not the production cloud source of truth. Keep `.gitkeep` so the directory
exists in a fresh clone. Never commit collected messages, databases, or
credentials.

---

## 简体中文

StockPulse 默认把本地 SQLite 数据库写入 `data/stockpulse.db`，把原始采集
快照写入 `data/raw/`。这两类运行文件已被 Git 忽略，也不是生产云端的事实
来源。`.gitkeep` 用于保证全新克隆后目录仍然存在。绝不要提交采集消息、
数据库或凭证。
