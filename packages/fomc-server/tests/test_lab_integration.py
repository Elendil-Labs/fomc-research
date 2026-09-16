"""Lab-package integration: the workspace (editable) install keeps fomc.regime's
__file__-derived paths pointing INSIDE the lab root, and get_stated_regime reads the
real corpus."""

from fomc import regime as lab_regime

from fomc_server import _paths
from fomc_server.tools.stated import get_stated_regime


def test_editable_install_resolves_statement_dir():
    # STMT_DIR is derived from fomc.regime.__file__; the editable install must keep it
    # inside the lab worktree, and the corpus must actually be there.
    stmt_dir = lab_regime.STMT_DIR.resolve()
    assert _paths.lab_root().resolve() in stmt_dir.parents
    assert stmt_dir.is_dir()
    assert any(stmt_dir.glob("*.txt"))


def test_stated_regime_easing_on_2026_07_01():
    out = get_stated_regime("2026-07-01")
    assert "error" not in out, out.get("error")
    assert out["regime"] == "Easing"
    assert out["query_date"] == "2026-07-01"
    assert out["as_of"] <= "2026-07-01"
    audit = out["audit"]
    assert audit["stale"] is False
    assert "ALARM" not in out
    assert audit["parsed"] > 0
    assert set(audit) >= {"parsed", "unparsed", "latest_statement", "latest_parsed", "stale"}
    prov = out["provenance"]
    assert set(prov) >= {"data_as_of", "retrieved_at", "source", "is_stale"}


def test_stated_regime_defaults_to_today():
    out = get_stated_regime()
    assert "error" not in out
    assert out["regime"] in ("Easing", "Tightening", "Unknown")
