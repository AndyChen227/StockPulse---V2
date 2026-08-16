# Topic Analysis and Representative Messages

> Status: explainable V1 implementation
>
> Topic version: `1:tsla-keywords-2026-08`

## Purpose

Sentiment shows direction but not cause. StockPulse topic analysis adds reviewable categories so the future Dashboard can explain whether a shift is associated with deliveries, margins, autonomy, regulation, competition, or another tracked theme.

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
