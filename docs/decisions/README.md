# Architecture decision records / 架构决策记录

[English](#english) · [简体中文](#简体中文)

## English

Architecture decision records (ADRs) preserve choices that should remain
understandable after the implementation changes. Use sequential names such as
`0002-short-decision-name.md` and record context, the decision, alternatives,
consequences, and status. Do not rewrite accepted history; supersede it with a
new ADR.

Current record: [`0001-cloud-datastore.md`](0001-cloud-datastore.md) explains
why Cloud SQL for PostgreSQL is the production source of truth.

---

## 简体中文

架构决策记录（ADR）用于保存即使实现变化后仍需理解的重要选择。文件按
`0002-short-decision-name.md` 形式顺序编号，并记录背景、决策、备选方案、
后果和状态。不要改写已接受的历史；应创建新的 ADR 取代旧决策。

当前记录：[`0001-cloud-datastore.md`](0001-cloud-datastore.md) 说明了为什么
生产事实来源选择 Cloud SQL for PostgreSQL。
