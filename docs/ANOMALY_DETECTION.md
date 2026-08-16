# Anomaly Detection

> Status: experimental, versioned, and suitable for replay; not yet calibrated for production alerts

## Purpose

StockPulse compares each daily AI metric with history that was available before
that date. The result is explainable and stored independently from future email
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

The median is used to reduce the influence of an earlier spike. Every threshold
is encoded into `detector_version`; changing behavior therefore creates a new
version and a new replay identity.

## Result states

| Status | Meaning |
|---|---|
| `insufficient_history` | Fewer than seven prior days are available; no alert is allowed |
| `normal` | Enough history exists, but no threshold was crossed |
| `anomaly` | One or more versioned thresholds were crossed |

One signal produces medium severity and two simultaneous signals produce high
severity. Severity is a display and routing aid, not a statement about investment
risk or factual truth.

## Replay and duplicate prevention

Replay evaluates each date using only earlier dates, preventing future data from
leaking into its baseline. A SHA-256 fingerprint identifies the date, sentiment
analysis version, and full detector version. SQLite stores each fingerprint once,
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

## Limitations before production alerts

- thresholds are engineering defaults and need calibration on representative history
- missing collection days are not imputed
- the current rule detects volume spikes, not unusually low volume
- topic shifts do not yet contribute to anomaly decisions
- message duplication and coordinated low-quality content need a separate signal
- no email is sent in this stage

Before enabling notifications, replay results should be manually reviewed, false
positive and missed-event rates should be recorded, and alert cooldown behavior
should be tested independently from evaluation storage.
