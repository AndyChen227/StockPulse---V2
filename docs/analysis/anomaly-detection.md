# Anomaly Detection / 异常检测

[English](#english) · [简体中文](#简体中文)

---

# English

> Status: experimental, versioned, replayable, and connected to production notifications; thresholds remain provisional

## Purpose

StockPulse compares each daily AI metric with history that was available before
that date. The result is explainable and stored independently from notification
delivery, so the Dashboard can show normal days, insufficient-history days, and
anomalies without implying that every evaluation sent an alert.

## Version 1 baseline

The default detector uses:

- up to 28 prior calendar days
- at least 7 prior days before evaluating thresholds
- the median prior message count and median prior sentiment score
- at least 5 current messages before emitting an anomaly
- a volume signal when current volume is at least 2.0 times baseline
- a bullish or bearish signal when sentiment moves by at least 0.35
- a topic-shift signal when a topic has at least 3 current assignments and its
  share of all assignments rises by at least 25 percentage points versus its
  median prior daily share

The median is used to reduce the influence of an earlier spike. Every threshold
is encoded into `detector_version`; changing behavior therefore creates a new
version and a new replay identity.

## Result states

| Status | Meaning |
|---|---|
| `insufficient_history` | Fewer than seven prior days are available; no alert is allowed |
| `normal` | Enough history exists, but no threshold was crossed |
| `anomaly` | One or more versioned thresholds were crossed |

One signal produces medium severity and two or more simultaneous signals produce high
severity. Severity is a display and routing aid, not a statement about investment
risk or factual truth.

## Replay and duplicate prevention

Replay evaluates each date using only earlier dates, preventing future data from
leaking into its baseline. A SHA-256 fingerprint identifies the date, sentiment
analysis version, topic version, and full detector version. SQLite stores each fingerprint once,
so retrying a job cannot create duplicate evaluations or future duplicate alerts.

```powershell
$env:PYTHONPATH = "src"

# Evaluate only the latest locally stored day.
python -m stockpulse.main --detect-anomalies

# Rebuild all versioned historical evaluations without contacting Apify.
python -m stockpulse.main --replay-anomalies

# Inspect complete stored evaluation history.
python -m stockpulse.main --anomalies
```

## Production notification state and limitations

- thresholds are engineering defaults and need calibration on representative history
- missing collection days are not imputed
- the current rule detects volume spikes, not unusually low volume
- topic-share counts are multi-label assignments, not unique-message market share
- message duplication and coordinated low-quality content need a separate signal
- detailed anomaly email delivery is enabled with durable duplicate suppression;
  a separate test mode verifies the template without creating an incident

Daily-summary, anomaly-test, and failure-test delivery were verified during V1
production acceptance. As representative twice-daily history accumulates,
replay results should still be manually reviewed, false-positive and
missed-event rates should be recorded, and notification signal/cooldown behavior
should be tuned independently from evaluation storage.

---

# 简体中文

> 状态：实验性、版本化、可重放，并已连接生产通知；阈值仍为临时工程基线

## 用途

StockPulse 会把每天的 AI 指标与该日期之前已经存在的历史数据比较。评估结果
具有明确解释，并与通知投递分开存储，因此 Dashboard 可以区分正常日期、历史
不足日期和异常日期，而不会让用户误以为每次评估都发送了告警。

## V1 基线

默认检测器使用：

- 最多 28 个此前自然日；
- 至少拥有 7 个此前日期后才评估阈值；
- 此前消息量中位数和此前情绪分数中位数；
- 当前至少 5 条消息时才允许产生异常；
- 当前讨论量至少为基线 2.0 倍时产生讨论量信号；
- 情绪变化至少为 0.35 时产生偏多或偏空信号；
- 某话题当前至少有 3 次分配，且占全部话题分配的比例比此前每日占比中位数
  上升至少 25 个百分点时，产生话题变化信号。

使用中位数可以降低早期尖峰的影响。所有阈值都编码进
`detector_version`；修改行为会创建新版本和新的重放身份，不会静默改写旧结果。

## 结果状态

| 状态 | 含义 |
|---|---|
| `insufficient_history` | 此前少于 7 天；不允许发送告警 |
| `normal` | 历史足够，但没有跨越任何阈值 |
| `anomaly` | 一个或多个版本化阈值被触发 |

一个信号对应中等严重程度，两个或更多同时出现的信号对应高严重程度。严重程度
只用于展示和通知路由，不代表投资风险，也不表示消息内容为事实。

## 重放与重复预防

重放每个日期时只使用更早日期，避免未来数据泄漏进历史基线。SHA-256 指纹
组合日期、情绪分析版本、话题版本和完整检测器版本。SQLite 或 PostgreSQL
只保存一次相同指纹，因此 Job 重试不会产生重复评估或后续重复告警。

```powershell
$env:PYTHONPATH = "src"

# 只评估本地保存的最新日期。
python -m stockpulse.main --detect-anomalies

# 不联系 Apify，重建所有版本化历史评估。
python -m stockpulse.main --replay-anomalies

# 查看完整的已保存评估历史。
python -m stockpulse.main --anomalies
```

## 生产通知状态与限制

- 阈值是工程默认值，需要在有代表性的历史上校准；
- 不会为缺失的采集日期填充数据；
- 当前规则检测讨论量尖峰，不检测异常低讨论量；
- 话题占比使用多标签分配次数，不等同于独立消息的市场份额；
- 消息重复和协同低质量内容需要单独信号；
- 详细异常邮件已启用持久化去重；独立测试模式可以验证模板而不创建事故。

每日摘要、异常 TEST 和失败 TEST 邮件均已在 V1 生产验收期间验证。随着每天
两次的代表性历史逐步积累，仍应人工复核重放结果、记录误报与漏报，并把通知
信号及冷却时间的调优与评估存储分开进行。
