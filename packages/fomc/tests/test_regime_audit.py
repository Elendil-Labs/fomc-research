"""Audit tests: a Fed language change must fail LOUDLY, never silently go stale.

Covers the broadened verb set (increase/reduce/decrease/hold), audit_statements()
semantics (parsed / unparsed / stale), the alarm text, and a real-corpus canary.
"""

from pathlib import Path

import pytest
from fomc.regime import (
    _RATE_RE,
    STMT_DIR,
    audit_statements,
    build_timeline,
    format_alarm,
    parse_statements,
)

CLASSIC_HIKE = (
    "In view of realized and expected labor market conditions and inflation, the "
    "Committee decided to raise the target range for the federal funds rate to "
    "2-1/4 to 2-1/2 percent."
)
CLASSIC_HOLD = (
    "The Committee decided to maintain the target range for the federal funds rate "
    "at 2-1/4 to 2-1/2 percent."
)
CLASSIC_CUT = (
    "The Committee decided to lower the target range for the federal funds rate to "
    "2 to 2-1/4 percent."
)
# plausible Warsh-era rewrite that must NOT match the rate-sentence pattern
REWRITTEN = (
    "Consistent with its mandate, the Committee set the policy rate corridor at "
    "4 percent and will review the setting at each meeting."
)


def _write(stmt_dir: Path, iso: str, text: str, suffix: str = "a") -> None:
    stmt_dir.mkdir(parents=True, exist_ok=True)
    (stmt_dir / f"{iso}{suffix}.txt").write_text(text, encoding="utf-8")


def test_audit_happy_path(tmp_path: Path) -> None:
    _write(tmp_path, "2024-01-31", CLASSIC_HIKE)
    _write(tmp_path, "2024-03-20", CLASSIC_HOLD)
    _write(tmp_path, "2024-05-01", CLASSIC_CUT)
    (tmp_path / "notes.txt").write_text("not a dated statement", encoding="utf-8")  # ignored
    audit = audit_statements(tmp_path)
    assert audit["parsed"] == 3
    assert audit["unparsed"] == []
    assert audit["latest_statement"] == "2024-05-01"
    assert audit["latest_parsed"] == "2024-05-01"
    assert audit["stale"] is False


def test_synonym_verbs_map_to_actions(tmp_path: Path) -> None:
    _write(tmp_path, "2026-01-28",
           "The Committee decided to increase the target range for the federal funds "
           "rate to 4 to 4-1/4 percent.")
    _write(tmp_path, "2026-03-18",
           "The Committee decided to reduce the target range for the federal funds "
           "rate to 3-3/4 to 4 percent.")
    _write(tmp_path, "2026-04-29",
           "The Committee decided to decrease the target range for the federal funds "
           "rate to 3-1/2 to 3-3/4 percent.")
    _write(tmp_path, "2026-06-17",
           "The Committee decided to hold the target range for the federal funds "
           "rate at 3-1/2 to 3-3/4 percent.")
    by_date = {d.date: d for d in parse_statements(tmp_path)}
    assert by_date["2026-01-28"].action == "Hike"
    assert (by_date["2026-01-28"].target_low, by_date["2026-01-28"].target_high) == (4.0, 4.25)
    assert by_date["2026-03-18"].action == "Cut"
    assert by_date["2026-04-29"].action == "Cut"
    assert (by_date["2026-04-29"].target_low, by_date["2026-04-29"].target_high) == (3.5, 3.75)
    assert by_date["2026-06-17"].action == "Hold"
    audit = audit_statements(tmp_path)
    assert audit["parsed"] == 4 and audit["unparsed"] == [] and audit["stale"] is False


def test_word_boundary_does_not_match_withhold() -> None:
    assert _RATE_RE.search(
        "The Committee decided to withhold the target range for the federal funds "
        "rate at 4 to 4-1/4 percent."
    ) is None


def test_stale_alarm_when_newest_statement_rewritten(tmp_path: Path) -> None:
    _write(tmp_path, "2026-04-29", CLASSIC_HIKE)
    _write(tmp_path, "2026-06-17", REWRITTEN)  # newest fails to parse
    audit = audit_statements(tmp_path)
    assert audit["stale"] is True
    assert audit["latest_statement"] == "2026-06-17"
    assert audit["latest_parsed"] == "2026-04-29"
    assert [u["date"] for u in audit["unparsed"]] == ["2026-06-17"]
    assert audit["unparsed"][0]["file"] == "2026-06-17a.txt"
    alarm = format_alarm(audit)
    assert alarm.startswith("!! ALARM")
    assert "2026-06-17" in alarm and "2026-04-29" in alarm and "STALE" in alarm


def test_old_unparsed_file_warns_but_not_stale(tmp_path: Path) -> None:
    _write(tmp_path, "2020-03-23", "Emergency facilities announcement, no rate sentence.")
    _write(tmp_path, "2026-06-17", CLASSIC_HOLD)
    audit = audit_statements(tmp_path)
    assert [u["date"] for u in audit["unparsed"]] == ["2020-03-23"]
    assert audit["stale"] is False
    assert audit["latest_parsed"] == "2026-06-17"


def test_companion_file_with_parsed_sibling_is_not_a_failure(tmp_path: Path) -> None:
    """'b' implementation notes never contain the rate sentence; the 'a' file does."""
    _write(tmp_path, "2026-06-17", CLASSIC_HOLD, suffix="a")
    _write(tmp_path, "2026-06-17", "Decisions Regarding Monetary Policy Implementation.",
           suffix="b")
    audit = audit_statements(tmp_path)
    assert audit["parsed"] == 1
    assert audit["unparsed"] == []
    assert audit["stale"] is False


def test_hold_verb_inherits_prior_regime(tmp_path: Path) -> None:
    _write(tmp_path, "2026-04-29", CLASSIC_HIKE)
    _write(tmp_path, "2026-06-17",
           "The Committee decided to hold the target range for the federal funds "
           "rate at 2-1/4 to 2-1/2 percent.")
    timeline = build_timeline(parse_statements(tmp_path))
    assert [r["action"] for r in timeline] == ["Hike", "Hold"]
    assert timeline[-1]["regime"] == "Tightening"  # Hold inherits, state machine unchanged
    assert timeline[-1]["change_bps"] == 0


@pytest.mark.skipif(not STMT_DIR.exists(), reason="real statement corpus not present")
def test_real_corpus_canary() -> None:
    """Every real rate-setting statement parses today; the timeline is not stale.

    The corpus also holds non-rate-setting releases (emergency facility and framework
    announcements) that legitimately lack the rate sentence — they are the only
    allowed unparsed dates, and all predate the newest parsed decision.
    """
    known_non_rate_dates = {"2020-03-19", "2020-03-23", "2020-03-31", "2020-08-27", "2025-08-22"}
    audit = audit_statements()
    assert audit["parsed"] >= 60
    assert {u["date"] for u in audit["unparsed"]} <= known_non_rate_dates
    assert audit["stale"] is False
    assert audit["latest_statement"] == audit["latest_parsed"]
