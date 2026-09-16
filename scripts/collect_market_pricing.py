"""Market-pricing axis — what the MARKET prices for Fed policy (hard data, no LLM).

The Regime Intelligence feed scores the *policy-rate / communications* axis from news,
and collect_balance_sheet.py scores the *balance-sheet / liquidity* axis. This script
adds a third hard-data read: what rates markets are actually PRICING for the Fed path —
2y yield momentum, curve shape, the 2y-vs-funds-rate gap, and net liquidity — straight
from FRED. The market can disagree with both the news lean and the balance sheet; this
axis makes that disagreement visible instead of implied.

Uses the official FRED API (api.stlouisfed.org). Needs a free FRED API key in
FRED_API_KEY. WITHOUT a key, or on any FRED outage, it writes {available:false} and the
dashboard shows a clean "axis pending" state rather than broken rows.

Usage:
    python scripts/collect_market_pricing.py     # needs FRED_API_KEY
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import _intel_common as ic

FRED_API = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={id}&api_key={key}&file_type=json&observation_start={start}"
)
# NOT "market_pricing.json": a news bucket named market_pricing already exists in
# _intel_common.BUCKETS — keep the file name distinct to avoid confusion.
MARKET_PRICING = ic.INTEL_DIR / "market_pricing_axis.json"

# WALCL/WTREGEN are $ millions; RRPONTSYD is $ BILLIONS — convert before combining.
RRP_TO_MILLIONS = 1000.0

# Each indicator: how to read it on the tightening (+) ↔ loosening (-) axis.
INDICATORS = [
    # Dead zone 0.10pp: sub-10bp 90d moves in the 2y are chop, not a repricing of the path.
    {"id": "DGS2", "name": "2y Treasury yield (policy-path momentum)", "unit": "%",
     "weight": 0.30, "mode": "change", "up_tightening": True, "dead": 0.10,
     "tnote": "market repricing tighter policy", "lnote": "market repricing easier policy"},
    # < -0.20 = decisively inverted (cuts priced ahead); > +0.75 = steep enough to signal
    # tightening/term premium rather than the flat-curve ambiguity in between.
    {"id": "T10Y2Y", "name": "Curve slope (10y − 2y)", "unit": "%",
     "weight": 0.20, "mode": "spread", "a": "DGS10", "b": "DGS2",
     "hi_thr": 0.75, "lo_thr": -0.20,
     "tnote": "steep curve — tightening / term premium priced",
     "lnote": "inverted curve — easing priced ahead"},
    # ±0.25pp ≈ one full 25bp move priced into the 2y relative to the current funds rate.
    {"id": "DGS2_DFF", "name": "Fed-funds path (2y − funds rate)", "unit": "%",
     "weight": 0.30, "mode": "spread", "a": "DGS2", "b": "DFF",
     "hi_thr": 0.25, "lo_thr": -0.25,
     "tnote": "hikes priced in (2y above funds)", "lnote": "cuts priced in (2y below funds)"},
    # Dead zone $100B (=100,000 $M): weekly TGA/RRP noise routinely swings tens of $B.
    {"id": "NET_LIQUIDITY", "name": "Net liquidity (WALCL − TGA − RRP)", "unit": "$M",
     "weight": 0.20, "mode": "composite", "up_tightening": False, "dead": 100_000,
     "tnote": "liquidity draining", "lnote": "liquidity building"},
]


def fetch_series(series_id: str, key: str, start: str) -> list[tuple[str, float]]:
    """Fetch a FRED series via the official API (JSON)."""
    url = FRED_API.format(id=series_id, key=key, start=start)
    req = urllib.request.Request(url, headers={"User-Agent": "elendil-labs-fomc/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    out: list[tuple[str, float]] = []
    for obs in payload.get("observations", []):
        v = obs.get("value", ".")
        if v in (".", "", None):
            continue
        try:
            out.append((obs["date"], float(v)))
        except (ValueError, KeyError):
            continue
    if not out:
        raise ValueError(f"no observations for {series_id}")
    return out


def change_90d(series: list[tuple[str, float]]) -> tuple[float, str, float, str]:
    """(latest_value, latest_date, change vs ~90d prior, prior_date).

    Falls back to the earliest obs when nothing is >=90 days back (truncated FRED
    response); the returned prior_date lets callers report the ACTUAL window instead
    of claiming a 90d change they don't have.
    """
    latest_date, latest_val = series[-1]
    target = datetime.fromisoformat(latest_date).date() - timedelta(days=90)
    prior_date, prior_val = series[0]
    for d, v in series:
        if datetime.fromisoformat(d).date() <= target:
            prior_date, prior_val = d, v
        else:
            break
    return latest_val, latest_date, latest_val - prior_val, prior_date


def window_days(latest_date: str, prior_date: str) -> int:
    latest = datetime.fromisoformat(latest_date).date()
    return (latest - datetime.fromisoformat(prior_date).date()).days


def signal_change(change: float, up_tightening: bool, dead: float) -> int:
    if abs(change) <= dead:
        return 0
    rising = change > 0
    tightening = rising if up_tightening else not rising
    return 1 if tightening else -1


def signal_spread(spread: float, hi_thr: float, lo_thr: float) -> int:
    return 1 if spread >= hi_thr else -1 if spread <= lo_thr else 0


def net_liquidity_90d(key: str, start: str) -> tuple[float, str, float, str]:
    """(latest level $M, as_of, ~90d change $M, prior_date) of WALCL − WTREGEN − RRPONTSYD.

    Each series is aligned to ITS OWN latest obs and the obs nearest 90 days back
    (WALCL/WTREGEN are weekly, RRPONTSYD daily), then the per-series 90d changes are
    combined. RRPONTSYD is $ BILLIONS while WALCL/WTREGEN are $ millions — ×1000 first.
    """
    w_val, w_date, w_chg, w_prior = change_90d(fetch_series("WALCL", key, start))
    t_val, _, t_chg, _ = change_90d(fetch_series("WTREGEN", key, start))
    r_val, _, r_chg, _ = change_90d(fetch_series("RRPONTSYD", key, start))
    level = w_val - t_val - r_val * RRP_TO_MILLIONS
    change = w_chg - t_chg - r_chg * RRP_TO_MILLIONS
    return level, w_date, change, w_prior


def _base(ind: dict) -> dict:
    return {"id": ind["id"], "name": ind["name"], "unit": ind["unit"], "weight": ind["weight"]}


def evaluate(key: str, start: str) -> list[dict]:
    rows: list[dict] = []
    for ind in INDICATORS:
        try:
            if ind["mode"] == "spread":
                a = fetch_series(ind["a"], key, start)
                b = fetch_series(ind["b"], key, start)
                spread = round(a[-1][1] - b[-1][1], 3)
                sig = signal_spread(spread, ind["hi_thr"], ind["lo_thr"])
                rows.append({**_base(ind), "latest": spread, "as_of": a[-1][0],
                             "signal": sig, "detail": f"{spread:+.2f}%"})
            elif ind["mode"] == "composite":
                level, as_of, chg, prior = net_liquidity_90d(key, start)
                sig = signal_change(chg, ind["up_tightening"], ind["dead"])
                rows.append({**_base(ind), "latest": round(level, 1), "as_of": as_of,
                             "prior_as_of": prior,
                             "change_90d": round(chg, 1), "signal": sig,
                             "detail": f"Δ{window_days(as_of, prior)}d {chg / 1000:+,.0f} $B"})
            else:  # change
                s = fetch_series(ind["id"], key, start)
                val, as_of, chg, prior = change_90d(s)
                sig = signal_change(chg, ind["up_tightening"], ind["dead"])
                rows.append({**_base(ind), "latest": val, "as_of": as_of,
                             "prior_as_of": prior,
                             "change_90d": round(chg, 3), "signal": sig,
                             "detail": f"Δ{window_days(as_of, prior)}d {chg:+,.2f} {ind['unit']}"})
        except (urllib.error.URLError, OSError, IndexError, ValueError, KeyError) as e:
            rows.append({**_base(ind), "latest": None, "signal": 0,
                         "detail": "unavailable", "error": str(e)[:80]})
    return rows


def aggregate(rows: list[dict]) -> tuple[float, float]:
    """(net_lean, coverage) over indicators that actually produced data.

    Renormalizes the weights over LIVE rows — a failed indicator must not dilute the
    lean toward neutral by sitting in the denominator with signal 0. Coverage is the
    weight share that produced data (1.0 = full read), so consumers can see when the
    lean rests on a degraded indicator set.
    """
    live = [r for r in rows if r.get("latest") is not None]
    wsum = sum(r["weight"] for r in live) or 1.0
    net = round(sum(r["signal"] * r["weight"] for r in live) / wsum, 4)
    coverage = round(sum(r["weight"] for r in live), 4)
    return net, coverage


def label(net: float) -> str:
    if net <= -0.25:
        return "loosening"
    if net < 0.25:
        return "neutral"
    return "tightening"


def write_unavailable(reason: str) -> None:
    """Write a clean 'axis pending' doc so the dashboard never shows broken rows."""
    ic.ensure_dirs()
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": False,
        "reason": reason,
        "net_lean": 0.0,
        "label": "neutral",
        "indicators": [],
        "source": "FRED API (api.stlouisfed.org)",
    }
    MARKET_PRICING.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Market-pricing axis unavailable: {reason} -> wrote pending state.")


def main() -> int:
    key = ic.load_api_key("FRED_API_KEY")
    if not key:
        write_unavailable("FRED_API_KEY not set")
        return 0

    start = (date.today() - timedelta(days=130)).isoformat()
    rows = evaluate(key, start)

    if all(r["signal"] == 0 and r.get("latest") is None for r in rows):
        write_unavailable("FRED unreachable / all series failed")
        return 0

    net, coverage = aggregate(rows)
    for r, ind in zip(rows, INDICATORS):
        if r.get("latest") is None:
            r["note"] = "unavailable"  # not a neutral vote — excluded from net_lean
        elif r["signal"] > 0:
            r["note"] = ind["tnote"]
        elif r["signal"] < 0:
            r["note"] = ind["lnote"]
        else:
            r["note"] = "neutral"

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": True,
        "net_lean": net,  # tightening positive, -1..1, over LIVE indicators only
        "label": label(net),
        "coverage": coverage,  # weight share of indicators that produced data
        "indicators": rows,
        "method": "Weighted -1/0/+1 signals from FRED primary series (deterministic; no LLM).",
        "source": "FRED API (api.stlouisfed.org)",
    }
    ic.ensure_dirs()
    MARKET_PRICING.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Market-pricing axis: {doc['label']} (net {net:+.2f})")
    for r in rows:
        print(f"  {r['name']:42} signal {r['signal']:+d}  {r['detail']}  [{r.get('note','')}]")
    print(f"  -> {MARKET_PRICING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
