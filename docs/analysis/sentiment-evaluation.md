# Sentiment Evaluation / 情绪评估

[English](#english) · [简体中文](#简体中文)

---

# English

> Status: provisional finance-specific baseline
>
> Dataset: `evaluations/finance_sentiment_v1.jsonl`
>
> Last evaluated: 2026-08-16

## Purpose

The current model was trained for general social-media sentiment, while StockPulse needs financial direction. A positive-sounding sentence is not always Bullish, and a sentence containing negative words is not always Bearish. This evaluation provides a reproducible check before model output is trusted by anomaly detection or the Dashboard.

This benchmark measures **direction expressed by the complete message**:

- `Bullish`: the author expresses a positive investment, business, demand, price, or forward outlook
- `Neutral`: the message is factual, balanced, uncertain, a question, or has no clear directional conclusion
- `Bearish`: the author expresses a negative investment, business, demand, price, risk, or forward outlook

Labels describe message direction, not whether a statement is factually correct and not whether the stock will rise or fall.

## Dataset V1

The first tracked set contains 36 original, manually written examples:

- 12 Bullish
- 12 Neutral
- 12 Bearish
- coverage of fundamentals, demand, operations, analyst actions, regulation, competition, price observations, mixed evidence, negation, uncertainty, and trading language

These sentences are synthetic and contain no private data. They are intentionally small enough for line-by-line review. This makes V1 reproducible, but it is not representative enough to establish production quality.

## Pinned-model baseline

Model: `cardiffnlp/twitter-roberta-base-sentiment-latest`

Revision: `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`

Confidence threshold: `0.60`

| Metric | Result |
|---|---:|
| Examples | 36 |
| Correct | 32 |
| Accuracy | 88.9% |
| Macro F1 | 89.2% |
| Average confidence | 75.0% |
| Low-confidence predictions | 5 |
| Low-confidence accuracy | 80.0% |
| Higher-confidence accuracy | 90.3% |

Per-label results:

| Expected label | Precision | Recall | F1 | Main error |
|---|---:|---:|---:|---|
| Bullish | 100.0% | 83.3% | 90.9% | 2 predicted Neutral |
| Neutral | 75.0% | 100.0% | 85.7% | absorbed 4 directional examples |
| Bearish | 100.0% | 83.3% | 90.9% | 2 predicted Neutral |

All four errors were directional messages classified as Neutral:

- strong demand and a growing backlog
- a possible short squeeze if guidance holds
- a Sell downgrade with a lower price target
- competitors gaining share while Tesla discounts vehicles

Three of the four errors were above the current `0.60` confidence threshold. The threshold alone therefore cannot identify every mistake.

The machine-readable baseline, including the exact dataset hash and every error, is stored in `evaluations/results/twitter-roberta-v1.json`.

## Finance-model comparison

The same 36 examples were evaluated with [ProsusAI FinBERT](https://huggingface.co/ProsusAI/finbert), pinned to revision `4556d13015211d73dccd3fdd39d39232506f3e43`. Its model card describes continued training on a financial corpus and fine-tuning with Financial PhraseBank. The associated [FinBERT paper](https://arxiv.org/abs/1908.10063) motivates domain-specific language modeling for financial sentiment.

| Model | Accuracy | Macro F1 | Direction reversals | Errors |
|---|---:|---:|---:|---:|
| Twitter-RoBERTa baseline | **88.9%** | **89.2%** | **0** | **4** |
| ProsusAI FinBERT | 69.4% | 69.5% | 2 | 11 |

FinBERT performed worse on this social-investor benchmark. It classified five Neutral examples as Bearish and produced two severe direction reversals: one Bullish example became Bearish and one Bearish example became Bullish. Its average confidence was higher despite lower accuracy, so confidence alone did not make it safer.

Decision: **do not replace the current adapter with ProsusAI FinBERT**. Keep Twitter-RoBERTa as the experimental baseline while expanding the evaluation set. This is a benchmark-specific decision, not a claim that FinBERT is generally inferior; its training domain is closer to formal financial text than Stocktwits-style language.

The FinBERT model card does not currently declare a license in its metadata. Production use would require license clarification even if a later benchmark favored it. The complete comparison output is stored in `evaluations/results/prosus-finbert-v1.json`.

## Interpretation

The pinned model is a useful experimental baseline. On this set, it did not reverse any Bullish example to Bearish or any Bearish example to Bullish. Its observed failure mode was under-detection: financially directional language was sometimes treated as Neutral.

This result does **not** establish production readiness because:

- 36 examples are too few for a stable estimate
- examples are synthetic rather than sampled from real Stocktwits distribution
- one author created the initial labels, so inter-annotator agreement is unknown
- sarcasm, emojis, incomplete posts, ticker slang, spam, and rapidly changing narratives need broader coverage
- model selection decisions should use a held-out set that is not repeatedly tuned against

## Acceptance gate before anomaly detection

Before sentiment drives anomaly alerts, StockPulse should:

1. expand to at least 150 reviewed examples sampled across the required categories
2. include de-identified or safely stored real-message patterns where permitted
3. have a second human review ambiguous and mixed-direction labels
4. separate a final held-out test set from development examples
5. define minimum per-label recall and calibration targets
6. compare additional finance-oriented or social-finance alternatives if their licensing and maintenance are acceptable
7. document every rule or calibration change through a new analysis version

Until that gate is met, Dashboard sentiment should be labeled experimental and should display model version and confidence context.

## Reproduce

Install the optional AI dependencies, then run:

```powershell
$env:PYTHONPATH = "src"
python -m stockpulse.evaluation `
  --json-output evaluations/results/twitter-roberta-v1.json
```

The first uncached run may download the public model. This command never contacts Apify and cannot spend Apify credits.

---

# 简体中文

> 状态：临时的金融语境基线
>
> 数据集：`evaluations/finance_sentiment_v1.jsonl`
>
> 最近评估：2026-08-16

## 用途

当前模型针对通用社交媒体情绪训练，但 StockPulse 需要识别金融方向。语气正面
的句子不一定偏多，包含负面词的句子也不一定偏空。本评估提供一套可复现检查，
用于判断模型输出是否适合进入异常检测和 Dashboard。

基准衡量的是**完整消息表达的方向**：

- `Bullish`：作者表达正面的投资、业务、需求、价格或未来观点；
- `Neutral`：消息属于事实陈述、平衡观点、不确定表达、问题，或没有明确方向；
- `Bearish`：作者表达负面的投资、业务、需求、价格、风险或未来观点。

标签只描述消息方向，不判断陈述是否真实，也不预测股票会上涨还是下跌。

## V1 数据集

第一版受 Git 跟踪的数据集包含 36 条人工编写的原创样例：

- 12 条 Bullish；
- 12 条 Neutral；
- 12 条 Bearish；
- 覆盖基本面、需求、运营、分析师行动、监管、竞争、价格观察、混合证据、
  否定、不确定性和交易语言。

这些句子是合成数据，不包含私人信息。规模刻意保持在可以逐行审查的范围内，
因此 V1 可复现，但不足以证明生产质量。

## 固定模型基线

模型：`cardiffnlp/twitter-roberta-base-sentiment-latest`

Revision：`3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`

置信度阈值：`0.60`

| 指标 | 结果 |
|---|---:|
| 样例数 | 36 |
| 正确数 | 32 |
| 准确率 | 88.9% |
| Macro F1 | 89.2% |
| 平均置信度 | 75.0% |
| 低置信度预测 | 5 |
| 低置信度准确率 | 80.0% |
| 较高置信度准确率 | 90.3% |

逐标签结果：

| 期望标签 | Precision | Recall | F1 | 主要错误 |
|---|---:|---:|---:|---|
| Bullish | 100.0% | 83.3% | 90.9% | 2 条被预测为 Neutral |
| Neutral | 75.0% | 100.0% | 85.7% | 吸收了 4 条有方向样例 |
| Bearish | 100.0% | 83.3% | 90.9% | 2 条被预测为 Neutral |

四个错误都是有方向的消息被判为 Neutral：

- 强劲需求与不断增长的积压订单；
- 如果指引成立，可能出现轧空；
- Sell 下调评级并降低目标价；
- 竞争对手取得份额，而 Tesla 通过折扣销售车辆。

四个错误中有三个高于当前 `0.60` 阈值，因此单靠置信度阈值无法识别所有错误。
包含精确数据集哈希和每条错误的机器可读基线保存在
`evaluations/results/twitter-roberta-v1.json`。

## 金融模型对比

同一组 36 条样例也使用固定 revision
`4556d13015211d73dccd3fdd39d39232506f3e43` 的
[ProsusAI FinBERT](https://huggingface.co/ProsusAI/finbert) 进行了评估。模型卡
说明它在金融语料上继续训练，并使用 Financial PhraseBank 微调；对应的
[FinBERT 论文](https://arxiv.org/abs/1908.10063) 解释了金融领域语言模型的
动机。

| 模型 | 准确率 | Macro F1 | 方向反转 | 错误数 |
|---|---:|---:|---:|---:|
| Twitter-RoBERTa 基线 | **88.9%** | **89.2%** | **0** | **4** |
| ProsusAI FinBERT | 69.4% | 69.5% | 2 | 11 |

FinBERT 在这组社交投资者基准上表现更差：它把五条 Neutral 判为 Bearish，
并产生两次严重方向反转。尽管准确率更低，它的平均置信度更高，说明高置信度
本身并不等于更安全。

决策：**不使用 ProsusAI FinBERT 替换当前适配器**。继续把 Twitter-RoBERTa
作为实验基线，同时扩充评估集。这只是针对当前基准的结论，并不表示 FinBERT
普遍更差；它更接近正式金融文本，而不是 Stocktwits 风格语言。

FinBERT 模型卡元数据目前没有声明许可证。即使未来基准支持它，在生产使用前
仍需澄清许可证。完整结果保存在
`evaluations/results/prosus-finbert-v1.json`。

## 结果解读

固定模型是一个有价值的实验基线。在这组数据中，它没有把 Bullish 反转成
Bearish，也没有把 Bearish 反转成 Bullish；主要失败模式是漏检，即把有金融
方向的表达当成 Neutral。

该结果**不能证明生产就绪**，原因包括：

- 36 条样例不足以形成稳定估计；
- 样例是合成文本，不代表真实 Stocktwits 分布；
- 初始标签由一人创建，未知标注者间一致性；
- 讽刺、Emoji、残缺帖子、Ticker 俚语、垃圾内容和快速变化叙事覆盖不足；
- 模型选择应使用没有被重复调参污染的保留测试集。

## 异常检测前的验收门槛

在让情绪直接驱动异常告警前，StockPulse 应：

1. 扩充到至少 150 条经过复核、覆盖所需类别的样例；
2. 在许可范围内加入去标识化或安全保存的真实消息模式；
3. 由第二位人工复核含糊和混合方向标签；
4. 把最终保留测试集与开发样例分开；
5. 定义逐标签最低召回率和校准目标；
6. 在许可证与维护状态可接受时，对比更多金融或社交金融候选模型；
7. 通过新的分析版本记录每次规则或校准变化。

在达到门槛前，Dashboard 情绪应标记为实验性，并显示模型版本与置信度背景。

## 复现

安装可选 AI 依赖，然后运行：

```powershell
$env:PYTHONPATH = "src"
python -m stockpulse.evaluation `
  --json-output evaluations/results/twitter-roberta-v1.json
```

第一次没有缓存的运行可能下载公开模型。该命令不会联系 Apify，也不会消耗
Apify 额度。
