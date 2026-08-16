# Sentiment Evaluation

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
