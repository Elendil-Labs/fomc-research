"""Balance-sheet / liquidity axis — the second, DATA-DRIVEN regime dimension.

The Regime Intelligence feed scores the *policy-rate / communications* axis from news
(vote-share). This script computes the orthogonal *balance-sheet / liquidity / collateral*
axis straight from FRED — no LLM, no judgment, fully deterministic — so the dashboard can
detect the Warsh-type divergence: the Fed easing on the rate while financial conditions
for levered actors tighten via the balance sheet.

Uses the official FRED API (api.stlouisfed.org), which — unlike the keyless graph/CSV
endpoint — is reachable from CI/datacenter IPs. Needs a free FRED API key
(https://fred.stlouisfed.org/docs/api/api_key.html) in FRED_API_KEY. WITHOUT a key, or
on any FRED outage, it writes {available:false} and the dashboard shows a clean "axis
pending" state rather than broken rows.

Usage:
    python scripts/collect_balance_sheet.py     # needs FRED_API_KEY
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
BALANCE_SHEET = ic.INTEL_DIR / "balance_sheet.json"

# Each indicator: how to read it on the tightening (+) ↔ loosening (-) axis.
INDICATORS = [
    {"id": "WALCL", "name": "Fed balance sheet", "unit": "$M", "weight": 0.28,
     "mode": "change", "up_tightening": False, "dead": 20000,
     "tnote": "shrinking (QT)", "lnote": "expanding (QE)"},
    {"id": "WRESBAL", "name": "Bank reserves", "unit": "$M", "weight": 0.22,
     "mode": "change", "up_tightening": False, "dead": 60000,
     "tnote": "draining", "lnote": "building"},
    {"id": "RRPONTSYD", "name": "Reverse-repo cushion", "unit": "$B", "weight": 0.15,
     "mode": "level", "hi_thr": 50, "lo_thr": 300, "level_tight": "low",
     "tnote": "near-depleted (QT cushion gone)", "lnote": "ample cushion"},
    {"id": "DGS10", "name": "10y Treasury yield (term-premium proxy)", "unit": "%", "weight": 0.20,
     "mode": "change", "up_tightening": True, "dead": 0.15,
     "tnote": "long-end rising", "lnote": "long-end falling"},
    {"id": "SOFR_IORB", "name": "Repo stress (SOFR − IORB)", "unit": "bp", "weight": 0.15,
     "mode": "spread", "a": "SOFR", "b": "IORB", "hi_thr": 0.05, "lo_thr": -0.03,
     "tnote": "funding stress", "lnote": "ample funding"},
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


def change_90d(series: list[tuple[str, float]]) -> tuple[float, str, float]:
    """(latest_value, latest_date, change vs the obs closest to 90 days earlier)."""
    latest_date, latest_val = series[-1]
    target = datetime.fromisoformat(latest_date).date() - timedelta(days=90)
    prior_val = series[0][1]
    for d, v in series:
        if datetime.fromisoformat(d).date() <= target:
            prior_val = v
        else:
            break
    return latest_val, latest_date, latest_val - prior_val


def signal_change(change: float, up_tightening: bool, dead: float) -> int:
    if abs(change) <= dead:
        return 0
    rising = change > 0
    tightening = rising if up_tightening else not rising
    return 1 if tightening else -1


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
                sig = 1 if spread >= ind["hi_thr"] else -1 if spread <= ind["lo_thr"] else 0
                rows.append({**_base(ind), "latest": spread, "as_of": a[-1][0],
                             "signal": sig, "detail": f"{spread:+.2f}%"})
            elif ind["mode"] == "level":
                s = fetch_series(ind["id"], key, start)
                level = s[-1][1]
                tight_low = ind.get("level_tight") == "low"
                if level <= ind["hi_thr"]:
                    sig = 1 if tight_low else -1
                elif level >= ind["lo_thr"]:
                    sig = -1 if tight_low else 1
                else:
                    sig = 0
                rows.append({**_base(ind), "latest": level, "as_of": s[-1][0],
                             "signal": sig, "detail": f"{level:,.0f} {ind['unit']}"})
            else:  # change
                s = fetch_series(ind["id"], key, start)
                val, as_of, chg = change_90d(s)
                sig = signal_change(chg, ind["up_tightening"], ind["dead"])
                rows.append({**_base(ind), "latest": val, "as_of": as_of,
                             "change_90d": round(chg, 3), "signal": sig,
                             "detail": f"Δ90d {chg:+,.2f} {ind['unit']}"})
        except (urllib.error.URLError, OSError, IndexError, ValueError, KeyError) as e:
            rows.append({**_base(ind), "latest": None, "signal": 0,
                         "detail": "unavailable", "error": str(e)[:80]})
    return rows


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
    BALANCE_SHEET.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Balance-sheet axis unavailable: {reason} -> wrote pending state.")


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

    wsum = sum(r["weight"] for r in rows) or 1.0
    net = round(sum(r["signal"] * r["weight"] for r in rows) / wsum, 4)
    for r, ind in zip(rows, INDICATORS):
        if r["signal"] > 0:
            r["note"] = ind["tnote"]
        elif r["signal"] < 0:
            r["note"] = ind["lnote"]
        else:
            r["note"] = "neutral"

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": True,
        "net_lean": net,  # tightening positive, -1..1
        "label": label(net),
        "indicators": rows,
        "method": "Weighted -1/0/+1 signals from FRED primary series (deterministic; no LLM).",
        "source": "FRED API (api.stlouisfed.org)",
    }
    ic.ensure_dirs()
    BALANCE_SHEET.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Balance-sheet axis: {doc['label']} (net {net:+.2f})")
    for r in rows:
        print(f"  {r['name']:42} signal {r['signal']:+d}  {r['detail']}  [{r.get('note','')}]")
    print(f"  -> {BALANCE_SHEET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
