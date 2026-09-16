"""Backtest the FOMC decision-day reversal edge on SPY (and a TLT-fade variant).

Builds on the event study: on each scheduled FOMC decision day t, the decision-day
SPY return predicts a partial reversal over the next 5 sessions. This module turns
that into explicit rules and measures per-trade P&L vs baselines.

Rules (enter at decision-day close t, exit at close t+H; H default 5 sessions):
    dip_long    long SPY  when SPY fell on the decision day  (buy the hawkish dip)
    pop_short   short SPY when SPY rose on the decision day  (fade the dovish pop)
    combined    dip_long + pop_short  (position = -sign(decision-day return))
    always_long long SPY every meeting                       (baseline)
    tlt_fade    short TLT every meeting   (TLT tends to sell off post-FOMC)

Per-trade P&L is modeled arithmetically (position * window return); it is not
daily-rebalanced. Powell-era scheduled meetings only; the Warsh meeting is scored
out-of-sample.

Usage:
    python -m fomc.backtest                 # H=5
    python -m fomc.backtest --horizon 3
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics as st
from dataclasses import dataclass
from datetime import datetime, timezone

from fomc.event_study import (
    OUT_DIR,
    build_windows,
    load_event_dates,
    load_prices,
)


@dataclass
class Trade:
    date: str
    spy_event0: float
    spy_ret: float       # SPY window return (close[t]->close[t+H])
    tlt_ret: float
    position: int        # +1 long / -1 short / 0 none, for the active rule
    pnl: float           # position * underlying window return


def _stats(pnls: list[float]) -> dict:
    if not pnls:
        return {"n": 0}
    n = len(pnls)
    mean = st.fmean(pnls)
    std = st.pstdev(pnls) if n > 1 else 0.0
    sd_sample = st.stdev(pnls) if n > 1 else 0.0
    t = (mean / (sd_sample / math.sqrt(n))) if sd_sample > 0 else 0.0
    cum = 1.0
    for r in pnls:
        cum *= (1 + r)
    return {
        "n": n,
        "mean_pct": round(100 * mean, 3),
        "median_pct": round(100 * st.median(pnls), 3),
        "win_rate_pct": round(100 * sum(1 for r in pnls if r > 0) / n, 1),
        "std_pct": round(100 * std, 3),
        "t_stat": round(t, 2),
        "total_return_pct": round(100 * (cum - 1), 2),
        "best_pct": round(100 * max(pnls), 2),
        "worst_pct": round(100 * min(pnls), 2),
    }


def _ret_field(w, base: str, h: int) -> float | None:
    return getattr(w, f"{base}_post{h}")


def run(horizon: int = 5) -> None:
    dates, spy, tlt = load_prices(do_fetch=True)
    events = load_event_dates()
    windows = build_windows(events, dates, spy, tlt)

    powell = [w for w in windows
              if w.chair == "Powell" and not w.emergency
              and _ret_field(w, "spy", horizon) is not None
              and _ret_field(w, "tlt", horizon) is not None
              and w.spy_event0 is not None]
    warsh = [w for w in windows if w.chair == "Warsh"]

    def build(rule: str) -> list[Trade]:
        trades = []
        for w in powell:
            sr = _ret_field(w, "spy", horizon)
            tr = _ret_field(w, "tlt", horizon)
            ev = w.spy_event0
            if rule == "dip_long":
                pos = 1 if ev < 0 else 0
                pnl = pos * sr
            elif rule == "pop_short":
                pos = -1 if ev >= 0 else 0
                pnl = pos * sr
            elif rule == "combined":
                pos = -1 if ev >= 0 else 1
                pnl = pos * sr
            elif rule == "always_long":
                pos, pnl = 1, sr
            elif rule == "tlt_fade":
                pos, pnl = -1, -tr
            else:
                raise ValueError(rule)
            if pos == 0:
                continue
            trades.append(Trade(w.date, ev, sr, tr, pos, pnl))
        return trades

    rules = ["dip_long", "pop_short", "combined", "always_long", "tlt_fade"]
    results = {r: build(r) for r in rules}
    stats = {r: _stats([t.pnl for t in results[r]]) for r in rules}

    # Stability: split the combined rule first half vs second half by date.
    comb = sorted(results["combined"], key=lambda t: t.date)
    half = len(comb) // 2
    stab = {"first_half": _stats([t.pnl for t in comb[:half]]),
            "second_half": _stats([t.pnl for t in comb[half:]])}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # trades CSV (combined rule)
    with (OUT_DIR / "reversal_trades.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["date", "spy_decision_day_pct", "position", "spy_window_pct", "pnl_pct"])
        for t in sorted(results["combined"], key=lambda x: x.date):
            wr.writerow([t.date, round(100 * t.spy_event0, 3), t.position,
                         round(100 * t.spy_ret, 3), round(100 * t.pnl, 3)])

    # report
    L = []
    L.append("# FOMC Decision-Day Reversal — Backtest\n")
    L.append(f"_Generated {datetime.now(timezone.utc).date()} · horizon = {horizon} "
             f"sessions · Powell-era scheduled meetings (n={len(powell)}) · "
             f"arithmetic per-trade P&L (not daily-rebalanced)._\n")
    L.append("Enter at the decision-day close, exit H sessions later.\n")
    L.append("| Rule | Trades | Mean | Median | Win% | t-stat | Total (compounded) | Worst |")
    L.append("|---|---|---|---|---|---|---|---|")
    labels = {"dip_long": "dip_long (long SPY when SPY fell)",
              "pop_short": "pop_short (short SPY when SPY rose)",
              "combined": "combined (−sign of decision-day SPY)",
              "always_long": "always_long SPY (baseline)",
              "tlt_fade": "tlt_fade (short TLT every meeting)"}
    for r in rules:
        s = stats[r]
        if not s.get("n"):
            continue
        L.append(f"| {labels[r]} | {s['n']} | {s['mean_pct']:+.2f}% | {s['median_pct']:+.2f}% | "
                 f"{s['win_rate_pct']:.0f}% | {s['t_stat']:+.2f} | {s['total_return_pct']:+.1f}% | "
                 f"{s['worst_pct']:+.1f}% |")

    L.append("\n## Stability — combined rule, split by date\n")
    L.append("| Period | Trades | Mean | Win% | t-stat | Total |")
    L.append("|---|---|---|---|---|---|")
    for k in ("first_half", "second_half"):
        s = stab[k]
        L.append(f"| {k.replace('_',' ')} | {s['n']} | {s['mean_pct']:+.2f}% | "
                 f"{s['win_rate_pct']:.0f}% | {s['t_stat']:+.2f} | {s['total_return_pct']:+.1f}% |")

    L.append("\n## Warsh's first meeting — out-of-sample signal\n")
    for w in warsh:
        ev = w.spy_event0
        signal = "LONG SPY (buy the dip)" if ev is not None and ev < 0 else "SHORT SPY (fade the pop)"
        realized = _ret_field(w, "spy", horizon)
        avail = "n/a (post-window not settled)" if realized is None else f"{100*realized:+.2f}%"
        post1 = w.spy_post1
        L.append(f"- **{w.date}** decision-day SPY {100*ev:+.2f}% → rule fires **{signal}**. "
                 f"H={horizon} outcome: {avail}. "
                 f"(Post +1d SPY {100*post1:+.2f}%.)" if post1 is not None else "")

    L.append("\n## Read\n")
    s_comb, s_dip, s_pop, s_base = stats["combined"], stats["dip_long"], stats["pop_short"], stats["always_long"]
    L.append(f"- Combined reversal: mean **{s_comb['mean_pct']:+.2f}%/trade**, "
             f"win {s_comb['win_rate_pct']:.0f}%, t={s_comb['t_stat']:+.2f} over {s_comb['n']} meetings "
             f"vs always-long baseline mean {s_base['mean_pct']:+.2f}% (t={s_base['t_stat']:+.2f}).")
    L.append(f"- The dip_long leg (mean {s_dip['mean_pct']:+.2f}%, win {s_dip['win_rate_pct']:.0f}%, "
             f"n={s_dip['n']}) typically carries the edge more than pop_short "
             f"(mean {s_pop['mean_pct']:+.2f}%, win {s_pop['win_rate_pct']:.0f}%, n={s_pop['n']}).")
    L.append("- |t|≈2 is the rough significance bar; treat anything below as suggestive, not proven.")
    L.append("- Caveats: small n, overlapping-window independence assumed, no costs/slippage, "
             "and Warsh's no-guidance regime may not inherit Powell-era reversion.")

    rep = OUT_DIR / "fomc_reversal_backtest.md"
    rep.write_text("\n".join([x for x in L if x is not None]) + "\n", encoding="utf-8")

    print(f"Powell scheduled trades: {len(powell)} | horizon {horizon}")
    for r in rules:
        s = stats[r]
        print(f"  {r:12s} n={s.get('n',0):2d} mean={s.get('mean_pct',0):+.2f}% "
              f"win={s.get('win_rate_pct',0):.0f}% t={s.get('t_stat',0):+.2f} "
              f"total={s.get('total_return_pct',0):+.1f}%")
    print(f"Report: {rep}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FOMC decision-day reversal backtest")
    p.add_argument("--horizon", type=int, default=5, help="holding sessions (1,3,5)")
    args = p.parse_args(argv)
    run(horizon=args.horizon)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
