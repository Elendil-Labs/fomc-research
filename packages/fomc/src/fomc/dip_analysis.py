"""Deep-dive on the "SPY fell on the FOMC decision day" cohort.

The buy-the-dip leg is where the FOMC reversal edge concentrates. This module
isolates every Powell-era scheduled meeting where SPY closed lower on the decision
day, and characterizes the forward path of SPY (and TLT) at several horizons, broken
out by the depth of the decision-day drop. Warsh's first meeting (a -1.25% dip) is
scored against the cohort.

Entry is modeled at the decision-day close; forward return at horizon H is
close[t+H]/close[t]-1 (raw close). Powell era = 2018-03-21 onward (his first FOMC).

Usage:
    python -m fomc.dip_analysis
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fomc.event_study import OUT_DIR, load_event_dates, load_prices

HORIZONS = [1, 2, 3, 5, 10]
# decision-day drop buckets (inclusive upper bound, exclusive lower)
BUCKETS = [("mild (0 to -0.5%)", -0.005, 0.0),
           ("moderate (-0.5 to -1%)", -0.01, -0.005),
           ("sharp (worse than -1%)", -1.0, -0.01)]


@dataclass
class DipEvent:
    date: str
    chair: str
    spy_decision: float
    spy_fwd: dict       # horizon -> SPY forward return (or None)
    tlt_fwd: dict       # horizon -> TLT forward return (or None)


def _ret(series, dates, i, j):
    if i < 0 or j < 0 or i >= len(dates) or j >= len(dates):
        return None
    a = series[dates[i]]
    return None if a == 0 else series[dates[j]] / a - 1.0


def _summ(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    n = len(vals)
    mean = st.fmean(vals)
    sd = st.stdev(vals) if n > 1 else 0.0
    t = (mean / (sd / math.sqrt(n))) if sd > 0 else 0.0
    return {"n": n, "mean_pct": round(100 * mean, 3), "median_pct": round(100 * st.median(vals), 3),
            "win_pct": round(100 * sum(1 for v in vals if v > 0) / n, 1), "t_stat": round(t, 2),
            "worst_pct": round(100 * min(vals), 2), "best_pct": round(100 * max(vals), 2)}


def _corr(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    try:
        return round(st.correlation([p[0] for p in pairs], [p[1] for p in pairs]), 3)
    except st.StatisticsError:
        return None


def build(dates, spy, tlt, events) -> tuple[list[DipEvent], list[DipEvent]]:
    """Return (powell_dip_events, warsh_dip_events)."""
    powell, warsh = [], []
    for ev in events:
        d = date.fromisoformat(ev["date"])
        idx = bisect_left(dates, d)
        if idx >= len(dates) or dates[idx] != d:
            continue
        decision = _ret(spy, dates, idx - 1, idx)
        if decision is None or decision >= 0:
            continue  # only dips
        de = DipEvent(
            date=ev["date"], chair=ev["chair"], spy_decision=decision,
            spy_fwd={h: _ret(spy, dates, idx, idx + h) for h in HORIZONS},
            tlt_fwd={h: _ret(tlt, dates, idx, idx + h) for h in HORIZONS},
        )
        if ev["chair"] == "Powell" and not ev["emergency"]:
            powell.append(de)
        elif ev["chair"] == "Warsh":
            warsh.append(de)
    return powell, warsh


def run() -> None:
    dates, spy, tlt = load_prices(do_fetch=True)
    events = load_event_dates()
    powell, warsh = build(dates, spy, tlt, events)
    n_sched = sum(1 for e in events if e["chair"] == "Powell" and not e["emergency"])

    L = []
    L.append("# FOMC Buy-the-Dip Cohort — SPY fell on the decision day\n")
    L.append(f"_Generated {datetime.now(timezone.utc).date()} · Powell era 2018-03-21 → 2026-04-29 · "
             f"raw close · entry at decision-day close._\n")
    L.append(f"**Cohort size: {len(powell)} of {n_sched} scheduled Powell meetings** had SPY down on "
             f"the decision day ({round(100*len(powell)/n_sched)}%).\n")

    # forward stats by horizon — SPY
    L.append("## SPY forward return after a decision-day dip\n")
    L.append("| Horizon | n | Mean | Median | Win% | t-stat | Worst / Best |")
    L.append("|---|---|---|---|---|---|---|")
    for h in HORIZONS:
        s = _summ([e.spy_fwd[h] for e in powell])
        L.append(f"| +{h}d | {s['n']} | {s['mean_pct']:+.2f}% | {s['median_pct']:+.2f}% | "
                 f"{s['win_pct']:.0f}% | {s['t_stat']:+.2f} | {s['worst_pct']:+.1f}% / {s['best_pct']:+.1f}% |")

    # TLT in the same cohort
    L.append("\n## TLT forward return in the same (SPY-dip) cohort\n")
    L.append("| Horizon | n | Mean | Median | Win% | t-stat |")
    L.append("|---|---|---|---|---|---|")
    for h in HORIZONS:
        s = _summ([e.tlt_fwd[h] for e in powell])
        L.append(f"| +{h}d | {s['n']} | {s['mean_pct']:+.2f}% | {s['median_pct']:+.2f}% | "
                 f"{s['win_pct']:.0f}% | {s['t_stat']:+.2f} |")

    # magnitude buckets at the 5d horizon
    L.append("\n## Does a deeper dip bounce harder? (SPY +5d by drop depth)\n")
    L.append("| Decision-day drop | n | SPY +5d mean | Median | Win% | t-stat |")
    L.append("|---|---|---|---|---|---|")
    for label, lo, hi in BUCKETS:
        sel = [e for e in powell if lo < e.spy_decision <= hi]
        s = _summ([e.spy_fwd[5] for e in sel])
        if s["n"]:
            L.append(f"| {label} | {s['n']} | {s['mean_pct']:+.2f}% | {s['median_pct']:+.2f}% | "
                     f"{s['win_pct']:.0f}% | {s['t_stat']:+.2f} |")
        else:
            L.append(f"| {label} | 0 | | | | |")
    corr = _corr([e.spy_decision for e in powell], [e.spy_fwd[5] for e in powell])
    L.append(f"\ncorr(decision-day drop, SPY +5d) within the dip cohort = **{corr}** "
             f"(more negative ⇒ deeper dips bounce more).")

    # Warsh
    L.append("\n## Warsh's first meeting (2026-06-17) vs the cohort\n")
    if not warsh:
        L.append("_No Warsh dip event in range._")
    for w in warsh:
        L.append(f"Decision day **{100*w.spy_decision:+.2f}%** (a "
                 f"{'sharp' if w.spy_decision <= -0.01 else 'moderate' if w.spy_decision <= -0.005 else 'mild'} dip). "
                 f"Forward SPY:")
        for h in HORIZONS:
            v = w.spy_fwd[h]
            base = _summ([e.spy_fwd[h] for e in powell])
            tag = "n/a (unsettled)" if v is None else f"{100*v:+.2f}% (cohort mean {base['mean_pct']:+.2f}%)"
            L.append(f"- +{h}d: {tag}")

    # full event list
    L.append("\n## All dip events (Powell + Warsh)\n")
    L.append("| Date | Chair | Decision day | SPY +1d | +3d | +5d | +10d |")
    L.append("|---|---|---|---|---|---|---|")
    def cell(v):
        return "n/a" if v is None else f"{100*v:+.2f}%"
    for e in sorted(powell + warsh, key=lambda x: x.date):
        L.append(f"| {e.date} | {e.chair} | {100*e.spy_decision:+.2f}% | "
                 f"{cell(e.spy_fwd[1])} | {cell(e.spy_fwd[3])} | {cell(e.spy_fwd[5])} | {cell(e.spy_fwd[10])} |")

    L.append("\n## Caveats\n")
    L.append("- Small n per bucket; t≈2 is the rough significance bar.")
    L.append("- Forward windows overlap across nearby meetings only minimally (meetings ~6-7 weeks apart).")
    L.append("- No transaction costs/slippage; raw close entry assumes execution at the 4pm close.")
    L.append("- Warsh's regime (no dot plot, less guidance) may not inherit Powell-era reversion.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "dip_cohort_analysis.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    with (OUT_DIR / "dip_events.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["date", "chair", "spy_decision_pct"] + [f"spy_fwd_{h}d_pct" for h in HORIZONS]
                    + [f"tlt_fwd_{h}d_pct" for h in HORIZONS])
        for e in sorted(powell + warsh, key=lambda x: x.date):
            row = [e.date, e.chair, round(100 * e.spy_decision, 3)]
            row += [None if e.spy_fwd[h] is None else round(100 * e.spy_fwd[h], 3) for h in HORIZONS]
            row += [None if e.tlt_fwd[h] is None else round(100 * e.tlt_fwd[h], 3) for h in HORIZONS]
            wr.writerow(row)

    print(f"Dip cohort: {len(powell)} Powell + {len(warsh)} Warsh")
    for h in HORIZONS:
        s = _summ([e.spy_fwd[h] for e in powell])
        print(f"  SPY +{h}d: n={s['n']} mean={s['mean_pct']:+.2f}% win={s['win_pct']:.0f}% t={s['t_stat']:+.2f}")
    print(f"Report: {OUT_DIR / 'dip_cohort_analysis.md'}")


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="FOMC buy-the-dip cohort analysis").parse_args(argv)
    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
