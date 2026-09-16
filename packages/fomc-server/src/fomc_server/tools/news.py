"""News-axis tools: scored evidence feed, daily log, what-would-change checklist."""

from __future__ import annotations

from typing import Any

from fomc_server._data import load_history, load_latest
from fomc_server.tools import error_dict

_VALID_BUCKETS = ("employment", "inflation", "fed_communications", "market_pricing", "other")
_VALID_DIRECTIONS = ("easing", "neutral", "tightening")
_VALID_CLAIM_TYPES = ("documented_fact", "official_data", "sell_side_scenario", "interpretation")

# Source-tier heuristics ported from the lab's scripts/_intel_common.py (source_tier).
_TIER_FED_HINTS = ("federalreserve.gov", "fomc", "federal reserve", "kevin warsh", "jerome powell")
_TIER_OFFICIAL_HINTS = (
    "bureau of labor", "bls", "bureau of economic", "bea", "treasury", "fred",
    "st. louis fed", "stlouisfed", "cme", "fedwatch", "department of labor", "dol",
)

CHECKLIST_HONESTY_NOTE = (
    "Honesty note: checklist statuses are derived mechanically from the bucket leans in "
    "the same intel run — they are a restatement of the evidence, not independent "
    "confirmation. The exception is 'spytlt_confirms', which is computed at refresh time "
    "from the trailing N-day SPY/TLT price trend (evidence in the run's top-level "
    "'spytlt' block) — a trend heuristic, not an event study — and falls back to "
    "'unknown' when prices are unavailable."
)


def _source_tier(publisher: str, url: str) -> str:
    hay = f"{publisher} {url}".lower()
    if any(h in hay for h in _TIER_FED_HINTS):
        return "fed"
    if any(h in hay for h in _TIER_OFFICIAL_HINTS):
        return "official"
    return "news"


def get_news_evidence(
    bucket: str | None = None,
    direction: str | None = None,
    claim_type: str | None = None,
    new_only: bool = False,
    limit: int = 25,
) -> dict[str, Any]:
    """The scored sources behind the news vote-share axis, newest first, filterable by
    bucket (employment/inflation/fed_communications/market_pricing/other), direction
    (easing/neutral/tightening), claim type (documented_fact/official_data/
    sell_side_scenario/interpretation), or only sources new this run. Each item carries
    its URL, source tier (fed/official/news), claim type, and event-cluster key.
    Historical/observational evidence only — not investment advice."""
    try:
        if bucket is not None and bucket not in _VALID_BUCKETS:
            return {"error": f"invalid bucket {bucket!r}; expected one of {_VALID_BUCKETS}"}
        if direction is not None and direction not in _VALID_DIRECTIONS:
            return {
                "error": f"invalid direction {direction!r}; expected one of {_VALID_DIRECTIONS}"
            }
        if claim_type is not None and claim_type not in _VALID_CLAIM_TYPES:
            return {
                "error": f"invalid claim_type {claim_type!r}; "
                f"expected one of {_VALID_CLAIM_TYPES}"
            }
        doc, prov = load_latest()
        sources = doc.get("sources") or []
        matched: list[dict[str, Any]] = []
        for s in sources:
            if bucket is not None and s.get("bucket") != bucket:
                continue
            if direction is not None and s.get("direction") != direction:
                continue
            if claim_type is not None and s.get("claim_type") != claim_type:
                continue
            if new_only and not s.get("is_new"):
                continue
            matched.append(
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "publisher": s.get("publisher"),
                    "url": s.get("url"),
                    "published_at": s.get("published_at"),
                    "bucket": s.get("bucket"),
                    "direction": s.get("direction"),
                    "tier": _source_tier(str(s.get("publisher") or ""), str(s.get("url") or "")),
                    "claim_type": s.get("claim_type"),
                    "importance": s.get("importance"),
                    "confidence": s.get("confidence"),
                    "official": s.get("official"),
                    "is_new": s.get("is_new"),
                    "event_key": s.get("event_key"),
                    "evidence_text": s.get("evidence_text"),
                    "why_it_matters": s.get("why_it_matters"),
                }
            )
        matched.sort(key=lambda s: str(s.get("published_at") or ""), reverse=True)
        truncated = len(matched) > max(limit, 0)
        return {
            "n_matched": len(matched),
            "truncated": truncated,
            "sources": matched[: max(limit, 0)],
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def get_daily_log(limit: int = 30) -> dict[str, Any]:
    """Daily intel-run log, newest first: net lean, inferred regime descriptor,
    conviction, and how many sources were new each run day.
    Historical/observational evidence only — not investment advice."""
    try:
        doc, prov = load_history()
        points = list(doc.get("points") or [])
        points.sort(key=lambda p: str(p.get("date") or ""), reverse=True)
        truncated = len(points) > max(limit, 0)
        return {
            "n_total": len(points),
            "truncated": truncated,
            "points": points[: max(limit, 0)],
            "description": doc.get("description"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def get_checklist() -> dict[str, Any]:
    """The 'what would change the call' checklist from the latest intel run, with
    per-item statuses (confirmed/partial/not_confirmed/unknown) and an honesty note
    about how those statuses are derived.
    Historical/observational evidence only — not investment advice."""
    try:
        doc, prov = load_latest()
        return {
            "inferred_regime": doc.get("inferred_regime"),
            "checklist": doc.get("checklist"),
            "what_would_change_the_call": doc.get("what_would_change_the_call"),
            "honesty_note": CHECKLIST_HONESTY_NOTE,
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_news_evidence)
    mcp.tool()(get_daily_log)
    mcp.tool()(get_checklist)
