"""Corpus tools: search over the REAL Fed corpus in this worktree, redline of two
REAL statements, plus a synthetic tmp-dir statement pair with known edits."""

import pytest

from fomc_server._paths import ENV_REPO_ROOT
from fomc_server.tools.corpus import diff_statements, search_fed_corpus

# ---------------------------------------------------------------- search (real corpus)


def test_search_plain_query_statements():
    out = search_fed_corpus("target range", doc_types=["statement"], limit=20)
    assert "error" not in out, out.get("error")
    # "target range" compiles fine as a regex, so it auto-detects as regex
    assert out["pattern_type"] == "regex"
    # boilerplate phrase: the vast majority of the 80+ statements carry it
    assert out["files_matched"] >= 60
    assert out["files_searched"] >= out["files_matched"]
    assert 0 < out["n_hits"] <= 20
    for hit in out["hits"]:
        assert set(hit) == {"date", "doc_type", "file", "snippet"}
        assert hit["doc_type"] == "statement"
        assert "«" in hit["snippet"] and "»" in hit["snippet"]
        assert "\n" not in hit["snippet"]  # whitespace-normalized
    # newest files first
    dates = [h["date"] for h in out["hits"]]
    assert dates == sorted(dates, reverse=True)
    assert set(out["provenance"]) >= {"data_as_of", "retrieved_at", "source", "is_stale"}


def test_search_regex_query():
    out = search_fed_corpus(r"balance\s+sheet", doc_types=["statement", "minutes"], limit=10)
    assert "error" not in out
    assert out["pattern_type"] == "regex"
    assert out["n_hits"] > 0
    assert all(h["doc_type"] in ("statement", "minutes") for h in out["hits"])


def test_search_speech_dates_extracted_despite_speaker_prefix():
    # speech/testimony filenames look like powell_2020-04-09a.txt — date is not a prefix
    out = search_fed_corpus("inflation", doc_types=["speech", "testimony"], limit=10)
    assert "error" not in out
    assert out["n_hits"] > 0
    import re as _re

    assert all(_re.fullmatch(r"\d{4}-\d{2}-\d{2}", h["date"]) for h in out["hits"])


def test_search_invalid_regex_falls_back_to_substring():
    # "(" is not a valid regex -> escaped substring search, no error
    out = search_fed_corpus("(", doc_types=["statement"], limit=5)
    assert "error" not in out
    assert out["pattern_type"] == "substring"


def test_search_doc_type_filter_and_validation():
    warsh = search_fed_corpus("policy", doc_types=["warsh"], limit=50)
    assert "error" not in warsh
    assert all(h["doc_type"] == "warsh" for h in warsh["hits"])
    assert 0 < warsh["files_searched"] <= 10  # small file set
    assert "error" in search_fed_corpus("policy", doc_types=["blog"])


def test_search_per_file_cap_and_limit():
    # "the" matches everywhere: per-file cap (3) and the global limit must both hold
    out = search_fed_corpus("the", doc_types=["statement"], limit=50)
    assert out["n_hits"] <= 50
    per_file: dict[str, int] = {}
    for h in out["hits"]:
        per_file[h["file"]] = per_file.get(h["file"], 0) + 1
    assert per_file and max(per_file.values()) <= 3


def test_search_since_until_window():
    out = search_fed_corpus("inflation", since="2026-01-01", until="2026-12-31", limit=100)
    assert "error" not in out
    assert out["n_hits"] > 0
    assert all(h["date"].startswith("2026") for h in out["hits"])


# ---------------------------------------------------------------- diff (real statements)


def test_diff_real_april_vs_june():
    out = diff_statements("2026-04-29", "2026-06-17")
    assert "error" not in out, out.get("error")
    assert out["date_a"] == "2026-04-29" and out["date_b"] == "2026-06-17"
    assert out["file_a"] == "2026-04-29a.txt" and out["file_b"] == "2026-06-17a.txt"
    assert out["unified_diff"] and len(out["unified_diff"]) <= 8000 + 30
    s = out["summary"]
    assert set(s) == {"n_added", "n_removed", "n_changed"}
    assert s["n_added"] == len(out["added"])
    assert s["n_removed"] == len(out["removed"])
    assert s["n_changed"] == len(out["changed_pairs"])
    # two different statements: SOMETHING changed
    assert s["n_added"] + s["n_removed"] + s["n_changed"] > 0
    for pair in out["changed_pairs"]:
        assert set(pair) == {"from", "to"} and pair["from"] != pair["to"]


def test_diff_defaults_pick_two_newest_statements():
    out = diff_statements()
    assert "error" not in out
    assert out["date_b"] > out["date_a"]
    # defaults must equal the explicit newest-pair diff
    explicit = diff_statements(out["date_a"], out["date_b"])
    assert explicit["summary"] == out["summary"]


def test_diff_unknown_date_is_error():
    assert "error" in diff_statements("1999-01-01", "2026-06-17")


# ---------------------------------------------------------------- diff (synthetic pair)

OLD_STMT = (
    "The Committee decided to maintain the target range at 4 percent. "
    "Inflation remains elevated. "
    "The labor market is strong. "
    "This sentence will be removed entirely."
)
NEW_STMT = (
    "The Committee decided to maintain the target range at 4 percent. "
    "Inflation has moved closer to the objective. "
    "The labor market is strong. "
    "This sentence is brand new."
)


@pytest.fixture
def synthetic_root(tmp_path, monkeypatch):
    stmt = tmp_path / "fomc-spy-tlt-lab" / "data" / "fomc" / "statement" / "text"
    stmt.mkdir(parents=True)
    (stmt / "2025-01-01a.txt").write_text(OLD_STMT, encoding="utf-8")
    (stmt / "2025-03-01a.txt").write_text(NEW_STMT, encoding="utf-8")
    # a 'b' release that must LOSE to the 'a' release for the same date
    (stmt / "2025-03-01b.txt").write_text("Decoy text.", encoding="utf-8")
    monkeypatch.setenv(ENV_REPO_ROOT, str(tmp_path))
    return tmp_path


def test_diff_synthetic_known_edits(synthetic_root):
    out = diff_statements()
    assert "error" not in out, out.get("error")
    assert out["date_a"] == "2025-01-01" and out["date_b"] == "2025-03-01"
    assert out["file_b"] == "2025-03-01a.txt"  # 'a' release preferred over 'b'
    assert out["summary"] == {"n_added": 0, "n_removed": 0, "n_changed": 2}
    changed = {p["from"]: p["to"] for p in out["changed_pairs"]}
    assert changed["Inflation remains elevated."] == (
        "Inflation has moved closer to the objective."
    )
    assert changed["This sentence will be removed entirely."] == "This sentence is brand new."


def test_diff_synthetic_pure_add_remove(synthetic_root, monkeypatch):
    stmt = (
        synthetic_root / "fomc-spy-tlt-lab" / "data" / "fomc" / "statement" / "text"
    )
    (stmt / "2025-05-01a.txt").write_text(
        NEW_STMT + " An extra closing sentence appears.", encoding="utf-8"
    )
    out = diff_statements("2025-03-01", "2025-05-01")
    assert out["added"] == ["An extra closing sentence appears."]
    assert out["removed"] == [] and out["changed_pairs"] == []
    reverse = diff_statements("2025-05-01", "2025-03-01")
    assert reverse["removed"] == ["An extra closing sentence appears."]
    assert reverse["added"] == []


def test_search_synthetic_counts(synthetic_root):
    out = search_fed_corpus("target range", limit=10)
    assert out["files_searched"] == 3
    assert out["files_matched"] == 2  # decoy 'b' release has no match
    assert out["n_hits"] == 2
