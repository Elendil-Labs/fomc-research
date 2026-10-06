"""CFTC Treasury-futures positioning — who is selling the long end? (hard data, no LLM).

Reads the Traders in Financial Futures report (futures only) for the four CBOT
Treasury contracts that carry long-end duration: 10y note, Ultra 10y, bond, Ultra bond.
Asset managers are the real-money side; leveraged funds are the spec side (basis trade
shorts live here); dealers are the residual. A long-end bottom has historically needed
real money to STOP distributing and specs to be stretched short.

Sources: the current-week file (no header row; columns by the published TFF layout)
merged with the yearly history zip (header row), deduped by report date; the prior
year's zip is added when fewer than 30 weeks are available. Degrades to
{available:false} if nothing can be fetched.

Usage:
    python scripts/collect_cftc_positioning.py
"""

from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timezone

import _intel_common as ic

CURRENT_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
HISTORY_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
CFTC_POSITIONING = ic.INTEL_DIR / "cftc_positioning.json"
SOURCE = "CFTC Traders in Financial Futures (futures only)"
MIN_WEEKS = 30
HISTORY_WEEKS = 26
OUTPUT_WEEKS = 12

CONTRACTS = {
    "UST 10Y NOTE - CHICAGO BOARD OF TRADE": ("UST_10Y", "10y T-Note"),
    "ULTRA UST 10Y - CHICAGO BOARD OF TRADE": ("ULTRA_10Y", "Ultra 10y T-Note"),
    "UST BOND - CHICAGO BOARD OF TRADE": ("UST_BOND", "T-Bond"),
    "ULTRA UST BOND - CHICAGO BOARD OF TRADE": ("ULTRA_BOND", "Ultra T-Bond"),
}
CONTRACT_ORDER = ("UST_10Y", "ULTRA_10Y", "UST_BOND", "ULTRA_BOND")

# Column positions in the TFF futures-only layout (verified against the yearly header).
COL_NAME = 0
COL_REPORT_DATE = 2
COL_OPEN_INTEREST = 7
COL_DEALER_LONG, COL_DEALER_SHORT = 8, 9
COL_AM_LONG, COL_AM_SHORT = 11, 12
COL_LF_LONG, COL_LF_SHORT = 14, 15
HEADER_FIRST_FIELD = "Market_and_Exchange_Names"


# ---------------------------------------------------------------- fetch


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 elendil-labs-fomc"})
    with urllib.request.urlopen(req, timeout=60, context=ic.ssl_context()) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_history_year(year: int) -> str:
    req = urllib.request.Request(HISTORY_URL.format(year=year),
                                 headers={"User-Agent": "Mozilla/5.0 elendil-labs-fomc"})
    with urllib.request.urlopen(req, timeout=120, context=ic.ssl_context()) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not names:
            raise ValueError("no txt in history zip")
        return z.read(names[0]).decode("utf-8", "replace")


# ---------------------------------------------------------------- pure logic


def _int(v: str) -> int:
    return int(float(v.strip()))


def parse_rows(text: str) -> list[dict]:
    """Rows for the tracked contracts from a TFF file, with or without a header row."""
    out: list[dict] = []
    for fields in csv.reader(io.StringIO(text)):
        if not fields or fields[COL_NAME].strip() == HEADER_FIRST_FIELD:
            continue
        name = fields[COL_NAME].strip()
        if name not in CONTRACTS or len(fields) <= COL_LF_SHORT:
            continue
        cid, label = CONTRACTS[name]
        try:
            out.append({
                "id": cid, "name": label,
                "report_date": fields[COL_REPORT_DATE].strip(),
                "open_interest": _int(fields[COL_OPEN_INTEREST]),
                "dealer_net": _int(fields[COL_DEALER_LONG]) - _int(fields[COL_DEALER_SHORT]),
                "am_net": _int(fields[COL_AM_LONG]) - _int(fields[COL_AM_SHORT]),
                "lf_net": _int(fields[COL_LF_LONG]) - _int(fields[COL_LF_SHORT]),
            })
        except ValueError:
            continue
    return out


def merge_weekly(*row_sets: list[dict]) -> dict[str, list[dict]]:
    """Per contract id: rows deduped by report date, oldest first."""
    by_id: dict[str, dict[str, dict]] = {}
    for rows in row_sets:
        for r in rows:
            by_id.setdefault(r["id"], {})[r["report_date"]] = r
    return {cid: [weeks[d] for d in sorted(weeks)] for cid, weeks in by_id.items()}


def change(series: list[int], weeks: int) -> int | None:
    return None if len(series) <= weeks else series[-1] - series[-1 - weeks]


def selling_streak(am_net: list[int]) -> int:
    """Consecutive weeks (back from latest) in which asset-manager net fell."""
    streak = 0
    for i in range(len(am_net) - 1, 0, -1):
        if am_net[i] - am_net[i - 1] < 0:
            streak += 1
        else:
            break
    return streak


def stopped_selling(am_net: list[int]) -> bool:
    """Last two weekly changes both positive."""
    if len(am_net) < 3:
        return False
    return am_net[-1] > am_net[-2] and am_net[-2] > am_net[-3]


def build_contract(rows: list[dict]) -> dict:
    """Positioning read for one contract from its oldest-first weekly rows."""
    window = rows[-HISTORY_WEEKS:]
    am = [r["am_net"] for r in window]
    lf = [r["lf_net"] for r in window]
    latest = window[-1]
    return {
        "id": latest["id"], "name": latest["name"], "as_of": latest["report_date"],
        "open_interest": latest["open_interest"],
        "am_net": am[-1], "am_net_change_1w": change(am, 1), "am_net_change_4w": change(am, 4),
        "lf_net": lf[-1], "lf_net_change_1w": change(lf, 1), "lf_net_change_4w": change(lf, 4),
        "dealer_net": latest["dealer_net"],
        "am_selling_streak_weeks": selling_streak(am),
        "am_stopped_selling": stopped_selling(am),
        "lf_net_26w_low": lf[-1] == min(lf),
        "history": [{"report_date": r["report_date"], "am_net": r["am_net"], "lf_net": r["lf_net"]}
                    for r in window[-OUTPUT_WEEKS:]],
    }


def build_contracts(weekly: dict[str, list[dict]]) -> list[dict]:
    return [build_contract(weekly[cid]) for cid in CONTRACT_ORDER if weekly.get(cid)]


def summarize(contracts: list[dict]) -> dict:
    distributing = sum(1 for c in contracts
                       if c["am_net_change_4w"] is not None and c["am_net_change_4w"] < 0)
    capitulating = sum(1 for c in contracts if c["lf_net_26w_low"])
    stopped = sum(1 for c in contracts if c["am_stopped_selling"])
    real_money_distribution = distributing >= 3
    spec_capitulation = capitulating >= 2
    dist_txt = "distribution" if real_money_distribution else "no broad distribution"
    read = (f"Asset managers cut net length over 4 weeks in {distributing} of {len(contracts)} "
            f"contracts ({dist_txt}); "
            f"leveraged funds at a 26-week net low in {capitulating} "
            f"({'spec capitulation' if spec_capitulation else 'no capitulation'}); "
            f"real money has stopped selling in {stopped}.")
    return {
        "as_of": max((c["as_of"] for c in contracts), default=None),
        "real_money_distribution": real_money_distribution,
        "spec_capitulation": spec_capitulation,
        "am_stopped_selling_count": stopped,
        "read": read,
    }


# ---------------------------------------------------------------- output


def write_unavailable(reason: str) -> None:
    """Write a clean 'pending' doc so the dashboard never shows broken rows."""
    ic.ensure_dirs()
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": False,
        "reason": reason,
        "source": SOURCE,
        "contracts": [],
        "summary": {"as_of": None, "real_money_distribution": False, "spec_capitulation": False,
                    "am_stopped_selling_count": 0, "read": "unavailable"},
    }
    CFTC_POSITIONING.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"CFTC positioning unavailable: {reason} -> wrote pending state.")


def load_weekly(today: date) -> dict[str, list[dict]]:
    """Current week + this year's history (+ last year's if thin); failures are logged."""
    row_sets: list[list[dict]] = []
    try:
        row_sets.append(parse_rows(fetch_text(CURRENT_URL)))
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"  current week unavailable ({str(e)[:80]})")
    for year in (today.year, today.year - 1):
        try:
            row_sets.append(parse_rows(fetch_history_year(year)))
        except (urllib.error.URLError, OSError, ValueError, zipfile.BadZipFile) as e:
            print(f"  history {year} unavailable ({str(e)[:80]})")
        weeks = max((len(v) for v in merge_weekly(*row_sets).values()), default=0)
        if weeks >= MIN_WEEKS:
            break
    return merge_weekly(*row_sets)


def main() -> int:
    weekly = load_weekly(date.today())
    contracts = build_contracts(weekly)
    if not contracts:
        write_unavailable("CFTC unreachable / no tracked contracts parsed")
        return 0
    summary = summarize(contracts)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": True,
        "source": SOURCE,
        "method": ("Net = long - short per trader class from the weekly TFF futures-only "
                   "report; 1w/4w changes, selling streaks and 26-week spec lows computed "
                   "over the merged current-week + yearly history (no LLM)."),
        "contracts": contracts,
        "summary": summary,
    }
    ic.ensure_dirs()
    CFTC_POSITIONING.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"CFTC positioning ({summary['as_of']}): {summary['read']}")
    for c in contracts:
        print(f"  {c['name']:18} AM {c['am_net']:>+12,} (4w {c['am_net_change_4w']:+,})  "
              f"LF {c['lf_net']:>+12,} (4w {c['lf_net_change_4w']:+,})  "
              f"streak {c['am_selling_streak_weeks']}w  26w-low {c['lf_net_26w_low']}")
    print(f"  -> {CFTC_POSITIONING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
