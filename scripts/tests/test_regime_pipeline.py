"""Tests for the regime-intelligence collect/score helpers (stdlib-only modules)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# The pipeline modules live in scripts/ and run as `python scripts/<name>.py`.
SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import _intel_common as ic  # noqa: E402
import score_regime_intel as score  # noqa: E402

# ---------------- normalization / dedupe ----------------

def test_normalize_clamps_and_defaults():
    s = ic.normalize_source(
        {
            "title": "Hot CPI",
            "url": "https://bls.gov/x",
            "publisher": "BLS",
            "score": 5,  # out of range -> clamp to 2
            "bucket": "garbage",  # invalid -> fallback
            "direction": "tightening",
        },
        fallback_bucket="inflation",
    )
    assert s is not None
    assert s.score == 2
    assert s.bucket == "inflation"
    assert s.official is True  # bls.gov hint


def test_normalize_rejects_missing_url_or_title():
    assert ic.normalize_source({"title": "x"}, "inflation") is None
    assert ic.normalize_source({"url": "https://a.com"}, "inflation") is None


def test_in_window():
    assert ic.in_window("2026-06-20T12:00:00Z", "2026-06-17") is True
    assert ic.in_window("2026-06-10", "2026-06-17") is False
    assert ic.in_window("", "2026-06-17") is True  # undated kept


def test_mark_and_merge_flags_new_and_dedupes():
    def s(url, title, pub="2026-06-20T00:00:00Z", **kw):
        return {"url": url, "title": title, "published_at": pub,
                "bucket": "inflation", "direction": "neutral", "score": 0, **kw}

    prior = [s("https://a.com/1", "CPI runs hot", collected_at="2026-06-18T00:00:00Z")]
    current = [
        s("https://a.com/1?utm=x", "CPI runs hot again"),  # same URL as prior -> carried, not new
        s("https://b.com/2", "Fed official turns hawkish"),  # genuinely new this run
        s("https://c.com/3", "Stale note", pub="2026-05-01"),  # out of window -> dropped
    ]
    now = "2026-06-23T00:00:00Z"
    merged, new_count = ic.mark_and_merge(prior, current, since="2026-06-17", now=now)
    by_url = {ic.url_key(m["url"]): m for m in merged}

    assert new_count == 1
    assert len(merged) == 2  # a.com (carried) + b.com (new); c.com out of window
    assert by_url["https://a.com/1"]["is_new"] is False
    assert by_url["https://a.com/1"]["first_seen_at"] == "2026-06-18T00:00:00Z"  # earliest wins
    assert by_url["https://b.com/2"]["is_new"] is True
    assert by_url["https://b.com/2"]["first_seen_at"] == "2026-06-23T00:00:00Z"


def test_mark_and_merge_first_run_all_new():
    cur = [{"url": "https://x.com/a", "title": "First headline", "published_at": "2026-06-20"}]
    merged, new_count = ic.mark_and_merge([], cur, since="2026-06-17", now="2026-06-23T00:00:00Z")
    assert new_count == 1
    assert merged[0]["is_new"] is True


def test_dedupe_by_url_and_title():
    mk = lambda url, title: ic.IntelSource(  # noqa: E731
        title=title, publisher="p", url=url, published_at="2026-06-20",
        bucket="inflation", direction="neutral", score=0,
        importance="medium", confidence="medium", evidence_text="", why_it_matters="",
    )
    rows = [
        mk("https://a.com/x", "Same headline here"),
        mk("https://a.com/x?utm=1", "Different title entirely now"),  # dup URL (query stripped)
        mk("https://b.com/y", "Same headline here"),  # dup title
        mk("https://c.com/z", "A genuinely fresh and distinct headline"),
    ]
    out = ic.dedupe(rows)
    assert len(out) == 2


# ---------------- scoring rubric ----------------

def test_recency_decay_buckets():
    today = date(2026, 6, 23)
    assert score.recency_decay("2026-06-20T00:00:00Z", today, False) == 1.0  # 3d
    assert score.recency_decay("2026-06-12T00:00:00Z", today, False) == 0.75  # 11d
    assert score.recency_decay("2026-06-01T00:00:00Z", today, False) == 0.5  # 22d
    assert score.recency_decay("2026-01-01T00:00:00Z", today, False) == 0.25  # old
    # official floor lifts an old primary source back to 0.5
    assert score.recency_decay("2026-01-01T00:00:00Z", today, True) == 0.5


def _src(bucket, direction, **kw):
    base = dict(
        importance="high", confidence="high", publisher="CNBC", url="https://cnbc.com/x",
        published_at="2026-06-22T00:00:00Z",
    )
    base.update(kw)
    return {"bucket": bucket, "direction": direction, **base}


def test_tier_weighting_elevates_fed_over_blog():
    today = date(2026, 6, 23)
    # Same claim_type so the test isolates the source-TIER effect.
    fed = _src("fed_communications", "tightening", publisher="Federal Reserve",
               url="https://federalreserve.gov/speech", claim_type="documented_fact")
    blog = _src("fed_communications", "tightening", publisher="Some Blog",
                url="https://blog.example.com/x", claim_type="documented_fact")
    # Same importance/confidence/recency/claim_type -> Fed weighs 2x the blog (tier 2.0 vs 1.0).
    assert round(score.weight_of(fed, today) / score.weight_of(blog, today), 2) == 2.0


def test_claim_type_of_resolves_and_falls_back():
    assert ic.claim_type_of({"claim_type": "documented_fact"}) == "documented_fact"
    assert ic.claim_type_of({"claim_type": "BOGUS"}) == "interpretation"  # invalid -> fallback
    assert ic.claim_type_of({"official": True}) == "official_data"  # unclassified official
    assert ic.claim_type_of({}) == "interpretation"  # unclassified non-official


def test_interpretation_is_discounted_vs_documented_fact():
    today = date(2026, 6, 23)
    # Same publisher/tier so the test isolates the CLAIM-TYPE effect.
    fact = _src("inflation", "tightening", claim_type="documented_fact")
    opinion = _src("inflation", "tightening", claim_type="interpretation")
    # interpretation weight is 0.4 vs 1.0 for a documented fact.
    assert round(score.weight_of(opinion, today) / score.weight_of(fact, today), 2) == 0.4


def test_direction_shares_are_weighted_and_sum_to_one():
    today = date(2026, 6, 23)
    sources = [
        _src("inflation", "tightening", publisher="BLS", url="https://bls.gov/cpi"),  # tier 1.5
        _src("employment", "easing", publisher="CNBC", url="https://cnbc.com/jobs"),  # tier 1.0
    ]
    shares, total = score.direction_shares(sources, today)
    assert round(shares["tightening"] + shares["neutral"] + shares["easing"], 6) == 1.0
    # tightening source weighs more (official tier) -> majority tightening
    assert shares["tightening"] > shares["easing"]
    assert score.evidence_dir(shares) == "tightening"


def test_descriptor_is_4_state_anchored_to_regime():
    # evidence agrees with regime -> settled
    assert score.descriptor("easing", "Easing") == "Easing"
    assert score.descriptor("tightening", "Tightening") == "Tightening"
    # evidence opposes regime -> pivot toward the evidence direction
    assert score.descriptor("tightening", "Easing") == "Potential pivot → tightening"
    assert score.descriptor("easing", "Tightening") == "Potential pivot → easing"
    # no regime anchor -> name the evidence direction
    assert score.descriptor("tightening", "Unknown") == "Tightening"


def test_conviction_scales_with_lopsidedness_and_volume():
    lop = {"tightening": 0.8, "neutral": 0.1, "easing": 0.1}
    split = {"tightening": 0.34, "neutral": 0.32, "easing": 0.34}
    assert score.conviction(lop, n=10) == "High"
    assert score.conviction(split, n=10) == "Low"
    assert score.conviction(lop, n=2) == "Low"  # thin evidence caps conviction


def test_score_buckets_reports_lean_and_share():
    today = date(2026, 6, 23)
    # Distinct URLs: keyless sources cluster by URL, so sharing _src's default URL
    # would now (correctly) collapse them into one event. Real inputs are URL-deduped
    # upstream, so distinct URLs is the representative scenario.
    sources = [
        _src("inflation", "tightening", url="https://a.com/1"),
        _src("inflation", "tightening", url="https://b.com/2"),
        _src("inflation", "easing", url="https://c.com/3"),
    ]
    buckets = score.score_buckets(sources, today)
    inf = buckets["inflation"]
    assert inf["n"] == 3  # three singleton event clusters
    assert inf["n_sources"] == 3
    assert inf["dominant"] == "tightening"
    assert inf["net"] > 0  # tightening share exceeds easing share


# ---------------- SPY/TLT market-confirmation signal ----------------

def test_inferred_lean_prefers_evidence_direction_then_regime_anchor():
    assert score.inferred_lean("tightening", "Easing") == "tightening"  # evidence wins
    assert score.inferred_lean("neutral", "Easing") == "easing"  # regime anchor fallback
    assert score.inferred_lean("neutral", "Unknown") == "neutral"  # no anchor at all


def test_spytlt_status_mapping():
    # Tightening lean: TLT down (yields up) confirms; SPY down corroborates risk tone.
    assert score.spytlt_status(-0.02, -0.02, "tightening") == "confirmed"
    assert score.spytlt_status(0.02, -0.02, "tightening") == "partial"  # SPY disagrees
    assert score.spytlt_status(-0.02, 0.001, "tightening") == "partial"  # TLT flat
    assert score.spytlt_status(0.02, 0.02, "tightening") == "not_confirmed"  # TLT up
    # Easing lean: inverse — TLT up confirms; SPY up corroborates.
    assert score.spytlt_status(0.02, 0.02, "easing") == "confirmed"
    assert score.spytlt_status(-0.02, 0.02, "easing") == "partial"
    assert score.spytlt_status(0.02, -0.001, "easing") == "partial"  # TLT flat
    assert score.spytlt_status(-0.02, -0.02, "easing") == "not_confirmed"  # TLT down
    # No directional macro read -> nothing to confirm.
    assert score.spytlt_status(0.02, 0.02, "neutral") == "unknown"
    # Boundary is inclusive-neutral (matches the market-pricing axis dead zone):
    # a return sitting exactly ON the flat band reads as flat, not a move.
    assert score.spytlt_status(-0.02, -score.SPYTLT_FLAT, "tightening") == "partial"
    assert score.spytlt_status(-0.02, -(score.SPYTLT_FLAT + 1e-9), "tightening") == "confirmed"


def _closes_fetcher(last_over_first: dict[str, float]):
    """Fake fetch_closes: 12 daily closes moving linearly to last/first = given ratio."""
    def fetch(ticker: str, start: date, end: date) -> dict[date, float]:
        ratio = last_over_first[ticker]
        return {
            date(2026, 7, 1) + timedelta(days=i): 100.0 * (1 + (ratio - 1) * i / 11)
            for i in range(12)
        }
    return fetch


def test_compute_spytlt_signal_tightening_lean_tlt_down_confirms():
    fetch = _closes_fetcher({"SPY": 0.97, "TLT": 0.96})  # both down ~3-4%
    out = score.compute_spytlt_signal("tightening", date(2026, 7, 12), fetch_closes=fetch)
    assert out is not None
    assert out["status"] == "confirmed"
    assert out["window_days"] == score.SPYTLT_WINDOW
    assert out["tlt_ret"] < -score.SPYTLT_FLAT
    assert out["as_of"] == "2026-07-12"


def test_compute_spytlt_signal_easing_lean_tlt_down_not_confirmed():
    fetch = _closes_fetcher({"SPY": 1.02, "TLT": 0.96})
    out = score.compute_spytlt_signal("easing", date(2026, 7, 12), fetch_closes=fetch)
    assert out is not None and out["status"] == "not_confirmed"


def test_compute_spytlt_signal_flat_tlt_is_partial():
    fetch = _closes_fetcher({"SPY": 1.02, "TLT": 1.001})  # TLT inside the flat band
    out = score.compute_spytlt_signal("tightening", date(2026, 7, 12), fetch_closes=fetch)
    assert out is not None and out["status"] == "partial"


def test_compute_spytlt_signal_fetch_failure_returns_none(capsys):
    def boom(ticker: str, start: date, end: date) -> dict[date, float]:
        raise ConnectionError("yfinance down")

    assert score.compute_spytlt_signal("tightening", date(2026, 7, 12), fetch_closes=boom) is None
    assert "falling back to unknown" in capsys.readouterr().err


def test_compute_spytlt_signal_thin_history_returns_none():
    def thin(ticker: str, start: date, end: date) -> dict[date, float]:
        return {date(2026, 7, 1): 100.0, date(2026, 7, 2): 101.0}  # < window+1 closes

    assert score.compute_spytlt_signal("easing", date(2026, 7, 12), fetch_closes=thin) is None


def test_build_checklist_threads_spytlt_status_and_defaults_unknown():
    buckets = score.empty_bucket_scores()
    by_id = {i["id"]: i["status"] for i in score.build_checklist(buckets, "confirmed")}
    assert by_id["spytlt_confirms"] == "confirmed"
    by_id_default = {i["id"]: i["status"] for i in score.build_checklist(buckets)}
    assert by_id_default["spytlt_confirms"] == "unknown"  # fetch-failure fallback


# ---------------- event-level clustering (one vote per event) ----------------

def test_same_event_multiple_outlets_votes_once():
    today = date(2026, 6, 23)
    # One CPI print covered by three outlets (one Fed-tier high-importance, two
    # low-importance news) vs one distinct easing event.
    fed = _src("inflation", "tightening", publisher="Federal Reserve",
               url="https://federalreserve.gov/cpi-note", importance="high",
               claim_type="documented_fact", event_key="2026_06_cpi_release")
    news1 = _src("inflation", "tightening", publisher="CNBC", url="https://cnbc.com/cpi",
                 importance="low", claim_type="interpretation",
                 event_key="2026_06_cpi_release")
    news2 = _src("inflation", "tightening", publisher="Reuters", url="https://reuters.com/cpi",
                 importance="low", claim_type="interpretation",
                 event_key="2026_06_cpi_release")
    ease = _src("employment", "easing", publisher="BLS", url="https://bls.gov/jobs",
                claim_type="official_data", event_key="2026_06_jobs_report")
    sources = [fed, news1, news2, ease]

    reps = score.cluster_events(sources, today)
    assert len(reps) == 2  # 3 CPI articles -> 1 event; jobs report -> 1 event
    rep_t = next(r for r in reps if r["direction"] == "tightening")
    assert rep_t["publisher"] == "Federal Reserve"  # max-weight source represents
    assert rep_t["cluster_size"] == 3
    assert next(r for r in reps if r["direction"] == "easing")["cluster_size"] == 1

    # Shares equal the TWO representatives' weights only — no 3x coverage volume.
    w_fed = score.weight_of(fed, today)
    w_ease = score.weight_of(ease, today)
    shares, total = score.direction_shares(sources, today)
    assert total == round(w_fed + w_ease, 3)
    assert shares["tightening"] == round(w_fed / (w_fed + w_ease), 4)
    assert shares["easing"] == round(w_ease / (w_fed + w_ease), 4)


def test_distinct_event_keys_vote_separately():
    today = date(2026, 6, 23)
    a = _src("inflation", "tightening", url="https://a.com/1", event_key="2026_06_cpi_release")
    b = _src("inflation", "tightening", url="https://b.com/2", event_key="2026_06_ppi_release")
    reps = score.cluster_events([a, b], today)
    assert len(reps) == 2
    _, total = score.direction_shares([a, b], today)
    assert total == round(score.weight_of(a, today) + score.weight_of(b, today), 3)


def test_keyless_sources_are_singleton_clusters_and_mix_with_keyed():
    today = date(2026, 6, 23)
    sources = [
        _src("inflation", "tightening", url="https://a.com/1"),  # keyless
        _src("inflation", "tightening", url="https://b.com/2", event_key=""),  # keyless
        _src("inflation", "easing", url="https://c.com/3", event_key="2026_06_x"),
        _src("inflation", "easing", url="https://d.com/4", event_key="2026_06_x"),
    ]
    reps = score.cluster_events(sources, today)
    assert len(reps) == 3  # 2 keyless singletons + 1 keyed pair
    sizes = sorted(r["cluster_size"] for r in reps)
    assert sizes == [1, 1, 2]


def test_event_cluster_key_namespaces_cannot_collide():
    keyed = {"event_key": "abc", "url": "https://x.com/1"}
    keyless = {"url": "https://x.com/1"}
    assert ic.event_cluster_key(keyed).startswith("ev::")
    assert ic.event_cluster_key(keyless).startswith("src::")
    assert ic.event_cluster_key(keyed) != ic.event_cluster_key(keyless)


def test_event_key_sanitizer():
    assert ic.sanitize_event_key("2026-06 CPI Release!") == "2026_06_cpi_release"
    assert ic.sanitize_event_key("  Powell -- Senate  Testimony ") == "powell_senate_testimony"
    assert ic.sanitize_event_key(None) == ""
    assert ic.sanitize_event_key("") == ""
    assert len(ic.sanitize_event_key("x_" * 100)) <= ic.EVENT_KEY_MAX_LEN
    # normalize_source applies the sanitizer
    s = ic.normalize_source(
        {"title": "t", "url": "https://a.com/1", "event_key": "2026-06 CPI Release!"},
        "inflation",
    )
    assert s is not None and s.event_key == "2026_06_cpi_release"
    assert s.to_dict()["event_key"] == "2026_06_cpi_release"
    # missing event_key stays empty
    s2 = ic.normalize_source({"title": "t", "url": "https://a.com/2"}, "inflation")
    assert s2 is not None and s2.event_key == ""


def test_event_key_survives_mark_and_merge():
    cur = [{"url": "https://x.com/a", "title": "CPI hot", "published_at": "2026-06-20",
            "event_key": "2026_06_cpi_release"}]
    merged, _ = ic.mark_and_merge([], cur, since="2026-06-17", now="2026-06-23T00:00:00Z")
    assert merged[0]["event_key"] == "2026_06_cpi_release"


def test_backward_compat_keyless_shares_match_direct_sum():
    """Legacy latest_raw.json has no event_key: every source must be its own cluster,
    so shares are IDENTICAL to the pre-clustering behavior (sum over all sources)."""
    today = date(2026, 6, 23)
    sources = [
        _src("inflation", "tightening", publisher="BLS", url="https://bls.gov/cpi",
             claim_type="official_data"),
        _src("fed_communications", "tightening", publisher="Federal Reserve",
             url="https://federalreserve.gov/speech", claim_type="documented_fact"),
        _src("employment", "easing", url="https://cnbc.com/jobs", importance="low"),
        _src("market_pricing", "neutral", url="https://cme.com/fedwatch",
             confidence="low", published_at="2026-06-10T00:00:00Z"),
    ]
    # Previous behavior: direct weighted sum over every source.
    direct = {"easing": 0.0, "neutral": 0.0, "tightening": 0.0}
    tot = 0.0
    for s in sources:
        wt = score.weight_of(s, today)
        direct[s["direction"]] += wt
        tot += wt
    expected = {k: round(v / tot, 4) for k, v in direct.items()}

    shares, total = score.direction_shares(sources, today)
    assert shares == expected
    assert total == round(tot, 3)

    reps = score.cluster_events(sources, today)
    assert len(reps) == len(sources)  # count preserved
    assert all(r["cluster_size"] == 1 for r in reps)


def test_score_buckets_counts_events_not_sources():
    today = date(2026, 6, 23)
    sources = [
        _src("inflation", "tightening", url="https://a.com/1", event_key="2026_06_cpi_release"),
        _src("inflation", "tightening", url="https://b.com/2", event_key="2026_06_cpi_release"),
        _src("inflation", "tightening", url="https://c.com/3", event_key="2026_06_cpi_release"),
        _src("inflation", "easing", url="https://d.com/4", event_key="2026_06_ppi_release"),
    ]
    inf = score.score_buckets(sources, today)["inflation"]
    assert inf["n"] == 2  # events, not sources
    assert inf["n_sources"] == 4
    # Equal-weight representatives -> 50/50 despite 3:1 coverage volume.
    assert inf["shares"]["tightening"] == inf["shares"]["easing"] == 0.5


# ---------------------------------------------------------------- summary quote integrity


def _summary_fixture():
    """Reproduces the live F2 incident: a neutral max-importance source with a mangled
    attributed quote sits atop a bucket whose dominant direction is tightening."""
    sources = [
        {"bucket": "fed_communications", "direction": "neutral", "importance": "high",
         "published_at": "2026-07-08T14:30:00Z", "publisher": "The Hill",
         "title": "Powell: Fed has 'no risk-free path' as unemployment, inflation rise",
         "evidence_text": "Powell stated, 'There no risk path for as we the tension between "
                          "our employment and inflation goals,' at the NE conference."},
        {"bucket": "fed_communications", "direction": "tightening", "importance": "high",
         "published_at": "2026-06-19T00:00:00Z", "publisher": "Wall Street Journal",
         "title": "Fed Minutes Reveal Support for Rate Hikes if Inflation Proves Sticky",
         "evidence_text": "Minutes showed several officials open to a hike."},
        {"bucket": "inflation", "direction": "tightening", "importance": "high",
         "published_at": "2026-06-25T00:00:00Z", "publisher": "Reuters",
         "title": "May US PCE inflation tops 4%, leaves Fed hike on the table",
         "evidence_text": "Core PCE ran above 4% in May."},
    ]
    bucket_scores = {
        "employment": {"label": "strongly easing", "dominant": "easing"},
        "inflation": {"label": "strongly tightening", "dominant": "tightening"},
        "fed_communications": {"label": "strongly tightening", "dominant": "tightening"},
        "market_pricing": {"label": "strongly tightening", "dominant": "tightening"},
    }
    shares = {"tightening": 0.39, "neutral": 0.45, "easing": 0.16}
    return sources, bucket_scores, shares


def test_contains_attributed_quote():
    assert score.contains_attributed_quote(
        "Powell stated, 'There no risk path for as we the tension'")
    assert score.contains_attributed_quote('Warsh said: "talk less, say more"')
    assert score.contains_attributed_quote("as officials noted, “inflation is sticky”")
    # Headlines and paraphrases pass: no speech verb followed by a quote span.
    assert not score.contains_attributed_quote(
        "Powell: Fed has 'no risk-free path' as unemployment, inflation rise")
    assert not score.contains_attributed_quote(
        "Powell said the Fed faces no risk-free path on the dual mandate.")
    assert not score.contains_attributed_quote("")


def test_top_source_prefers_matching_direction():
    sources, _, _ = _summary_fixture()
    # Without a direction the neutral Hill source wins (importance+recency)...
    assert score.top_source(sources, "fed_communications")["publisher"] == "The Hill"
    # ...but the summary exemplar for a tightening bucket must vote tightening.
    got = score.top_source(sources, "fed_communications", direction="tightening")
    assert got["publisher"] == "Wall Street Journal"
    # Unmatched direction falls back to the top source rather than dropping the bucket.
    assert score.top_source(sources, "inflation", direction="easing")["publisher"] == "Reuters"


def test_build_summary_never_quotes_evidence_text():
    sources, bucket_scores, shares = _summary_fixture()
    summary, _ = score.build_summary("Potential pivot → tightening", shares, bucket_scores, sources)
    # The mangled attributed quote must not reach the public summary in any form.
    assert "There no risk path" not in summary
    assert "NE conference" not in summary
    assert not score.contains_attributed_quote(summary)
    # Exemplars are direction-matched headline citations with publisher attribution.
    assert "per Wall Street Journal: Fed Minutes Reveal Support for Rate Hikes" in summary
    assert "per Reuters: May US PCE inflation tops 4%" in summary


def test_exemplar_refuses_titles_with_attributed_quotes():
    sources, bucket_scores, _ = _summary_fixture()
    sources[1]["title"] = "Fed officials said, 'hikes are coming' — minutes"
    ex = score._exemplar(bucket_scores, sources, "fed_communications")
    assert ex is None  # guard refuses rather than emitting an attributed quote
