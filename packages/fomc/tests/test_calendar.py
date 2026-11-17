"""Tests for the canonical FOMC meeting calendar (fomc.calendar).

Covers the 2026 -> 2027 -> Jan 2028 extension, the strategy-meeting exclusion from
decision logic, the unchanged blackout math, and the schedule-extension warning.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from fomc import calendar as cal
from fomc import export_calendar

# --- schedule shape -------------------------------------------------------------


def test_decision_dates_cover_2026_2027_and_jan_2028():
    assert cal.DECISION_DATES == (
        "2026-01-28",
        "2026-03-18",
        "2026-04-29",
        "2026-06-17",
        "2026-07-29",
        "2026-09-16",
        "2026-10-28",
        "2026-12-09",
        "2027-01-27",
        "2027-03-17",
        "2027-04-28",
        "2027-06-09",
        "2027-07-28",
        "2027-09-15",
        "2027-11-17",
        "2028-01-26",
    )


def test_meetings_sorted_ascending_and_two_day():
    ends = [m.end for m in cal.MEETINGS]
    assert ends == sorted(ends)
    for m in cal.MEETINGS:
        assert date.fromisoformat(m.end) - date.fromisoformat(m.start) == timedelta(days=1)
        assert m.source_url.startswith("https://www.federalreserve.gov/")


def test_no_december_2027_meeting():
    assert not [m for m in cal.MEETINGS if m.end.startswith("2027-12")]
    assert not [d for d in cal.DECISION_DATES if d.startswith("2027-12")]


def test_2027_meetings_are_published_by_the_november_2026_release():
    for m in cal.MEETINGS:
        if m.end >= "2027-01-01":
            assert m.published == "2026-11-12"
            assert m.source_url == cal.SOURCE_2027


# --- strategy meeting -----------------------------------------------------------


def test_october_2027_is_a_strategy_meeting_with_no_decision():
    strategy = [m for m in cal.MEETINGS if m.kind == "strategy"]
    assert len(strategy) == 1
    (m,) = strategy
    assert (m.start, m.end) == ("2027-10-26", "2027-10-27")
    assert m.decision_date is None
    assert "2027-10-27" not in cal.DECISION_DATES


def test_strategy_meeting_still_has_a_blackout():
    (m,) = [x for x in cal.MEETINGS if x.kind == "strategy"]
    # Second Saturday before Wed 2027-10-27 -> 10-16; first Thursday after -> 10-28.
    assert (m.blackout_start, m.blackout_end) == ("2027-10-16", "2027-10-28")
    assert cal.in_blackout(date(2027, 10, 20), m.end)


def test_next_meeting_finds_the_strategy_meeting_but_next_decision_skips_it():
    today = date(2027, 10, 1)
    assert cal.next_meeting(today).end == "2027-10-27"
    assert cal.next_meeting(today, kind="strategy").end == "2027-10-27"
    assert cal.next_decision(today) == "2027-11-17"


# --- next decision --------------------------------------------------------------


def test_next_decision_after_the_last_2026_meeting_is_january_2027():
    assert cal.next_decision(date(2026, 12, 10)) == "2027-01-27"
    # The decision day itself still counts as "next".
    assert cal.next_decision(date(2026, 12, 9)) == "2026-12-09"


def test_next_decision_after_september_2027_is_november_2027():
    assert cal.next_decision(date(2027, 9, 16)) == "2027-11-17"


def test_next_decision_returns_none_past_the_schedule():
    assert cal.next_decision(date(2028, 1, 27)) is None


def test_legacy_aliases_still_resolve():
    assert cal.FOMC_DECISION_DATES is cal.DECISION_DATES
    assert cal.next_fomc(date(2026, 12, 10)) == "2027-01-27"


# --- blackout math (unchanged from the 2026-only implementation) ----------------


def test_blackout_window_2026_12_09_is_unchanged():
    assert cal.blackout_start("2026-12-09") == "2026-11-28"
    assert cal.blackout_end("2026-12-09") == "2026-12-10"


def test_blackout_window_2027_01_27():
    assert cal.blackout_start("2027-01-27") == "2027-01-16"
    assert cal.blackout_end("2027-01-27") == "2027-01-28"


def test_blackout_windows_well_formed_for_every_meeting():
    for m in cal.MEETINGS:
        assert m.blackout_start < m.end < m.blackout_end
        assert date.fromisoformat(m.blackout_start).weekday() == 5  # Saturday
        assert date.fromisoformat(m.blackout_end).weekday() == 3  # Thursday


def test_in_blackout_endpoints_inclusive():
    d = "2027-01-27"
    assert cal.in_blackout(date(2027, 1, 16), d)
    assert cal.in_blackout(date(2027, 1, 27), d)
    assert cal.in_blackout(date(2027, 1, 28), d)
    assert not cal.in_blackout(date(2027, 1, 15), d)
    assert not cal.in_blackout(date(2027, 1, 29), d)


def test_days_until():
    assert cal.days_until("2027-01-27", date(2027, 1, 20)) == 7
    assert cal.days_until("2027-01-27", date(2027, 1, 28)) == -1


# --- extension reminder ---------------------------------------------------------


def test_schedule_warning_silent_while_the_horizon_is_long():
    assert cal.last_decision() == "2028-01-26"
    assert cal.schedule_warning(date(2026, 11, 17)) is None
    # Exactly at the horizon is still fine (strictly fewer than 120 days fires).
    at_horizon = date(2028, 1, 26) - timedelta(days=cal.SCHEDULE_HORIZON_DAYS)
    assert cal.schedule_warning(at_horizon) is None


def test_schedule_warning_fires_inside_the_horizon():
    inside = date(2028, 1, 26) - timedelta(days=cal.SCHEDULE_HORIZON_DAYS - 1)
    msg = cal.schedule_warning(inside)
    assert msg is not None
    assert "schedule needs extending" in msg
    assert "2028-01-26" in msg


def test_schedule_warning_still_fires_after_the_schedule_runs_out():
    msg = cal.schedule_warning(date(2028, 6, 1))
    assert msg is not None and "schedule needs extending" in msg


def test_provenance_cites_the_november_2026_release():
    prov = cal.provenance(date(2026, 11, 17))
    urls = [s["url"] for s in prov["sources"]]
    assert cal.SOURCE_2027 in urls
    assert prov["sources"][0]["published"] == "2026-11-12"
    assert prov["coverage"]["last_decision"] == "2028-01-26"
    assert prov["coverage"]["n_decisions"] == 16
    assert prov["coverage"]["n_strategy_meetings"] == 1


# --- JSON export ----------------------------------------------------------------


def test_calendar_document_shape():
    doc = cal.calendar_document(date(2026, 11, 17))
    assert doc["as_of"] == "2026-11-17"
    assert doc["next_decision"] == "2026-12-09"
    assert len(doc["meetings"]) == len(cal.MEETINGS)
    assert doc["decision_dates"] == list(cal.DECISION_DATES)
    kinds = {m["kind"] for m in doc["meetings"]}
    assert kinds == {"decision", "strategy"}


def test_export_calendar_writes_the_dashboard_json(tmp_path):
    out = tmp_path / "nested" / "fomc_calendar.json"
    export_calendar.run(out)
    doc = json.loads(out.read_text())
    assert doc["decision_dates"] == list(cal.DECISION_DATES)
    assert doc["provenance"]["coverage"]["n_strategy_meetings"] == 1


def test_export_calendar_default_target_is_the_dashboard_public_data():
    assert export_calendar.DEFAULT_JSON.parts[-4:] == (
        "fomc-dashboard",
        "public",
        "data",
        "fomc_calendar.json",
    )
