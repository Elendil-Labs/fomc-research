"""get_fomc_guide — static methodology orientation for the fomc-intel server."""

from __future__ import annotations

from typing import Any

from fomc_server.tools import error_dict

_GUIDE: dict[str, Any] = {
    "server": "fomc-intel",
    "purpose": (
        "Read-only tools over the fomc-research FOMC regime dashboard: what regime the "
        "Fed has STATED (parsed from its own statements), what the weighted news/data "
        "evidence and the balance sheet currently LEAN, and what historically happened to "
        "SPY/TLT around FOMC decisions under comparable conditions."
    ),
    "two_axis_model": {
        "news_axis": {
            "what": (
                "Weighted vote-share over source direction (easing/neutral/tightening). "
                "No magnitude averaging — each event cluster casts ONE vote (one vote per "
                "event_key; the representative is the max-weight source; keyless sources "
                "are singleton clusters)."
            ),
            "weight": (
                "source-tier x claim-type x importance x confidence x recency-decay"
            ),
            "source_tier_weights": {"fed": 2.0, "official": 1.5, "news": 1.0},
            "claim_type_weights": {
                "documented_fact": 1.0,
                "official_data": 1.0,
                "sell_side_scenario": 0.6,
                "interpretation": 0.4,
            },
            "recency_decay": (
                "0-7d: 1.0, 8-14d: 0.75, 15-30d: 0.5, >30d: 0.25 — with a 0.5 floor for "
                "Fed/official sources so primary sources never decay to noise."
            ),
            "output": "net_lean in [-1, +1] (negative = easing, positive = tightening).",
        },
        "balance_sheet_axis": {
            "what": (
                "Deterministic -1/0/+1 signals from FRED primary series (WALCL, WRESBAL, "
                "RRP cushion, DGS10, SOFR-IORB), weighted into a net lean. No LLM anywhere "
                "on this axis."
            ),
            "why": (
                "Catches the divergence case: the Fed easing on the rate while liquidity/"
                "collateral tightens via the balance sheet (or vice versa)."
            ),
        },
        "market_pricing_axis": {
            "what": (
                "Deterministic -1/0/+1 signals from FRED primary series on what the "
                "MARKET prices for Fed policy (2y yield 90d momentum, 10y-2y curve "
                "slope, 2y-vs-funds-rate gap, net liquidity = WALCL - TGA - RRP), "
                "weighted into a net lean. No LLM anywhere on this axis. A separate "
                "hard-data cross-check — NOT part of the two-axis quadrant."
            ),
            "why": (
                "The market can disagree with both the news lean and the balance "
                "sheet; this axis makes that disagreement visible instead of implied."
            ),
        },
        "descriptor": (
            "Four-state read anchored to the statement-derived regime: 'Easing' / "
            "'Tightening' when the evidence confirms the stated regime, and 'Potential "
            "pivot → tightening' / 'Potential pivot → easing' when the weighted evidence "
            "leans against it."
        ),
    },
    "stated_regime": (
        "Parsed from FOMC statements only — the actual rate action (Hike/Cut) sets the "
        "regime; Holds inherit the prior regime. No interpretation, no news."
    ),
    "divergence_bifurcation": (
        "'Bifurcated' = the Fed's stated rate stance and the balance-sheet/liquidity lean "
        "disagree materially (stated Easing with balance-sheet lean >= +0.25, or stated "
        "Tightening with lean <= -0.25). Rate path and financial-conditions stance pulling "
        "in opposite directions."
    ),
    "tools": {
        "get_fomc_guide": "This orientation. Call first each session.",
        "get_regime_read": "Headline read: descriptor, conviction, shares, stated regime.",
        "get_two_axis_state": "Both axes + quadrant name + divergence flag.",
        "get_balance_sheet_axis": "The deterministic FRED indicators behind the second axis.",
        "get_market_pricing_axis": (
            "The deterministic FRED market-pricing axis: what the market prices for "
            "the Fed path (2y momentum, curve slope, 2y-vs-funds, net liquidity)."
        ),
        "get_playbook": (
            "Next meeting, blackout window, and conditional SPY/TLT stats for FOMC events "
            "under the current stated regime (optional Hike/Hold/Cut filter)."
        ),
        "get_event_history": "Filtered per-event truth table (regime/action/chair/color/date).",
        "get_news_evidence": "The scored sources behind the news axis, filterable.",
        "get_daily_log": "Daily net_lean / inferred-regime history points.",
        "get_checklist": "What-would-change-the-call checklist with statuses.",
        "get_stated_regime": "Statement-parsed regime on any date + parser audit/ALARM.",
        "get_fomc_calendar": "2026 decision dates, blackout windows, truth-data coverage.",
        "search_fed_corpus": (
            "Regex/substring search across the Fed primary-source corpus (statements, "
            "minutes, speeches, testimony, Warsh), newest first, with «»-marked snippets."
        ),
        "diff_statements": (
            "Fed-watcher redline of two FOMC statements (default: newest vs previous): "
            "added/removed sentences, changed pairs, unified diff."
        ),
        "refresh_intel": (
            "LIVE: run the news collect→score pipeline + FRED balance-sheet step now; "
            "reports before/after regime read and the delta. publish=True pushes the "
            "dashboard data."
        ),
        "ingest_meeting": (
            "LIVE meeting-day ingest: fetch the new statement, rebuild the SPY/TLT "
            "truth table, re-export dashboard JSON, optionally re-run the news pipeline; "
            "surfaces the statement-parser STALE ALARM instead of failing."
        ),
    },
    "framing": (
        "Nothing here is a forecast or a recommendation. Conditional stats are small-n "
        "base rates; the news axis is an evidence tally, not a prediction."
    ),
}


def get_fomc_guide() -> dict[str, Any]:
    """Methodology orientation for the fomc-intel server: the two-axis regime model
    (news vote-share axis + deterministic balance-sheet axis), what the stated regime
    means, the divergence/bifurcation concept, and which tool to use when.
    Historical/observational evidence only — not investment advice."""
    try:
        return dict(_GUIDE)
    except Exception as exc:  # pragma: no cover — static dict
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_fomc_guide)
