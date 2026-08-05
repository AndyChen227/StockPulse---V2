<div align="center">

# 📈 StockPulse

### AI-Powered Stock Sentiment Anomaly Monitor

**Monitor investor discussions · Detect sentiment shifts · Explain what changed**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Apify](https://img.shields.io/badge/Apify-Data%20Collection-FF9013?logo=apify&logoColor=white)](https://apify.com/)
[![Data Source](https://img.shields.io/badge/Data-Stocktwits-1DA1F2)](https://stocktwits.com/)
[![Status](https://img.shields.io/badge/Status-In%20Development-F4B400)](#project-status)
[![License](https://img.shields.io/badge/License-MIT-2EA44F)](LICENSE)

**English** · [简体中文](#简体中文)

</div>

---

## Overview

**StockPulse** is a cost-aware stock sentiment monitoring project that detects unusual changes in investor discussions.

Version 1 focuses exclusively on **Tesla (TSLA)**. Once per day, StockPulse collects TSLA-related posts from **Stocktwits** through **Apify**, classifies their sentiment, stores historical results, and compares current activity with a historical baseline.

> StockPulse does not try to predict stock prices. It asks a different question: **Is investor sentiment behaving unusually today—and what may be driving the change?**

## Project Goals

| Question | How StockPulse answers it |
|---|---|
| 💬 What are investors saying? | Analyze recent TSLA discussions on Stocktwits |
| 📊 Has sentiment changed? | Compare today's results with historical levels |
| 🚨 Is the change unusual? | Detect abnormal shifts in volume or sentiment |
| 🧠 What may have caused it? | Identify major topics and summarize representative posts |

## System Workflow

```mermaid
flowchart TD
    A["TSLA discussions on Stocktwits"] --> B["Apify data collection"]
    B --> C["Clean and deduplicate messages"]
    C --> D["AI sentiment and topic analysis"]
    D --> E["Historical database"]
    E --> F["Daily metrics and baseline comparison"]
    F --> G{"Anomaly detected?"}
    G -- No --> H["Save daily result"]
    G -- Yes --> I["Generate event summary"]
    I --> J["Send email alert"]
```

## V1 Scope

| Area | Decision |
|---|---|
| Monitored asset | **Tesla (TSLA)** only |
| Discussion source | **Stocktwits** |
| Collection method | **Apify Stocktwits scraper** |
| Schedule | Approximately **once per day** |
| Sentiment classes | Bullish · Neutral · Bearish |
| Main output | Daily metrics and anomaly alerts |
| Out of scope | Trading, price prediction, and financial advice |

## Data Model

### Collected fields

| Field | Description |
|---|---|
| `messageId` | Unique Stocktwits message ID used for deduplication |
| `createdAt` | Original publication time |
| `body` | Message text |
| `symbols` | Assets mentioned in the post |
| `stocktwitsSentiment` | Optional Bullish or Bearish label selected by the author |
| `username` | Author username |
| `followers` | Author follower count |
| `url` | Link to the original message |

### Generated fields

| Field | Description |
|---|---|
| `aiSentiment` | Bullish, Neutral, or Bearish classification |
| `aiConfidence` | Confidence score for the classification |
| `topic` | Main topic discussed in the message |
| `processed` | Whether analysis has completed |

Stocktwits sentiment and AI sentiment are kept separate. A Stocktwits label reflects what the author selected; the AI label is StockPulse's independent analysis, including posts whose original sentiment is missing.

## Daily Analysis and Anomaly Detection

Each run is planned to calculate metrics such as:

| Metric | Example |
|---|---:|
| New messages collected | 100 |
| Bullish posts | 47% |
| Neutral posts | 29% |
| Bearish posts | 24% |
| Daily sentiment score | +0.23 |
| Main topic | Robotaxi |

After enough history is available, StockPulse will look for:

- Sudden increases in discussion volume
- Significant bullish or bearish sentiment shifts
- Unusual changes in discussion topics
- Repeated messages and low-quality noise

Example alert:

```text
TSLA SENTIMENT ANOMALY

Discussion volume: +210% versus historical average
Bearish sentiment: 24% → 58%
Main topics: Robotaxi, FSD, regulatory investigation

Summary: Investor sentiment became significantly more negative,
with discussion concentrated around autonomous-driving regulation.
```

## Cost-Aware Design

Apify usage is a real project constraint, so V1 intentionally stays small:

- Monitor only one asset: **TSLA**
- Collect data only **once per day**
- Use `messageId` to prevent duplicate storage and processing
- Keep only the fields needed for analysis
- Track Apify usage and avoid unnecessary test runs
- Scale frequency or coverage only after the MVP is validated

## Planned Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application and data processing |
| Apify | Stocktwits data collection |
| Stocktwits | Investor-discussion data source |
| AI / NLP | Sentiment, topic, and summary generation |
| SQLite or another lightweight database | Historical storage for V1 |
| Docker | Reproducible application packaging |
| Google Cloud Run | Planned cloud execution |
| Google Cloud Scheduler | Planned daily scheduling |
| Gmail API | Planned anomaly email alerts |
| GitHub | Version control and documentation |

## Local Collection Commands

StockPulse separates free local commands from the command that starts a paid Actor run.

```powershell
# Install the tested dependencies.
python -m pip install -r requirements.txt

# Make the src package available in the current PowerShell session.
$env:PYTHONPATH = "src"

# Preview configuration. This does not contact Apify.
python -m stockpulse.main

# Explicitly start one cost-capped Actor run.
python -m stockpulse.main --collect

# Read an existing successful run without starting another Actor.
python -m stockpulse.main --resume-run YOUR_RUN_ID

# Show daily statistics stored in local SQLite. This does not contact Apify.
python -m stockpulse.main --stats
```

The real `.env`, raw JSON files, and SQLite database are excluded from Git. The current test configuration limits a run to **5 messages**, **5 minutes**, and **$0.05 maximum Actor charge**.

## Planned Architecture

```text
StockPulse/
├── src/
│   └── stockpulse/
│       ├── collector/
│       │   └── apify_client.py
│       ├── analyzer/
│       │   ├── sentiment.py
│       │   └── topics.py
│       ├── storage.py
│       ├── detection/
│       │   └── anomaly.py
│       ├── notification/
│       │   └── email.py
│       └── main.py
├── data/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

> This structure is a plan and may evolve during implementation.

## Roadmap

### Phase 0 — Research and Planning

- [x] Define the project goal and V1 scope
- [x] Select TSLA as the first monitored asset
- [x] Select Stocktwits as the data source
- [x] Select Apify as the collection platform
- [x] Run a successful Stocktwits scraping test
- [x] Retrieve and inspect real TSLA messages

### Phase 1 — Project Setup

- [x] Create the local Python project
- [x] Create a virtual environment
- [x] Add configuration and dependency files
- [x] Connect the local project to GitHub

### Phase 2 — Collection and Storage

- [x] Connect Python to Apify
- [x] Retrieve and parse TSLA messages
- [x] Validate required fields and handle errors
- [x] Deduplicate messages by `messageId`
- [x] Store raw messages and daily statistics

### Phase 3 — AI Analysis

- [ ] Classify Bullish, Neutral, and Bearish sentiment
- [ ] Generate confidence scores
- [ ] Extract major discussion topics
- [ ] Compare AI sentiment with author-selected labels
- [ ] Evaluate classification quality

### Phase 4 — Baseline and Detection

- [ ] Build a historical daily baseline
- [ ] Define anomaly thresholds
- [ ] Detect unusual volume and sentiment changes
- [ ] Reduce false and duplicate alerts

### Phase 5 — Summaries and Alerts

- [ ] Select representative messages
- [ ] Generate concise, evidence-based summaries
- [ ] Design and test email alerts
- [ ] Send alerts only when an anomaly is detected

### Phase 6 — Automation and Deployment

- [ ] Add logging, retry logic, and usage monitoring
- [ ] Package the application with Docker
- [ ] Deploy to Google Cloud Run
- [ ] Schedule one daily run
- [ ] Configure secrets and cost alerts

## Project Status

> 🚧 **Currently in active development**

```text
Completed: project planning, Python setup, and cost-capped Apify data collection
Current milestone: AI sentiment analysis
Next milestone: classify unlabeled messages as Bullish, Neutral, or Bearish
```

## Future Ideas

- Multi-stock and cryptocurrency monitoring
- X, Reddit, or other discussion sources
- Higher-frequency monitoring
- Historical sentiment dashboard
- Cross-platform sentiment comparison
- Sentiment and market-price correlation research
- Mobile or chat notifications

## Disclaimer

StockPulse is an educational and research project. It does **not** provide financial advice, investment recommendations, automated trading, or guaranteed price predictions. All outputs are informational only.

---

<a id="简体中文"></a>

<div align="center">

# 🇨🇳 StockPulse 中文介绍

[返回英文](#-stockpulse)

</div>

## 项目简介

**StockPulse** 是一个注重成本控制的股票舆情异常监控项目，用于发现投资者讨论中不同寻常的变化。

第一版只监控 **Tesla（TSLA）**。系统计划每天运行一次，通过 **Apify** 获取 **Stocktwits** 上与 TSLA 相关的帖子，分析情绪并保存历史结果，再将当天情况与历史基准进行比较。

> StockPulse 不预测股票价格。它关注的问题是：**今天的投资者情绪是否异常？可能是什么原因造成的？**

## 项目目标

| 问题 | StockPulse 的处理方式 |
|---|---|
| 💬 投资者在说什么？ | 分析 Stocktwits 上近期的 TSLA 讨论 |
| 📊 情绪是否变化？ | 将当天结果与历史水平比较 |
| 🚨 变化是否异常？ | 检测讨论量和情绪比例的异常波动 |
| 🧠 可能是什么原因？ | 提取主要话题并总结代表性帖子 |

## 系统流程

```mermaid
flowchart TD
    A["Stocktwits 上的 TSLA 讨论"] --> B["Apify 数据采集"]
    B --> C["数据清洗与去重"]
    C --> D["AI 情绪和话题分析"]
    D --> E["历史数据库"]
    E --> F["每日指标与历史基准比较"]
    F --> G{"检测到异常？"}
    G -- 否 --> H["保存当天结果"]
    G -- 是 --> I["生成事件摘要"]
    I --> J["发送邮件提醒"]
```

## 第一版范围

| 项目 | 决定 |
|---|---|
| 监控标的 | 只监控 **Tesla（TSLA）** |
| 讨论来源 | **Stocktwits** |
| 采集方式 | **Apify Stocktwits Scraper** |
| 运行频率 | 大约**每天一次** |
| 情绪分类 | 看多 · 中性 · 看空 |
| 主要输出 | 每日舆情指标与异常提醒 |
| 不包含 | 自动交易、股价预测和投资建议 |

## 数据设计

### 采集字段

| 字段 | 说明 |
|---|---|
| `messageId` | Stocktwits 帖子唯一 ID，用于去重 |
| `createdAt` | 原始发帖时间 |
| `body` | 帖子正文 |
| `symbols` | 帖子提到的股票或资产 |
| `stocktwitsSentiment` | 作者主动选择的 Bullish / Bearish 标签，可为空 |
| `username` | 作者用户名 |
| `followers` | 作者粉丝数量 |
| `url` | 原始帖子链接 |

### 系统生成字段

| 字段 | 说明 |
|---|---|
| `aiSentiment` | 看多、中性或看空 |
| `aiConfidence` | AI 情绪判断的置信度 |
| `topic` | 帖子的主要讨论话题 |
| `processed` | 是否已经完成分析 |

Stocktwits 用户标签与 AI 判断会分开保存。前者是作者自己的选择，后者是 StockPulse 对文字内容的独立分析，也可以处理原始情绪标签为空的帖子。

## 每日分析与异常检测

每次运行计划计算以下指标：

| 指标 | 示例 |
|---|---:|
| 新增帖子 | 100 |
| 看多 | 47% |
| 中性 | 29% |
| 看空 | 24% |
| 每日情绪分数 | +0.23 |
| 主要话题 | Robotaxi |

积累足够历史数据后，StockPulse 会重点检测：

- 讨论量突然上升
- 看多或看空情绪出现显著变化
- 讨论话题发生异常转移
- 重复内容和低质量噪声

## 成本控制

Apify 的使用成本是项目的重要限制，因此第一版会主动保持轻量：

- 只监控一个标的：**TSLA**
- 只在**每天运行一次**左右
- 使用 `messageId` 防止重复保存和分析
- 只保留分析所需字段
- 监控 Apify 用量，避免不必要的测试运行
- MVP 验证成功后，再考虑增加频率或标的数量

## 计划技术栈

| 技术 | 用途 |
|---|---|
| Python | 核心程序和数据处理 |
| Apify | Stocktwits 数据采集 |
| Stocktwits | 投资者讨论数据源 |
| AI / NLP | 情绪、话题和摘要分析 |
| SQLite 或其他轻量数据库 | 第一版历史数据存储 |
| Docker | 应用容器化 |
| Google Cloud Run | 计划中的云端运行环境 |
| Google Cloud Scheduler | 计划中的每日定时任务 |
| Gmail API | 计划中的异常邮件提醒 |
| GitHub | 版本管理和项目文档 |

## 本地采集命令

StockPulse 会把免费的本地命令与真正启动付费 Actor 的命令分开。

```powershell
# 安装经过测试的依赖
python -m pip install -r requirements.txt

# 让当前 PowerShell 会话能够找到 src 中的项目代码
$env:PYTHONPATH = "src"

# 预览配置，不连接 Apify
python -m stockpulse.main

# 明确启动一次带费用保护的 Actor Run
python -m stockpulse.main --collect

# 读取已经成功的 Run，不重新启动 Actor
python -m stockpulse.main --resume-run YOUR_RUN_ID

# 查看 SQLite 中的每日统计，不连接 Apify
python -m stockpulse.main --stats
```

真实 `.env`、原始 JSON 和 SQLite 数据库均不会上传到 Git。当前测试配置将单次运行限制为 **5 条消息**、**5 分钟**和 **最高 0.05 美元 Actor 费用**。

## 开发路线

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 明确目标、选择数据源、完成真实抓取测试 | ✅ 已完成 |
| Phase 1 | 建立本地 Python 项目并连接 GitHub | ✅ 已完成 |
| Phase 2 | 使用 Python 采集、清洗、去重并保存数据 | ✅ 已完成 |
| Phase 3 | AI 情绪与话题分析 | ⏳ 下一步 |
| Phase 4 | 建立历史基准并检测异常 | ⏳ 待开始 |
| Phase 5 | 生成事件摘要和邮件提醒 | ⏳ 待开始 |
| Phase 6 | 自动化、Docker 和云端部署 | ⏳ 待开始 |

## 当前进度

> 🚧 **项目正在开发中**

```text
已完成：项目规划、Python 搭建和带费用保护的 Apify 数据采集
当前阶段：AI 情绪分析
下一阶段：将未标注帖子分类为看多、中性或看空
```

## 后续扩展

- 多股票与加密货币监控
- 接入 X、Reddit 或其他讨论平台
- 提高监控频率
- 历史情绪可视化 Dashboard
- 多平台情绪对比
- 舆情与市场价格的相关性研究
- 手机或聊天软件通知

## 免责声明

StockPulse 是一个学习与研究项目，不提供投资建议、自动交易或有保证的价格预测。所有分析结果仅供信息参考。

---

<div align="center">

### 🚀 StockPulse

**Detect the signal before it gets lost in the noise.**

</div>
