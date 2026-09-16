"""fomc.prices CSV cache I/O + the event_study cache-extension logic (no network)."""

from datetime import date

import pytest
from fomc import event_study, prices
from fomc.prices import DailyBar


def _bar(d: date, close: float) -> DailyBar:
    return DailyBar(date=d, open=close, high=close, low=close, close=close,
                    adj_close=close, volume=100)


def test_csv_round_trip(tmp_path):
    bars = {date(2024, 1, 2): _bar(date(2024, 1, 2), 100.5),
            date(2024, 1, 3): _bar(date(2024, 1, 3), 101.25)}
    path = tmp_path / "X.csv"
    prices.write_bars_csv(path, bars)
    header = path.read_text().splitlines()[0]
    assert header == "Date,Open,High,Low,Close,Adj. Close,Volume"
    assert prices.load_csv_bars(path) == bars


def test_load_csv_tolerates_missing_high_low_adj_and_extra_columns(tmp_path):
    path = tmp_path / "X.csv"
    path.write_text("Date,Open,Close,Change,Volume\n2024-01-02,10,11,+1.00%,\"1,000\"\n")
    bars = prices.load_csv_bars(path)
    bar = bars[date(2024, 1, 2)]
    assert (bar.high, bar.low, bar.adj_close) == (11.0, 11.0, 11.0)
    assert bar.volume == 1000  # comma-grouped ints parse


def test_load_csv_missing_required_column(tmp_path):
    path = tmp_path / "X.csv"
    path.write_text("Date,Close\n2024-01-02,11\n")
    with pytest.raises(ValueError):
        prices.load_csv_bars(path)
    with pytest.raises(FileNotFoundError):
        prices.load_csv_bars(tmp_path / "missing.csv")


def test_flatten_yf_multiindex_columns():
    pd = pytest.importorskip("pandas")
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    cols = pd.MultiIndex.from_product([["Close", "Open", "Volume"], ["SPY"]])
    df = pd.DataFrame([[1.0, 2.0, 3], [4.0, 5.0, 6]], index=idx, columns=cols)
    flat = prices._flatten_yf_columns(df, "SPY")
    assert list(flat.columns) == ["Close", "Open", "Volume"]
    assert float(flat["Close"].iloc[1]) == 4.0
    # flat frames pass through untouched
    assert prices._flatten_yf_columns(flat, "SPY") is flat


# ---------------------------------------------------------------- cache logic


def test_cache_missing_no_fetch_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="--no-fetch"):
        event_study._load_cached_bars("SPY", tmp_path / "SPY-history.csv", do_fetch=False)


def test_cache_missing_fetch_seeds_period_max(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(ticker, start=None, end=None):
        calls.append((ticker, start, end))
        return {date(2024, 1, 2): _bar(date(2024, 1, 2), 1.0)}

    monkeypatch.setattr(event_study, "fetch_yfinance_bars", fake_fetch)
    cache = tmp_path / "SPY-history.csv"
    bars = event_study._load_cached_bars("SPY", cache, do_fetch=True)
    assert calls == [("SPY", None, None)]  # period=max path
    assert cache.exists() and prices.load_csv_bars(cache) == bars


def test_cache_extends_only_past_cache_end_and_rewrites(tmp_path, monkeypatch):
    cache = tmp_path / "TLT-history.csv"
    d1, d2, d3 = date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)
    prices.write_bars_csv(cache, {d1: _bar(d1, 10.0), d2: _bar(d2, 11.0)})
    calls = []

    def fake_fetch(ticker, start=None, end=None):
        calls.append((ticker, start, end))
        # overlapping revised value for d2 must NOT overwrite the cached close
        return {d2: _bar(d2, 999.0), d3: _bar(d3, 12.0)}

    monkeypatch.setattr(event_study, "fetch_yfinance_bars", fake_fetch)
    bars = event_study._load_cached_bars("TLT", cache, do_fetch=True)
    assert calls[0][1] == d2 - event_study.timedelta(days=7)
    assert {d: b.close for d, b in bars.items()} == {d1: 10.0, d2: 11.0, d3: 12.0}
    assert {d: b.close for d, b in prices.load_csv_bars(cache).items()}[d3] == 12.0


def test_cache_present_no_fetch_loads_as_is(tmp_path, monkeypatch):
    cache = tmp_path / "SPY-history.csv"
    d1 = date(2024, 1, 2)
    prices.write_bars_csv(cache, {d1: _bar(d1, 10.0)})
    monkeypatch.setattr(event_study, "fetch_yfinance_bars",
                        lambda *a, **k: pytest.fail("must not fetch"))
    assert set(event_study._load_cached_bars("SPY", cache, do_fetch=False)) == {d1}


def test_load_prices_returns_common_dates(tmp_path, monkeypatch):
    spy_csv, tlt_csv = tmp_path / "SPY.csv", tmp_path / "TLT.csv"
    d1, d2, d3 = date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)
    prices.write_bars_csv(spy_csv, {d1: _bar(d1, 1.0), d2: _bar(d2, 2.0)})
    prices.write_bars_csv(tlt_csv, {d2: _bar(d2, 3.0), d3: _bar(d3, 4.0)})
    monkeypatch.setattr(event_study, "SPY_CSV", spy_csv)
    monkeypatch.setattr(event_study, "TLT_CSV", tlt_csv)
    dates, spy, tlt = event_study.load_prices(do_fetch=False)
    assert dates == [d2]
    assert spy[d2] == 2.0 and tlt[d2] == 3.0
