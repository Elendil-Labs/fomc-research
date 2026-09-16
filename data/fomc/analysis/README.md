# analysis/ — generated outputs

Everything here is **generated** by `fomc` commands — do not hand-edit. Regenerate any
file by running the command in its row. Returns are in **percent**; `dN`/`pN`/`+Nd`
mean N trading sessions relative to the FOMC decision day.

| File | Produced by | What it is |
|---|---|---|
| `regime_timeline.csv` | `fomc regime` | One row per rate decision: date, action (Hike/Hold/Cut), regime (Tightening/Easing), target range, change/trailing-12m bps. |
| `fomc_event_truth.csv` | `fomc truth` | **Pocket source-truth.** One row per FOMC event with regime/action/target + SPY & TLT returns for pre-5d, decision day, and +1/2/3/5/10 sessions. Machine-readable. |
| `fomc_event_truth.md` | `fomc truth` | Same data as a wide, human-readable Markdown table. |
| `fomc_spy_tlt_event_study.md` | `fomc study` | Powell-era SPY/TLT stats 5d before/after FOMC, reversal/drift relationships, conditional post-windows, Warsh vs the distribution. |
| `event_windows.csv` | `fomc study` | Per-event SPY/TLT window returns feeding the study. |
| `prices_spy_tlt.csv` | `fomc study` | Merged SPY/TLT daily close series (CSV history + yfinance backfill) used by all analysis. |
| `dip_cohort_analysis.md` | `fomc dips` | The "SPY fell on the decision day" cohort: forward returns by horizon, by drop depth, Warsh comparison, full event list. |
| `dip_events.csv` | `fomc dips` | Every dip event with SPY/TLT forward returns at 1/2/3/5/10d. |
| `fomc_reversal_backtest.md` | `fomc backtest` | Decision-day reversal rules (dip_long/pop_short/combined/always_long/tlt_fade): mean, win%, t-stat, compounded, stability split, Warsh OOS. |
| `reversal_trades.csv` | `fomc backtest` | Per-trade log for the combined reversal rule. |

Reproduce everything:
```bash
uv run fomc regime && uv run fomc truth && uv run fomc study && uv run fomc dips && uv run fomc backtest
```

Note: files that backfill recent prices via yfinance change their newest rows when
re-run on a later date. See `../../../AGENTS.md` §6 (price seam).

- `retros/`: day-by-day SPY/TLT paths after FOMC days by decision-day color x regime (see `retros/README.md`; generator `scripts/retro_color_regime.py`).
