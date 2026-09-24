"""Retro of SPY/TLT daily moves after FOMC decision days of a given color and regime.

Starts from the decision day's own move (day 0) and walks forward N trading days,
one row per event per asset, plus cumulative change from the day-0 close. Writes a
CSV (long format, one row per event x asset x day) and a Markdown table under
data/fomc/analysis/retros/.

Color rule (decision-day close vs prior close): Green = SPY up & TLT up,
Orange = SPY up & TLT down, Blue = SPY down & TLT up, Red = both down; zero counts
as up. Emergency (inter-meeting) actions are excluded.

    uv run python scripts/retro_color_regime.py --regime Tightening --color Blue
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fomc.event_study import load_prices

REPO = Path(__file__).resolve().parents[1]
TRUTH_CSV = REPO / "data" / "fomc" / "analysis" / "fomc_event_truth.csv"
OUT_DIR = REPO / "data" / "fomc" / "analysis" / "retros"

COLORS = {
    (True, True): "Green",
    (True, False): "Orange",
    (False, True): "Blue",
    (False, False): "Red",
}


@dataclass
class EventPath:
    decision: date
    chair: str
    action: str
    ff_target: str
    asset: str
    daily_pct: list[float]  # day 0 .. day N
    cum_pct: list[float]  # cumulative from day-0 close, day 1 .. day N
    closes: list[float]  # closing price, day 0 .. day N


def color_of(spy_d0: float, tlt_d0: float) -> str:
    return COLORS[(spy_d0 >= 0, tlt_d0 >= 0)]


def load_events(regime: str, color: str) -> list[dict]:
    with TRUTH_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        if r["regime"] != regime or r["emergency"] == "True":
            continue
        if not r["spy_d0"] or not r["tlt_d0"]:
            continue
        if color_of(float(r["spy_d0"]), float(r["tlt_d0"])) != color:
            continue
        out.append(r)
    return out


def walk(
    closes: dict[date, float], dates: list[date], d0: date, horizon: int
) -> tuple[list[float], list[float], list[float]]:
    i = dates.index(d0)
    window = [closes[d] for d in dates[i - 1 : i + horizon + 1]]  # prior close .. +N
    daily = [(window[k] / window[k - 1] - 1) * 100 for k in range(1, len(window))]
    cum = [(window[k] / window[1] - 1) * 100 for k in range(2, len(window))]
    return daily, cum, window[1:]


def build(regime: str, color: str, horizon: int) -> list[EventPath]:
    dates, spy, tlt = load_prices()
    paths: list[EventPath] = []
    for r in load_events(regime, color):
        d0 = date.fromisoformat(r["date"])
        if d0 not in dates or dates.index(d0) + horizon >= len(dates):
            continue  # not yet settled
        for asset, closes in (("SPY", spy), ("TLT", tlt)):
            daily, cum, px = walk(closes, dates, d0, horizon)
            paths.append(
                EventPath(d0, r["chair"], r["action"], r["ff_target"], asset, daily, cum, px)
            )
    return paths


def write_csv(paths: list[EventPath], out: Path, horizon: int) -> None:
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "decision",
                "chair",
                "action",
                "ff_target",
                "asset",
                "day",
                "close",
                "daily_pct",
                "cum_from_d0_pct",
            ]
        )
        for p in paths:
            for day in range(0, horizon + 1):
                cum = "" if day == 0 else f"{p.cum_pct[day - 1]:.3f}"
                w.writerow(
                    [
                        p.decision.isoformat(),
                        p.chair,
                        p.action,
                        p.ff_target,
                        p.asset,
                        day,
                        f"{p.closes[day]:.2f}",
                        f"{p.daily_pct[day]:.3f}",
                        cum,
                    ]
                )


def write_md(paths: list[EventPath], out: Path, regime: str, color: str, horizon: int) -> None:
    fmt = lambda x: f"{x:+.2f}%"  # noqa: E731
    hdr = (
        ["Decision", "Action", "Asset", "Day 0"]
        + [f"+{k}" for k in range(1, horizon + 1)]
        + [f"{horizon}-day cum"]
    )
    L = [
        f"# Retro: {color} FOMC decision days in {regime} regimes",
        "",
        f"Day 0 is the decision day's own close-to-close move. +1 to +{horizon} are each following "
        f"trading day's move. The last column is the cumulative change from the day-0 close. "
        "Emergency meetings excluded. Percent.",
        "",
        "| " + " | ".join(hdr) + " |",
        "|" + "---|" * len(hdr),
    ]
    for p in paths:
        first = p.asset == "SPY"
        cells = [
            p.decision.isoformat() if first else "",
            p.action if first else "",
            p.asset,
            f"**{fmt(p.daily_pct[0])}**",
        ]
        cells += [fmt(x) for x in p.daily_pct[1:]] + [fmt(p.cum_pct[-1])]
        L.append("| " + " | ".join(cells) + " |")
    n = len({p.decision for p in paths})
    L += [
        "",
        f"## Averages across {n} events",
        "",
        "| Asset | Day 0 | "
        + " | ".join(f"+{k}" for k in range(1, horizon + 1))
        + f" | {horizon}-day cum | Up after {horizon} days |",
        "|---|" * 1 + "---|" * (horizon + 3),
    ]
    for asset in ("SPY", "TLT"):
        ps = [p for p in paths if p.asset == asset]
        if not ps:
            continue
        means = [sum(p.daily_pct[k] for p in ps) / len(ps) for k in range(horizon + 1)]
        cum = sum(p.cum_pct[-1] for p in ps) / len(ps)
        up = sum(1 for p in ps if p.cum_pct[-1] > 0)
        L.append(
            f"| {asset} | "
            + " | ".join(fmt(m) for m in means)
            + f" | {fmt(cum)} | {up} of {len(ps)} |"
        )
    L += [
        "",
        f"Source: `data/fomc/analysis/fomc_event_truth.csv` + the yfinance price cache. "
        f"Regenerate with `uv run python scripts/retro_color_regime.py "
        f"--regime {regime} --color {color} --horizon {horizon}`.",
        "",
    ]
    out.write_text("\n".join(L), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--regime", default="Tightening", choices=["Tightening", "Easing"])
    ap.add_argument("--color", default="Blue", choices=["Green", "Orange", "Blue", "Red"])
    ap.add_argument("--horizon", type=int, default=5)
    a = ap.parse_args(argv)
    paths = build(a.regime, a.color, a.horizon)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"retro_{a.color.lower()}_{a.regime.lower()}_{a.horizon}d"
    write_csv(paths, OUT_DIR / f"{stem}.csv", a.horizon)
    write_md(paths, OUT_DIR / f"{stem}.md", a.regime, a.color, a.horizon)
    print(f"{len({p.decision for p in paths})} events -> {OUT_DIR / (stem + '.csv')} and .md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
