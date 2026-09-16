# FOMC Event Study — SPY & TLT around FOMC decisions

_Generated 2026-06-23 · price source: ported CSVs + yfinance backfill · returns use raw close._

**Event universe:** 65 scheduled Powell-era FOMC days (2018-03-21 → 2026-04-29), plus 2 flagged COVID emergency decisions (excluded from aggregates), plus 1 Warsh meeting(s).

## Powell era — SPY (scheduled meetings)

| Window | n | Mean | Median | Hit rate (up) | Std | Min / Max |
|---|---|---|---|---|---|---|
| Pre-5d run-up (t-5→t-1) | 65 | +0.50% | +0.92% | 68% | 2.20% | -10.1% / +5.2% |
| Decision day (t-1→t) | 65 | +0.09% | -0.01% | 46% | 1.19% | -3.0% / +3.0% |
| Post +1d | 65 | -0.17% | -0.01% | 49% | 1.31% | -5.8% / +1.9% |
| Post +3d | 65 | -0.26% | +0.20% | 52% | 2.33% | -7.2% / +3.9% |
| Post +5d | 65 | -0.08% | -0.20% | 46% | 2.44% | -8.5% / +5.5% |

## Powell era — TLT (scheduled meetings)

| Window | n | Mean | Median | Hit rate (up) | Std | Min / Max |
|---|---|---|---|---|---|---|
| Pre-5d run-up (t-5→t-1) | 65 | -0.32% | -0.15% | 48% | 1.56% | -5.5% / +2.8% |
| Decision day (t-1→t) | 65 | +0.25% | +0.17% | 60% | 0.83% | -1.6% / +2.3% |
| Post +1d | 65 | +0.04% | +0.07% | 57% | 1.13% | -2.7% / +2.3% |
| Post +3d | 65 | -0.28% | -0.15% | 46% | 1.85% | -4.2% / +4.5% |
| Post +5d | 65 | -0.27% | -0.17% | 48% | 2.17% | -5.0% / +5.4% |

## Relationships (Powell, scheduled)

- **Pre-FOMC drift:** mean SPY run-up into the decision = +0.50% (hit 68%); mean decision-day SPY = +0.09%.
- **Reversal check:** corr(SPY pre-5d, SPY post-5d) = -0.097; corr(SPY decision-day, SPY post-5d) = -0.149.
- **Stock/bond co-move on decision day:** corr(SPY, TLT) = 0.105.
- **Decision-day color counts (SPY×TLT sign):** {'Blue': 19, 'Red': 16, 'Orange': 10, 'Green': 20} (Green=both up, Orange=stocks up/bonds down, Blue=stocks down/bonds up, Red=both down).

## Conditional post-5d (Powell, scheduled)

| Condition on decision day | SPY post-5d mean (hit) | TLT post-5d mean (hit) |
|---|---|---|
| SPY fell on decision day | +0.08% (51%, n=35) | -0.28% (49%, n=35) |
| SPY rose on decision day | -0.26% (40%, n=30) | -0.25% (47%, n=30) |
| TLT rose on decision day | -0.29% (44%, n=39) | -0.55% (38%, n=39) |

## Warsh's first meeting — applying the Powell-era lens

### 2026-06-17 (Warsh #1) — post-window incomplete (fewer than 5 post sessions settled)

| Window | SPY | percentile vs Powell | TLT | percentile vs Powell |
|---|---|---|---|---|
| Pre-5d run-up | +1.80% | 76.9%ile | +1.26% | 84.6%ile |
| Decision day | -1.25% | 12.3%ile | +0.16% | 47.7%ile |
| Post +1d | +0.78% | 76.9%ile | +0.49% | 67.7%ile |
| Post +3d | -0.42% | 38.5%ile | -0.08% | 52.3%ile |
| Post +5d | n/a | n/a%ile | n/a | n/a%ile |

Decision-day color: **Blue**.

## Notes & caveats

- Returns use raw closing prices; 5-day dividend drag on TLT is negligible.
- Decision-day return captures the 2pm statement + press conference within that session's close.
- COVID emergency decisions (Mar 2020) are flagged and excluded from aggregates.
- Warsh post-window is partial until 5 sessions settle; re-run after more sessions.
- Event windows CSV: `data/fomc/analysis/event_windows.csv` (values in percent).
