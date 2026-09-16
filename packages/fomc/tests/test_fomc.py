"""Offline unit tests for the fomc package (no network)."""

from datetime import date

import pytest
from fomc import event_study, fetch, speeches, warsh


def test_ymd_to_iso():
    assert fetch._ymd_to_iso("20240131") == "2024-01-31"
    assert speeches._ymd_to_iso("20201216") == "2020-12-16"


def test_extract_text_html_strips_chrome():
    html = b"""
    <html><body>
      <nav>menu junk</nav>
      <div id="article"><h1>FOMC statement</h1>
      <p>The Committee decided to maintain the target range.</p>
      <script>var x=1;</script></div>
      <footer>footer junk</footer>
    </body></html>
    """
    text = fetch._extract_text(html, "html")
    assert "maintain the target range" in text
    assert "menu junk" not in text
    assert "footer junk" not in text
    assert "var x" not in text


def test_statement_pattern_captures_date_and_suffix():
    pat = fetch.LINK_PATTERNS["statement"][0]
    m = pat.search("/newsevents/pressreleases/monetary20200315a.htm")
    assert m and m.group(1) == "20200315" and m.group(2) == "a"


def test_presconf_pattern_matches_landing_page():
    pat = fetch.LINK_PATTERNS["press_conference_transcript"][0]
    m = pat.search("/monetarypolicy/fomcpresconf20240131.htm")
    assert m and m.group(1) == "20240131"


def test_speech_pattern_extracts_speaker():
    pat = speeches.SOURCES["speech"][1]
    m = pat.search("/newsevents/speech/powell20240131a.htm")
    assert m and m.group(1) == "powell" and m.group(2) == "20240131" and m.group(3) == "a"


def test_warsh_catalog_integrity():
    slugs = [s.slug for s in warsh.CATALOG]
    assert len(slugs) == len(set(slugs)), "duplicate slugs in CATALOG"
    for s in warsh.CATALOG:
        assert date.fromisoformat(s.date)  # valid ISO date
        assert s.url.startswith("http")
        assert s.ext in {"pdf", "html"}
    for b in warsh.BLOCKED:
        assert {"date", "title", "venue", "url", "reason"} <= b.keys()


def test_event_study_ret_and_color():
    from datetime import date as _d
    dates = [_d(2024, 1, i) for i in range(1, 8)]
    series = {d: float(100 + i) for i, d in enumerate(dates)}  # 100,101,...,106
    # return from idx 0 (100) to idx 5 (105) = 5%
    assert round(event_study._ret(series, dates, 0, 5), 4) == 0.05
    assert event_study._ret(series, dates, -1, 5) is None  # out of range
    assert event_study._ret(series, dates, 0, 99) is None
    assert event_study._color(0.01, 0.01) == "Green"
    assert event_study._color(0.01, -0.01) == "Orange"
    assert event_study._color(-0.01, 0.01) == "Blue"
    assert event_study._color(-0.01, -0.01) == "Red"
    assert event_study._color(None, 0.01) == ""


def test_event_study_percentile():
    sample = [-0.02, -0.01, 0.0, 0.01, 0.02]
    assert event_study.percentile(0.0, sample) == 60.0  # 3 of 5 <= 0.0
    assert event_study.percentile(0.03, sample) == 100.0
    assert event_study.percentile(None, sample) is None


def test_event_study_summ():
    d = event_study._summ([0.01, -0.01, 0.02, None])
    assert d["n"] == 3
    assert d["hit_rate_pct"] == round(100 * 2 / 3, 1)


def test_backtest_stats():
    from fomc import backtest
    s = backtest._stats([0.02, -0.01, 0.03, 0.01])
    assert s["n"] == 4
    assert s["win_rate_pct"] == 75.0
    # compounded total of [+2%,-1%,+3%,+1%]
    expected = (1.02 * 0.99 * 1.03 * 1.01 - 1) * 100
    assert abs(s["total_return_pct"] - round(expected, 2)) < 0.01
    assert backtest._stats([])["n"] == 0


def test_dip_analysis_summ_and_chair():
    from datetime import date as _d

    from fomc import dip_analysis, event_study
    s = dip_analysis._summ([-0.01, 0.02, 0.03])
    assert s["n"] == 3 and s["win_pct"] == round(100 * 2 / 3, 1)
    assert dip_analysis._summ([None, None])["n"] == 0
    # chair attribution boundaries
    assert event_study._chair_for(_d(2018, 1, 31)) == "Yellen"   # pre-Powell
    assert event_study._chair_for(_d(2018, 3, 21)) == "Powell"   # Powell's first
    assert event_study._chair_for(_d(2026, 6, 17)) == "Warsh"    # Warsh's first


def test_regime_parse_rate():
    from fomc import regime
    assert regime._parse_rate("3-1/2") == 3.5
    assert regime._parse_rate("5-1/4") == 5.25
    assert regime._parse_rate("0") == 0.0
    assert regime._parse_rate("1/4") == 0.25
    assert regime._parse_rate("2‑1/2") == 2.5  # unicode non-breaking hyphen


def test_regime_statement_parsing_and_state_machine():
    from fomc import regime
    decisions = regime.parse_statements()
    assert len(decisions) > 50
    bydate = {x.date: x for x in decisions}
    # known decisions from primary text
    assert bydate["2018-12-19"].action == "Hike" and bydate["2018-12-19"].target_high == 2.5
    assert bydate["2020-03-15"].action == "Cut" and bydate["2020-03-15"].target_low == 0.0
    assert bydate["2023-07-26"].action == "Hike" and bydate["2023-07-26"].target_high == 5.5
    tl = regime.build_timeline(decisions)
    spans = {r["date"]: r["regime"] for r in tl}
    assert spans["2018-12-19"] == "Tightening"
    assert spans["2021-07-28"] == "Easing"   # ZLB hold inherits easing
    assert spans["2023-07-26"] == "Tightening"


def test_regime_on_boundaries():
    from fomc import regime
    tl = regime.build_timeline()
    assert regime.regime_on("2023-01-01", tl)["regime"] == "Tightening"
    assert regime.regime_on("2025-01-01", tl)["regime"] == "Easing"
    assert regime.regime_on("1990-01-01", tl)["regime"] == "Unknown"  # before data


def test_cli_dispatch():
    from fomc import cli
    # every advertised command maps to a callable main
    expected = {"status", "regime", "truth", "study", "dips", "backtest",
                "fetch", "speeches", "warsh"}
    assert expected <= set(cli.COMMANDS)
    for _help, fn in cli.COMMANDS.values():
        assert callable(fn)
    assert cli.main(["--help"]) == 0
    assert cli.main([]) == 0
    assert cli.main(["bogus-cmd"]) == 2  # unknown command


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_write_manifest_merges_with_existing(tmp_path):
    """A filtered fetch must not erase manifest entries it did not touch.

    Regression: `fomc.fetch --types statement --since ...` used to rewrite
    manifest.json with only the docs from that run, destroying the corpus index
    (event universe -> 0 rows, truth table crash).
    """
    def doc(doc_type, meeting_date, suffix="a", text_path="x.txt"):
        return fetch.FomcDoc(
            doc_type=doc_type, meeting_date=meeting_date, suffix=suffix,
            url=f"https://example.gov/{doc_type}/{meeting_date}", ext="html",
            text_path=text_path,
        )

    # First run: full corpus (statement + minutes for an old meeting).
    fetch.write_manifest([doc("statement", "2026-06-17"), doc("minutes", "2026-06-17", suffix="")], tmp_path)
    # Second run: filtered fetch of a NEW statement only.
    fetch.write_manifest([doc("statement", "2026-07-29")], tmp_path)

    import json as _json
    m = _json.loads((tmp_path / "manifest.json").read_text())
    keys = {(d["doc_type"], d["meeting_date"]) for d in m["documents"]}
    assert keys == {("statement", "2026-06-17"), ("minutes", "2026-06-17"), ("statement", "2026-07-29")}
    assert m["doc_count"] == 3
    meeting_dates = [mt["meeting_date"] for mt in m["meetings"]]
    assert meeting_dates == ["2026-06-17", "2026-07-29"]
    # Re-fetching the SAME doc replaces, not duplicates.
    fetch.write_manifest([doc("statement", "2026-07-29", text_path="y.txt")], tmp_path)
    m = _json.loads((tmp_path / "manifest.json").read_text())
    assert m["doc_count"] == 3
    stmt = [d for d in m["documents"] if d["meeting_date"] == "2026-07-29"][0]
    assert stmt["text_path"] == "y.txt"
