# Topic Analysis and Representative Messages / 话题分析与代表消息

[English](#english) · [简体中文](#简体中文)

---

# English

> Status: explainable V1 implementation
>
> Topic version: `1:tsla-keywords-2026-08`

## Purpose

Sentiment shows direction but not cause. StockPulse topic analysis adds reviewable categories so the Dashboard can explain whether a shift is associated with deliveries, margins, autonomy, regulation, competition, or another tracked theme.

Topic output is multi-label and stored separately from messages and sentiment. Changing the taxonomy creates a new topic version; it never silently rewrites earlier results.

## V1 taxonomy

| Topic | Example concepts |
|---|---|
| Deliveries & Demand | deliveries, orders, demand, inventory, discounts |
| Earnings & Margins | earnings, revenue, margins, cash flow, guidance |
| Price Action | targets, support, resistance, rallies, selloffs, squeezes |
| Autonomy & FSD | FSD, Autopilot, self-driving, autonomy |
| Robotaxi | Robotaxi, Cybercab, ride-hailing |
| Energy | Megapack, Powerwall, solar, energy storage and margins |
| Regulation & Safety | regulation, investigations, recalls, safety, approvals |
| Competition | competitors, market share, BYD, Rivian, legacy automakers |
| Manufacturing & Supply | factories, production, supply chains, batteries, ramps |
| Leadership & Governance | Elon Musk, executives, board, governance, shareholder meeting |
| Other | no tracked term matched |

Every stored assignment includes:

- topic name
- normalized score relative to the strongest topic in that message
- exact matched terms
- rank within the message
- topic analysis version
- analysis timestamp

The current implementation returns at most three topics per message. Phrase and word boundaries prevent accidental substring matches such as `board` inside `boardwalk`.

## Representative-message rules

StockPulse does not generate or paraphrase representative posts. It selects stored source messages deterministically, preserving body text and the original URL.

Candidates for one exact topic are ranked by:

1. topic-match score
2. AI sentiment confidence
3. bounded author follower count
4. publication time
5. message ID as a stable tie-breaker

This is a relevance heuristic, not a credibility score. Follower count cannot establish truth or quality, and the Dashboard must not present selected messages as verified facts.

## Local workflow

Topic analysis requires stored messages with the current sentiment analysis version.

```powershell
$env:PYTHONPATH = "src"

# Analyze only messages missing the current topic version.
python -m stockpulse.main --analyze-topics

# Force a bounded replacement for the current topic version.
python -m stockpulse.main --reanalyze-topics --topic-limit 100

# Inspect topic counts.
python -m stockpulse.main --topic-stats

# Inspect UTC date-bucketed topic and sentiment metrics for historical charts.
python -m stockpulse.main --topic-history

# Inspect up to three representative messages and their source links.
python -m stockpulse.main --representatives "Robotaxi"
```

These commands are local and never contact Apify.

The history query returns one row per UTC date and topic. Each row includes the
message count, Bullish/Neutral/Bearish counts, average AI confidence, average
topic score, and a `-1.0` to `1.0` sentiment score. The repository contract also
supports optional inclusive start and end dates so the future API can expose
bounded chart ranges without loading the full history.

## Known limitations and next validation

V1 is intentionally transparent but has important limitations:

- keyword rules miss synonyms and new narratives that are not in the taxonomy
- a term match does not guarantee that the term is the main subject
- negation and quoted text are not interpreted at the topic layer
- taxonomy coverage has not yet been measured on a representative real-message sample
- `Other` may hide emerging topics
- representative ranking favors confident, on-topic, followed, recent messages but does not measure factual reliability

Before topic output drives anomaly explanations, StockPulse should review a labeled sample, measure per-topic precision and recall, inspect `Other`, and version every taxonomy adjustment.

---

# 简体中文

> 状态：可解释的 V1 实现
>
> 话题版本：`1:tsla-keywords-2026-08`

## 用途

情绪只说明方向，不说明原因。StockPulse 话题分析使用可以人工复核的类别，
帮助 Dashboard 解释变化是否与交付、利润率、自动驾驶、监管、竞争或其他主题
有关。

话题输出支持多标签，并与消息和情绪结果分开存储。修改分类体系会创建新的
话题版本，绝不会静默改写旧结果。

## V1 话题体系

| 话题 | 示例概念 |
|---|---|
| Deliveries & Demand | 交付、订单、需求、库存、折扣 |
| Earnings & Margins | 财报、收入、利润率、现金流、指引 |
| Price Action | 目标价、支撑、阻力、上涨、抛售、轧空 |
| Autonomy & FSD | FSD、Autopilot、自动驾驶、自治 |
| Robotaxi | Robotaxi、Cybercab、网约车 |
| Energy | Megapack、Powerwall、太阳能、储能和利润率 |
| Regulation & Safety | 监管、调查、召回、安全、批准 |
| Competition | 竞争对手、市场份额、BYD、Rivian、传统车企 |
| Manufacturing & Supply | 工厂、产量、供应链、电池、爬坡 |
| Leadership & Governance | Elon Musk、高管、董事会、治理、股东大会 |
| Other | 没有匹配任何受跟踪词语 |

每条已保存话题分配都包含：

- 话题名称；
- 相对于该消息最强话题的标准化分数；
- 精确命中的词语；
- 该话题在消息中的排名；
- 话题分析版本；
- 分析时间戳。

当前实现每条消息最多返回三个话题。短语和单词边界可避免把 `boardwalk` 中的
`board` 等子字符串误判为话题命中。

## 代表消息规则

StockPulse 不生成或改写代表帖子，而是确定性地选择已保存的原始消息，保留
正文和原始 URL。

一个精确话题的候选消息按以下顺序排序：

1. 话题匹配分数；
2. AI 情绪置信度；
3. 有上限处理的作者关注者数量；
4. 发布时间；
5. 作为稳定最终排序键的消息 ID。

这是相关性启发式规则，不是可信度评分。关注者数量不能证明内容真实或优质，
Dashboard 也不得把选中的消息当成已经核实的事实。

## 本地工作流

话题分析需要已经使用当前情绪版本处理过的消息。

```powershell
$env:PYTHONPATH = "src"

# 只分析缺少当前话题版本的消息。
python -m stockpulse.main --analyze-topics

# 在固定上限内替换当前话题版本。
python -m stockpulse.main --reanalyze-topics --topic-limit 100

# 查看话题计数。
python -m stockpulse.main --topic-stats

# 查看按 UTC 日期分组的话题与情绪指标。
python -m stockpulse.main --topic-history

# 查看最多三条代表消息及其来源链接。
python -m stockpulse.main --representatives "Robotaxi"
```

这些命令只在本地工作，永远不会联系 Apify。

历史查询按 UTC 日期和话题各返回一行。每行包含消息数、
Bullish/Neutral/Bearish 数、平均 AI 置信度、平均话题分数，以及从 `-1.0`
到 `1.0` 的情绪分数。仓库契约还支持可选的包含式起止日期，让 API 可以读取
有界图表范围，而不必加载全部历史。

## 已知限制与下一步验证

V1 刻意保持透明，但有以下重要限制：

- 关键词规则会漏掉分类体系中没有的同义词和新叙事；
- 命中词语不代表该词一定是消息的主要主题；
- 话题层不会理解否定或引用文本；
- 尚未在有代表性的真实消息样本上测量体系覆盖率；
- `Other` 可能隐藏正在出现的新话题；
- 代表消息排序偏向置信度高、话题相关、作者关注者多且较新的消息，但不衡量
  事实可靠性。

在使用话题输出解释异常前，应复核标注样本、测量逐话题 Precision 和 Recall、
检查 `Other`，并为每次分类体系调整创建新版本。
