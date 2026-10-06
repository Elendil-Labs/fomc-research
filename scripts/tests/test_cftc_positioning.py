"""Tests for the CFTC Treasury-futures positioning collector (pure logic; no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_cftc_positioning as cp  # noqa: E402

HEADER = ('"Market_and_Exchange_Names","As_of_Date_In_Form_YYMMDD","Report_Date_as_YYYY-MM-DD",'
          '"CFTC_Contract_Market_Code","CFTC_Market_Code","CFTC_Region_Code","CFTC_Commodity_Code",'
          '"Open_Interest_All","Dealer_Positions_Long_All","Dealer_Positions_Short_All",'
          '"Dealer_Positions_Spread_All","Asset_Mgr_Positions_Long_All","Asset_Mgr_Positions_Short_All",'
          '"Asset_Mgr_Positions_Spread_All","Lev_Money_Positions_Long_All","Lev_Money_Positions_Short_All",'
          '"Lev_Money_Positions_Spread_All","Other_Rept_Positions_Long_All"')

# Real current-week row shape (no header): quoted name, then bare numbers with padding.
ROW_10Y = ('"UST 10Y NOTE - CHICAGO BOARD OF TRADE",260929,2026-09-29,043602,CBT ,00,043 , '
           '5676556,   92958,  829543,   14784, 3506513,  729982,  723861,  510579, 2547011,'
           '  119447,  262889,  315176,      75, 5231106, 5279879,  445450,  396677,  268830,'
           '  -37606,  118305')
ROW_OTHER = ('"E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",260929,2026-09-29,13874A,CME ,00,138 ,'
             ' 2000000, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10')


def _row(cid_name: str, day: str, am_long: int, am_short: int, lf_long: int, lf_short: int,
         dealer_long: int = 100, dealer_short: int = 50, oi: int = 1000) -> str:
    return (f'"{cid_name}",260101,{day},043602,CBT ,00,043 , {oi}, {dealer_long}, '
            f'{dealer_short}, 0, {am_long}, {am_short}, 0, {lf_long}, {lf_short}, 0, 0')


def test_parse_headerless_row_by_known_column_order():
    rows = cp.parse_rows(ROW_10Y + "\n" + ROW_OTHER + "\n")
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == "UST_10Y" and r["name"] == "10y T-Note"
    assert r["report_date"] == "2026-09-29"
    assert r["open_interest"] == 5676556
    assert r["dealer_net"] == 92958 - 829543
    assert r["am_net"] == 3506513 - 729982  # +2,776,531
    assert r["lf_net"] == 510579 - 2547011  # -2,036,432


def test_parse_skips_header_row_and_short_rows():
    text = HEADER + "\n" + ROW_10Y + "\n" + '"UST BOND - CHICAGO BOARD OF TRADE",1,2\n'
    rows = cp.parse_rows(text)
    assert [r["id"] for r in rows] == ["UST_10Y"]


def test_merge_dedupes_by_report_date_and_sorts_oldest_first():
    cur = cp.parse_rows(_row("UST BOND - CHICAGO BOARD OF TRADE", "2026-09-29", 10, 5, 1, 2))
    hist = cp.parse_rows("\n".join([
        _row("UST BOND - CHICAGO BOARD OF TRADE", "2026-09-29", 10, 5, 1, 2),  # duplicate week
        _row("UST BOND - CHICAGO BOARD OF TRADE", "2026-09-22", 9, 5, 1, 2),
        _row("UST BOND - CHICAGO BOARD OF TRADE", "2026-09-15", 8, 5, 1, 2),
    ]))
    weekly = cp.merge_weekly(cur, hist)
    assert [r["report_date"] for r in weekly["UST_BOND"]] == [
        "2026-09-15", "2026-09-22", "2026-09-29"]


def test_change_streak_and_stopped_selling_logic():
    assert cp.change([1, 2, 3, 4, 5], 1) == 1
    assert cp.change([1, 2, 3, 4, 5], 4) == 4
    assert cp.change([1, 2, 3], 4) is None
    # Streak counts consecutive declines back from the latest.
    assert cp.selling_streak([10, 9, 8, 7]) == 3
    assert cp.selling_streak([10, 9, 10, 8, 7]) == 2
    assert cp.selling_streak([5, 6]) == 0
    assert cp.selling_streak([5, 5]) == 0  # flat is not selling
    assert cp.selling_streak([5]) == 0
    # Stopped selling = last two weekly changes both positive.
    assert cp.stopped_selling([5, 4, 5, 6]) is True
    assert cp.stopped_selling([5, 4, 6, 6]) is False  # flat last week
    assert cp.stopped_selling([5, 6, 5, 6]) is False
    assert cp.stopped_selling([5, 6]) is False  # too short


def _weeks(am: list[int], lf: list[int],
           name: str = "UST 10Y NOTE - CHICAGO BOARD OF TRADE") -> list[dict]:
    text = "\n".join(_row(name, f"2026-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}", a, 0, lf_i, 0)
                     for i, (a, lf_i) in enumerate(zip(am, lf)))
    return cp.merge_weekly(cp.parse_rows(text))["UST_10Y"]


def test_build_contract_metrics_and_26w_low():
    am = list(range(130, 100, -1))  # 30 weeks of steady selling: 130 -> 101
    lf = [-50] * 29 + [-60]  # latest is the 26-week low
    c = cp.build_contract(_weeks(am, lf))
    assert c["id"] == "UST_10Y" and c["as_of"] == "2026-02-02"
    assert c["am_net"] == 101 and c["am_net_change_1w"] == -1 and c["am_net_change_4w"] == -4
    assert c["lf_net"] == -60 and c["lf_net_change_1w"] == -10 and c["lf_net_change_4w"] == -10
    assert c["am_selling_streak_weeks"] == 25  # capped by the 26-week window (25 changes)
    assert c["am_stopped_selling"] is False
    assert c["lf_net_26w_low"] is True
    assert len(c["history"]) == 12
    assert c["history"][0]["report_date"] < c["history"][-1]["report_date"]
    assert c["history"][-1] == {"report_date": "2026-02-02", "am_net": 101, "lf_net": -60}


def test_build_contract_26w_low_ignores_older_weeks():
    # Week 0 (outside the 26-week window) is lower than the latest; latest is still the
    # window low.
    lf = [-100] + [-50] * 28 + [-60]
    am = [10] * 27 + [8, 9, 10]  # two positive changes -> stopped selling
    c = cp.build_contract(_weeks(am, lf))
    assert c["lf_net_26w_low"] is True
    assert c["am_stopped_selling"] is True
    assert c["am_selling_streak_weeks"] == 0


def test_build_contract_short_history_yields_null_changes():
    c = cp.build_contract(_weeks([5, 4, 3], [1, 1, 0]))
    assert c["am_net_change_1w"] == -1 and c["am_net_change_4w"] is None
    assert c["lf_net_26w_low"] is True
    assert len(c["history"]) == 3


def _contract(cid: str, am4: int | None, low: bool, stopped: bool) -> dict:
    return {"id": cid, "as_of": "2026-09-29", "am_net_change_4w": am4, "lf_net_26w_low": low,
            "am_stopped_selling": stopped}


def test_summarize_distribution_and_capitulation_thresholds():
    contracts = [_contract("UST_10Y", -5, True, False), _contract("ULTRA_10Y", -1, True, True),
                 _contract("UST_BOND", -2, False, False), _contract("ULTRA_BOND", 3, False, False)]
    s = cp.summarize(contracts)
    assert s["as_of"] == "2026-09-29"
    assert s["real_money_distribution"] is True  # 3 of 4 negative
    assert s["spec_capitulation"] is True  # 2 at 26w low
    assert s["am_stopped_selling_count"] == 1
    assert "3 of 4 contracts (distribution)" in s["read"]
    # Only 2 distributing, only 1 at low -> both false; None change does not count.
    contracts = [_contract("UST_10Y", -5, True, False), _contract("ULTRA_10Y", None, False, False),
                 _contract("UST_BOND", -2, False, False), _contract("ULTRA_BOND", 3, False, False)]
    s = cp.summarize(contracts)
    assert s["real_money_distribution"] is False and s["spec_capitulation"] is False
    assert "no broad distribution" in s["read"] and "no capitulation" in s["read"]


def test_write_unavailable_writes_pending_doc(tmp_path, monkeypatch):
    monkeypatch.setattr(cp, "CFTC_POSITIONING", tmp_path / "cftc_positioning.json")
    cp.write_unavailable("CFTC unreachable")
    doc = json.loads((tmp_path / "cftc_positioning.json").read_text(encoding="utf-8"))
    assert doc["available"] is False
    assert doc["contracts"] == []
    assert doc["summary"]["real_money_distribution"] is False
    assert doc["summary"]["read"] == "unavailable"
