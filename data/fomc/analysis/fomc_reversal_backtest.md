# FOMC Decision-Day Reversal — Backtest

_Generated 2026-06-23 · horizon = 5 sessions · Powell-era scheduled meetings (n=65) · arithmetic per-trade P&L (not daily-rebalanced)._

Enter at the decision-day close, exit H sessions later.

| Rule | Trades | Mean | Median | Win% | t-stat | Total (compounded) | Worst |
|---|---|---|---|---|---|---|---|
| dip_long (long SPY when SPY fell) | 35 | +0.08% | +0.03% | 51% | +0.20 | +1.9% | -4.8% |
| pop_short (short SPY when SPY rose) | 30 | +0.26% | +0.27% | 60% | +0.55 | +7.0% | -4.7% |
| combined (−sign of decision-day SPY) | 65 | +0.16% | +0.15% | 55% | +0.53 | +9.0% | -4.8% |
| always_long SPY (baseline) | 65 | -0.08% | -0.20% | 46% | -0.25 | -6.7% | -8.5% |
| tlt_fade (short TLT every meeting) | 65 | +0.27% | +0.17% | 52% | +0.98 | +17.0% | -5.4% |

## Stability — combined rule, split by date

| Period | Trades | Mean | Win% | t-stat | Total |
|---|---|---|---|---|---|
| first half | 32 | -0.21% | 50% | -0.54 | -7.2% |
| second half | 33 | +0.52% | 61% | +1.12 | +17.4% |

## Warsh's first meeting — out-of-sample signal

- **2026-06-17** decision-day SPY -1.25% → rule fires **LONG SPY (buy the dip)**. H=5 outcome: n/a (post-window not settled). (Post +1d SPY +0.78%.)

## Read

- Combined reversal: mean **+0.16%/trade**, win 55%, t=+0.53 over 65 meetings vs always-long baseline mean -0.08% (t=-0.25).
- The dip_long leg (mean +0.08%, win 51%, n=35) typically carries the edge more than pop_short (mean +0.26%, win 60%, n=30).
- |t|≈2 is the rough significance bar; treat anything below as suggestive, not proven.
- Caveats: small n, overlapping-window independence assumed, no costs/slippage, and Warsh's no-guidance regime may not inherit Powell-era reversion.
