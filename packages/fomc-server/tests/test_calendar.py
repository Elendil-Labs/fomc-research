"""Blackout / schedule date math (pure logic).

The schedule itself is owned by `fomc.calendar` in the lab package and tested there
(packages/fomc/tests/test_calendar.py). These tests pin the shim's re-exported API,
the blackout values the server has always returned, and the decision-vs-strategy
split the MCP tools depend on.
"""

from datetime import date

from fomc_server import _calendar as cal


def test_blackout_window_2026_07_29():
    # Decision Wed 2026-07-29: second Saturday before = 07-18, first Thursday after = 07-30.
    assert cal.blackout_start("2026-07-29") == "2026-07-18"
    assert cal.blackout_end("2026-07-29") == "2026-07-30"


def test_blackout_window_2026_12_09_unchanged_by_the_2027_extension():
    assert cal.blackout_start("2026-12-09") == "2026-11-28"
    assert cal.blackout_end("2026-12-09") == "2026-12-10"


def test_blackout_windows_all_meetings_well_formed():
    for m in cal.MEETINGS:
        start, end = m.blackout_start, m.blackout_end
        assert start < m.end < end
        assert date.fromisoformat(start).weekday() == 5  # Saturday
        assert date.fromisoformat(end).weekday() == 3  # Thursday
        # second Saturday before is 8-14 days out
        assert 8 <= (date.fromisoformat(m.end) - date.fromisoformat(start)).days <= 14


def test_in_blackout_endpoints_inclusive():
    assert cal.in_blackout(date(2026, 7, 18), "2026-07-29")
    assert cal.in_blackout(date(2026, 7, 30), "2026-07-29")
    assert cal.in_blackout(date(2026, 7, 29), "2026-07-29")
    assert not cal.in_blackout(date(2026, 7, 17), "2026-07-29")
    assert not cal.in_blackout(date(2026, 7, 31), "2026-07-29")


def test_next_fomc_and_days_until():
    assert cal.next_fomc(date(2026, 7, 10)) == "2026-07-29"
    assert cal.next_fomc(date(2026, 7, 29)) == "2026-07-29"  # decision day counts
    # The schedule now runs through Jan 2028, so Dec 10 2026 rolls to the 2027 calendar.
    assert cal.next_fomc(date(2026, 12, 10)) == "2027-01-27"
    assert cal.next_fomc(date(2028, 1, 27)) is None  # schedule ran out
    assert cal.days_until("2026-07-29", date(2026, 7, 10)) == 19
    assert cal.days_until("2026-07-29", date(2026, 8, 1)) == -3


def test_strategy_meeting_is_not_a_decision_date():
    assert "2027-10-27" not in cal.DECISION_DATES
    assert cal.next_decision(date(2027, 10, 1)) == "2027-11-17"
    strategy = cal.next_meeting(date(2027, 10, 1), kind="strategy")
    assert strategy is not None and strategy.end == "2027-10-27"
    assert strategy.decision_date is None


def test_schedule_warning_and_provenance_are_available_through_the_shim():
    assert cal.last_decision() == "2028-01-26"
    assert cal.schedule_warning(date(2026, 11, 17)) is None
    assert "schedule needs extending" in (cal.schedule_warning(date(2027, 12, 1)) or "")
    prov = cal.provenance(date(2026, 11, 17))
    assert prov["sources"][0]["published"] == "2026-11-12"
