"""Long-end bottom watch — has the long end of the curve bottomed? (hard data, no LLM).

The two analog bottoms are the yardstick: 2022-10-24 (10y real yield 1.74, ACM 10y
term premium -0.10, MOVE ~160) and 2023-10-19 (real 2.52, term premium 0.45, MOVE
~130). Valuation boxes ask whether the long end is as cheap as it was at the 2023
bottom; timing boxes ask whether the market is showing the stress/stall that marked
both bottoms. Context rows carry the levels the read is made from.

Sources: FRED API (DFII10, T10YIE, DGS2, DGS5, DGS10, DGS30, MORTGAGE30US), the NY Fed
ACM term-premium workbook (served as a BIFF8 .xls at the .csv URL — read with
xlrd), and the ICE BofA MOVE index via Yahoo (yfinance). Any
single series failing marks that indicator unavailable and keeps going; FRED failing
entirely writes {available:false} so the dashboard shows a clean pending state.

Usage:
    python scripts/collect_long_end.py     # needs FRED_API_KEY
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import _intel_common as ic
import xlrd

FRED_API = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={id}&api_key={key}&file_type=json&observation_start={start}"
)
ACM_URL = "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.csv"
ACM_SHEET = "ACM Daily"
ACM_COLUMN = "ACMTP10"
MOVE_TICKER = "^MOVE"
LONG_END = ic.INTEL_DIR / "long_end_axis.json"
SOURCE = "FRED API + NY Fed ACM + ICE BofA MOVE (via Yahoo)"
HISTORY_DAYS = 400
LOOKBACK_DAILY = 20  # trading-day observations behind the latest
LOOKBACK_WEEKLY = 4  # weekly observations ≈ 20 trading days
STALL_BAND = 0.05  # pp: "at its 20d high" / "off its 20d high" tolerance

FRED_SERIES = ("DFII10", "T10YIE", "DGS2", "DGS5", "DGS10", "DGS30", "MORTGAGE30US")

ANALOGS = {
    "2022-10-24": {"DFII10": 1.74, "ACMTP10": -0.10, "MOVE": 160},
    "2023-10-19": {"DFII10": 2.52, "ACMTP10": 0.45, "MOVE": 130},
}

# mode: level  -> checked if latest >= threshold
#       change -> checked if change_20d <= threshold
#       stall  -> TWO_YEAR_STALL composite (see two_year_stall)
#       context-> never checked (null)
INDICATORS = [
    {"id": "DFII10", "name": "10y TIPS real yield", "unit": "%", "group": "valuation",
     "mode": "level", "threshold": 2.52, "rule": "latest >= 2.52 (2023-10-19 bottom level)",
     "note": "Real yield is the cleanest valuation anchor; the 2023 bottom printed 2.52."},
    {"id": "ACMTP10", "name": "ACM 10y term premium", "unit": "pp", "group": "valuation",
     "mode": "level", "threshold": 0.45, "rule": "latest >= 0.45 (2023-10-19 bottom level)",
     "note": "Term premium is the compensation for duration risk; it was 0.45 at the 2023 "
             "bottom and negative at the 2022 one."},
    {"id": "T10YIE", "name": "10y breakeven inflation (not an inflation panic)", "unit": "%",
     "group": "valuation", "mode": "change", "threshold": 0.05,
     "rule": "20-day change <= +0.05pp",
     "note": "A long-end bottom needs the selloff to be about term premium, not a "
             "repricing of inflation; breakevens must not be running."},
    {"id": "MOVE", "name": "MOVE index (rates vol)", "unit": "index", "group": "timing",
     "mode": "level", "threshold": 130, "rule": "latest >= 130 (2023 bottom ~130, 2022 ~160)",
     "note": "Both bottoms came with rates vol elevated; a calm MOVE says the flush has not "
             "happened yet."},
    {"id": "TWO_YEAR_STALL", "name": "Front end stalling while long end makes highs",
     "unit": "pp", "group": "timing", "mode": "stall", "threshold": -STALL_BAND,
     "rule": "DGS2 >= 0.05pp below its 20d max while DGS30 within 0.05pp of its 20d max",
     "note": "At both bottoms the 2y had stopped rising while the 30y was still printing "
             "highs: the steepening that marks the end of a long-end selloff."},
    {"id": "DGS10", "name": "10y Treasury yield", "unit": "%", "group": "context",
     "mode": "context", "note": "Level of the benchmark long rate."},
    {"id": "DGS30", "name": "30y Treasury yield", "unit": "%", "group": "context",
     "mode": "context", "note": "Level of the long bond."},
    {"id": "T10Y2Y", "name": "Curve slope (10y - 2y)", "unit": "pp", "group": "context",
     "mode": "context", "a": "DGS10", "b": "DGS2",
     "note": "Bear steepening is the long-end selloff signature; its reversal marks a bottom."},
    {"id": "FIVE_THIRTY", "name": "5s30s slope (30y - 5y)", "unit": "pp", "group": "context",
     "mode": "context", "a": "DGS30", "b": "DGS5",
     "note": "Belly-to-long slope isolates term premium from the policy path."},
    {"id": "MORTGAGE30US", "name": "30y mortgage rate (weekly)", "unit": "%",
     "group": "context", "mode": "context", "weekly": True,
     "note": "Where the long end bites the real economy."},
]

Series = list[tuple[str, float]]


# ---------------------------------------------------------------- fetchers


def fetch_series(series_id: str, key: str, start: str) -> Series:
    """Fetch a FRED series via the official API (JSON)."""
    url = FRED_API.format(id=series_id, key=key, start=start)
    req = urllib.request.Request(url, headers={"User-Agent": "elendil-labs-fomc/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    out: Series = []
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


def read_sheet(xls_bytes: bytes, sheet: str) -> list[dict[int, object]]:
    """Rows of `sheet` as {column_index: value}; date cells come back as DD-Mon-YYYY."""
    book = xlrd.open_workbook(file_contents=xls_bytes)
    ws = book.sheet_by_name(sheet)
    rows: list[dict[int, object]] = []
    for r in range(ws.nrows):
        row: dict[int, object] = {}
        for c in range(ws.ncols):
            cell = ws.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_EMPTY:
                continue
            if cell.ctype == xlrd.XL_CELL_DATE:
                row[c] = xlrd.xldate_as_datetime(cell.value, book.datemode).strftime("%d-%b-%Y")
            else:
                row[c] = cell.value
        rows.append(row)
    return rows


def parse_acm(xls_bytes: bytes, start: str, column: str = ACM_COLUMN) -> Series:
    """(iso_date, value) for `column` of the ACM Daily sheet, dates >= start."""
    rows = read_sheet(xls_bytes, ACM_SHEET)
    header = rows[0]
    cols = [c for c, v in header.items() if v == column]
    if not cols:
        raise ValueError(f"{column} not in ACM header")
    col = cols[0]
    out: Series = []
    for row in rows[1:]:
        raw_date, val = row.get(0), row.get(col)
        if not isinstance(raw_date, str) or not isinstance(val, (int, float)):
            continue
        try:
            iso = datetime.strptime(raw_date, "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue
        if iso >= start:
            out.append((iso, float(val)))
    if not out:
        raise ValueError("no ACM observations in window")
    return out


def fetch_acm(start: str) -> Series:
    req = urllib.request.Request(ACM_URL, headers={"User-Agent": "Mozilla/5.0 elendil-labs-fomc"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return parse_acm(resp.read(), start)


def fetch_move() -> Series:
    """ICE BofA MOVE index closes via Yahoo; MultiIndex columns -> Close."""
    import yfinance as yf  # optional dependency; imported lazily so FRED still works without it

    df = yf.download(MOVE_TICKER, period="6mo", progress=False, auto_adjust=False)
    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    out: Series = [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in close.items() if v == v]
    if not out:
        raise ValueError("no MOVE observations")
    return out


def fetch_all(key: str, start: str) -> dict[str, Series | None]:
    """Every raw series keyed by id; a failed fetch stores None (never raises)."""
    series: dict[str, Series | None] = {}
    for sid in FRED_SERIES:
        try:
            series[sid] = fetch_series(sid, key, start)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            print(f"  {sid}: unavailable ({str(e)[:80]})")
            series[sid] = None
    try:
        series["ACMTP10"] = fetch_acm(start)
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as e:
        print(f"  ACMTP10: unavailable ({str(e)[:80]})")
        series["ACMTP10"] = None
    try:
        series["MOVE"] = fetch_move()
    except Exception as e:  # yfinance raises a zoo of types; this must never abort the run
        print(f"  MOVE: unavailable ({str(e)[:80]})")
        series["MOVE"] = None
    return series


# ---------------------------------------------------------------- pure logic


def change_n(series: Series, n: int) -> float | None:
    """latest minus the value n observations earlier; None if the window is short."""
    if len(series) <= n:
        return None
    return round(series[-1][1] - series[-1 - n][1], 4)


def trailing_max(series: Series, n: int) -> float:
    """Max over the latest observation and the n before it."""
    return max(v for _, v in series[-(n + 1):])


def check_level(latest: float, threshold: float) -> bool:
    return latest >= threshold


def check_change(change: float | None, threshold: float) -> bool | None:
    return None if change is None else change <= threshold


def two_year_stall(dgs2: Series, dgs30: Series, n: int = LOOKBACK_DAILY,
                   band: float = STALL_BAND) -> tuple[float, bool, str]:
    """(2y distance from its 20d max in pp, checked, detail).

    Checked when the 2y has backed off its 20d max by >= band while the 30y is still
    within band of its own 20d max: front end stalling as the long end makes highs.
    """
    two, two_max = dgs2[-1][1], trailing_max(dgs2, n)
    thirty, thirty_max = dgs30[-1][1], trailing_max(dgs30, n)
    two_dist = round(two - two_max, 4)
    thirty_dist = round(thirty - thirty_max, 4)
    checked = two_dist <= -band and thirty_dist >= -band
    detail = (f"2y {two:.2f} is {abs(two_dist):.2f}pp below its 20d max {two_max:.2f}; "
              f"30y {thirty:.2f} is {abs(thirty_dist):.2f}pp below its 20d max {thirty_max:.2f}")
    return two_dist, checked, detail


def _base(ind: dict) -> dict:
    return {"id": ind["id"], "name": ind["name"], "unit": ind["unit"], "group": ind["group"],
            "threshold": ind.get("threshold"), "rule": ind.get("rule", "context only")}


def _unavailable(ind: dict) -> dict:
    return {**_base(ind), "latest": None, "as_of": None, "change_20d": None,
            "checked": None, "detail": "unavailable", "note": "unavailable"}


def _spread(series: dict[str, Series | None], ind: dict) -> Series | None:
    a, b = series.get(ind["a"]), series.get(ind["b"])
    if not a or not b:
        return None
    bv = dict(b)
    out = [(d, round(v - bv[d], 4)) for d, v in a if d in bv]
    return out or None


def build_indicator(ind: dict, series: dict[str, Series | None]) -> dict:
    """One output row from the raw series; unavailable inputs degrade, never raise."""
    mode = ind["mode"]
    if mode == "stall":
        dgs2, dgs30 = series.get("DGS2"), series.get("DGS30")
        if not dgs2 or not dgs30 or len(dgs2) < 2 or len(dgs30) < 2:
            return _unavailable(ind)
        dist, checked, detail = two_year_stall(dgs2, dgs30)
        return {**_base(ind), "latest": dist, "as_of": dgs2[-1][0],
                "change_20d": change_n(dgs2, LOOKBACK_DAILY), "checked": checked,
                "detail": detail, "note": ind["note"]}
    s = _spread(series, ind) if "a" in ind else series.get(ind["id"])
    if not s:
        return _unavailable(ind)
    as_of, latest = s[-1]
    n = LOOKBACK_WEEKLY if ind.get("weekly") else LOOKBACK_DAILY
    change = change_n(s, n)
    unit = ind["unit"]
    chg_txt = "n/a" if change is None else f"{change:+.2f}"
    detail = f"{latest:.2f} {unit} (20d {chg_txt})"
    if mode == "level":
        checked: bool | None = check_level(latest, ind["threshold"])
    elif mode == "change":
        checked = check_change(change, ind["threshold"])
    else:
        checked = None
    return {**_base(ind), "latest": round(latest, 4), "as_of": as_of, "change_20d": change,
            "checked": checked, "detail": detail, "note": ind["note"]}


def build_indicators(series: dict[str, Series | None]) -> list[dict]:
    return [build_indicator(ind, series) for ind in INDICATORS]


def summarize(indicators: list[dict]) -> dict:
    def count(group: str) -> tuple[int, int]:
        rows = [r for r in indicators if r["group"] == group]
        return sum(1 for r in rows if r["checked"] is True), len(rows)

    v, vt = count("valuation")
    t, tt = count("timing")
    missing = sum(1 for r in indicators if r["group"] != "context" and r["note"] == "unavailable")
    read = (f"{v} of {vt} valuation boxes and {t} of {tt} timing boxes checked; "
            "bottoms have needed the timing boxes.")
    if missing:
        read += f" ({missing} box{'es' if missing > 1 else ''} unavailable)"
    return {"checked": v + t, "total": vt + tt, "valuation_checked": v, "valuation_total": vt,
            "timing_checked": t, "timing_total": tt, "read": read}


# ---------------------------------------------------------------- output


def write_unavailable(reason: str) -> None:
    """Write a clean 'pending' doc so the dashboard never shows broken rows."""
    ic.ensure_dirs()
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": False,
        "reason": reason,
        "source": SOURCE,
        "analogs": ANALOGS,
        "summary": {"checked": 0, "total": 0, "valuation_checked": 0, "valuation_total": 0,
                    "timing_checked": 0, "timing_total": 0, "read": "unavailable"},
        "indicators": [],
    }
    LONG_END.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Long-end watch unavailable: {reason} -> wrote pending state.")


def main() -> int:
    key = ic.load_api_key("FRED_API_KEY")
    if not key:
        write_unavailable("FRED_API_KEY not set")
        return 0

    start = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
    series = fetch_all(key, start)
    if all(series.get(sid) is None for sid in FRED_SERIES):
        write_unavailable("FRED unreachable / all series failed")
        return 0

    indicators = build_indicators(series)
    summary = summarize(indicators)
    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "available": True,
        "source": SOURCE,
        "method": ("Deterministic level/20-day-change checks against the 2022-10 and 2023-10 "
                   "long-end bottoms; valuation boxes use the 2023 levels, timing boxes need "
                   "elevated MOVE and a stalled front end (no LLM)."),
        "analogs": ANALOGS,
        "summary": summary,
        "indicators": indicators,
    }
    ic.ensure_dirs()
    LONG_END.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Long-end watch: {summary['read']}")
    for r in indicators:
        mark = {True: "[x]", False: "[ ]", None: "[-]"}[r["checked"]]
        print(f"  {mark} {r['name']:48} {r['detail']}")
    print(f"  -> {LONG_END}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
