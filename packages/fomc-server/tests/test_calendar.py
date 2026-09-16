"""Blackout / schedule date math (pure logic)."""

from datetime import date

from fomc_server import _calendar as cal


def test_blackout_window_2026_07_29():
    # Decision Wed 2026-07-29: second Saturday before = 07-18, first Thursday after = 07-30.
    assert cal.blackout_start("2026-07-29") == "2026-07-18"
    assert cal.blackout_end("2026-07-29") == "2026-07-30"


def test_blackout_windows_all_2026_meetings_well_formed():
    for d in cal.FOMC_DECISION_DATES:
        start, end = cal.blackout_start(d), cal.blackout_end(d)
        assert start < d < end
        assert date.fromisoformat(start).weekday() == 5  # Saturday
        assert date.fromisoformat(end).weekday() == 3  # Thursday
        # second Saturday before is 8-14 days out
        assert 8 <= (date.fromisoformat(d) - date.fromisoformat(start)).days <= 14


def test_in_blackout_endpoints_inclusive():
    assert cal.in_blackout(date(2026, 7, 18), "2026-07-29")
    assert cal.in_blackout(date(2026, 7, 30), "2026-07-29")
    assert cal.in_blackout(date(2026, 7, 29), "2026-07-29")
    assert not cal.in_blackout(date(2026, 7, 17), "2026-07-29")
    assert not cal.in_blackout(date(2026, 7, 31), "2026-07-29")


def test_next_fomc_and_days_until():
    assert cal.next_fomc(date(2026, 7, 10)) == "2026-07-29"
    assert cal.next_fomc(date(2026, 7, 29)) == "2026-07-29"  # decision day counts
    assert cal.next_fomc(date(2026, 12, 10)) is None  # schedule ran out
    assert cal.days_until("2026-07-29", date(2026, 7, 10)) == 19
    assert cal.days_until("2026-07-29", date(2026, 8, 1)) == -3
