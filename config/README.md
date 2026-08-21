# Project configuration / 项目配置

[English](#english) · [简体中文](#简体中文)

## English

This directory groups setup inputs that are safe to version. `env.example`
documents supported environment variables without real values, while
`requirements/` contains locked dependency sets for the base, AI, and
PostgreSQL runtimes. Real `.env` files and credentials stay untracked at the
repository root.

---

## 简体中文

本目录集中保存可以安全纳入版本控制的配置输入。`env.example` 说明支持的
环境变量，但不包含真实值；`requirements/` 保存基础、AI 和 PostgreSQL 三组
锁定依赖。真实 `.env` 与凭证必须留在仓库根目录，并保持不受 Git 跟踪。
