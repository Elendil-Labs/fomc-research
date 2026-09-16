"""Daily price bars: CSV cache I/O and a yfinance fetch helper.

The FOMC event study needs nothing more than raw daily closes for SPY and TLT. This
module keeps that dependency small and self-contained:

  * ``DailyBar``            one OHLCV row (raw close + adjusted close)
  * ``load_csv_bars``       read a cache CSV (Date,Open,High,Low,Close,Adj. Close,Volume)
  * ``write_bars_csv``      rewrite a cache CSV in that canonical schema, sorted by date
  * ``fetch_yfinance_bars`` download daily bars via yfinance (raw, un-adjusted closes)

The CSV reader tolerates missing High / Low / Adj. Close columns (they fall back to
Close) and ignores any extra columns, so hand-exported histories load as well.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

CSV_FIELDS = ["Date", "Open", "High", "Low", "Close", "Adj. Close", "Volume"]


@dataclass(frozen=True)
class DailyBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


def _parse_float(value: str | None, fallback: float | None = None) -> float:
    cleaned = (value or "").replace(",", "").strip()
    if not cleaned:
        if fallback is None:
            raise ValueError("empty numeric cell")
        return fallback
    return float(cleaned)


def _parse_int(value: str | None) -> int:
    cleaned = (value or "").replace(",", "").strip()
    if not cleaned:
        return 0
    return int(float(cleaned))


def load_csv_bars(path: Path) -> dict[date, DailyBar]:
    """Read a daily-bar CSV into ``{date: DailyBar}``.

    Requires Date, Open, Close and Volume columns; High, Low and Adj. Close are optional
    and default to Close when absent or blank.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}")

    bars: dict[date, DailyBar] = {}
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"Date", "Open", "Close", "Volume"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing required columns: {sorted(missing)}")
        for row in reader:
            raw_date = (row.get("Date") or "").strip()
            if not raw_date:
                continue
            d = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
            close_px = _parse_float(row["Close"])
            bars[d] = DailyBar(
                date=d,
                open=_parse_float(row["Open"], close_px),
                high=_parse_float(row.get("High"), close_px),
                low=_parse_float(row.get("Low"), close_px),
                close=close_px,
                adj_close=_parse_float(row.get("Adj. Close"), close_px),
                volume=_parse_int(row.get("Volume")),
            )
    return bars


def write_bars_csv(path: Path, bars: dict[date, DailyBar]) -> None:
    """Rewrite ``path`` in the canonical schema, rows sorted by ascending date.

    OHLC are stored to the cent and the adjusted close to 3 decimals: that is the
    precision the event-truth table was originally built from, and yfinance's extra
    sub-cent digits would otherwise flip the last decimal of a few settled returns.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for d in sorted(bars):
            bar = bars[d]
            writer.writerow(
                {
                    "Date": d.isoformat(),
                    "Open": f"{bar.open:.2f}",
                    "High": f"{bar.high:.2f}",
                    "Low": f"{bar.low:.2f}",
                    "Close": f"{bar.close:.2f}",
                    "Adj. Close": f"{bar.adj_close:.3f}",
                    "Volume": str(int(bar.volume)),
                }
            )


# ---------------------------------------------------------------- yfinance


def _flatten_yf_columns(df: Any, ticker: str) -> Any:
    """Collapse yfinance's MultiIndex columns (('Close','SPY'), ...) to plain names.

    Newer yfinance versions return a (field, ticker) MultiIndex even for a single
    ticker; older ones return flat columns. Handle both, and either level order.
    """
    cols = getattr(df, "columns", None)
    if cols is None or getattr(cols, "nlevels", 1) == 1:
        return df
    for level in range(cols.nlevels):
        values = list(cols.get_level_values(level))
        if ticker in values or ticker.upper() in [str(v).upper() for v in values]:
            try:
                return df.xs(ticker, axis=1, level=level)
            except KeyError:
                continue
    # Fall back to the first level that looks like OHLC field names.
    for level in range(cols.nlevels):
        values = {str(v) for v in cols.get_level_values(level)}
        if "Close" in values:
            df = df.copy()
            df.columns = cols.get_level_values(level)
            return df
    df = df.copy()
    df.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in cols]
    return df


def _cell(row: Any, name: str, fallback: float) -> float:
    try:
        value = row[name]
    except (KeyError, IndexError):
        return fallback
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return fallback if math.isnan(value) else value


def fetch_yfinance_bars(
    ticker: str,
    start: date | None = None,
    end: date | None = None,
) -> dict[date, DailyBar]:
    """Download daily bars for ``ticker`` via yfinance.

    Closes are raw (``auto_adjust=False``); the adjusted close is kept alongside.
    With neither ``start`` nor ``end`` the full available history is fetched
    (``period="max"``). ``end`` is inclusive.
    """
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - dependency present via pyproject
        raise RuntimeError("yfinance is not installed (add it with `uv sync`)") from exc

    kwargs: dict[str, Any] = {
        "interval": "1d",
        "auto_adjust": False,
        "actions": False,
        "progress": False,
    }
    if start is not None:
        kwargs["start"] = start.isoformat()
    if end is not None:
        kwargs["end"] = (end + timedelta(days=1)).isoformat()
    if start is None and end is None:
        kwargs["period"] = "max"

    df = yf.download(ticker, **kwargs)
    if df is None or len(df) == 0:
        return {}
    df = _flatten_yf_columns(df, ticker)

    out: dict[date, DailyBar] = {}
    for idx, row in df.iterrows():
        try:
            row_date = idx.date()
        except AttributeError:
            row_date = datetime.strptime(str(idx)[:10], "%Y-%m-%d").date()
        close_px = _cell(row, "Close", math.nan)
        open_px = _cell(row, "Open", math.nan)
        if math.isnan(close_px) or math.isnan(open_px):
            continue
        out[row_date] = DailyBar(
            date=row_date,
            open=open_px,
            high=_cell(row, "High", close_px),
            low=_cell(row, "Low", close_px),
            close=close_px,
            adj_close=_cell(row, "Adj Close", close_px),
            volume=int(_cell(row, "Volume", 0.0)),
        )
    return out
