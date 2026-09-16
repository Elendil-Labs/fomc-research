"""Playbook conditioning, null-safe stats, and color classification (pure logic)."""

from fomc_server._playbook import color_of, condition_events, playbook_table, window_stats


def _ev(**kw):
    base = {"date": "2020-01-01", "regime": "Easing", "action": "Hold", "emergency": False}
    base.update(kw)
    return base


def test_condition_excludes_emergency_and_matches_regime():
    events = [
        _ev(),
        _ev(emergency=True),
        _ev(regime="Tightening"),
        _ev(regime=None),
        _ev(action="Cut"),
    ]
    got = condition_events(events, "Easing")
    assert len(got) == 2
    assert all(not e["emergency"] and e["regime"] == "Easing" for e in got)
    # missing regime is treated as "Unknown"
    assert len(condition_events(events, "Unknown")) == 1
    # action filter
    assert len(condition_events(events, "Easing", action="Cut")) == 1


def test_window_stats_null_safety():
    events = [_ev(spy_d0=1.0), _ev(spy_d0=None), _ev(), _ev(spy_d0=-2.0), _ev(spy_d0=0.0)]
    s = window_stats(events, "spy_d0")
    assert s["n"] == 3
    assert s["mean"] == round((1.0 - 2.0 + 0.0) / 3, 2)
    assert s["median"] == 0.0
    # win_rate counts strictly > 0 observations
    assert s["win_rate"] == round(1 / 3, 4)


def test_window_stats_empty():
    assert window_stats([], "spy_p5") == {"n": 0, "mean": None, "median": None, "win_rate": None}
    assert window_stats([_ev(spy_p5=None)], "spy_p5")["n"] == 0


def test_playbook_table_shape():
    grid = playbook_table([_ev(spy_d0=1.0, tlt_d0=-0.5)])
    assert set(grid) == {"spy", "tlt"}
    assert set(grid["spy"]) == {"d0", "p1", "p3", "p5", "p10"}
    assert grid["spy"]["d0"]["n"] == 1
    assert grid["tlt"]["d0"]["win_rate"] == 0.0
    assert grid["spy"]["p10"]["n"] == 0


def test_color_classification_zero_is_up():
    assert color_of(0.0, 0.0) == "green"
    assert color_of(0.5, 0.1) == "green"
    assert color_of(0.0, -0.1) == "orange"
    assert color_of(-0.1, 0.0) == "blue"
    assert color_of(-0.1, -0.1) == "red"
    assert color_of(None, 0.5) is None
    assert color_of(0.5, None) is None
