"""Regime-read tools: headline read, two-axis state, balance-sheet axis,
market-pricing axis."""

from __future__ import annotations

from typing import Any

from fomc_server._data import (
    load_balance_sheet,
    load_latest,
    load_market_pricing,
    load_truth,
    truth_events,
)
from fomc_server.tools import error_dict

# Balance-sheet lean must oppose the stated regime by at least this much to call
# the setup bifurcated (mirrors the dashboard's RegimeQuadrant divergence banner).
DIVERGENCE_THRESHOLD = 0.25


def _stated_as_of() -> str | None:
    """Meeting date the stated regime is as-of = last event in the truth table."""
    doc, _ = load_truth()
    events = truth_events(doc)
    return events[-1].get("date") if events else None


def get_regime_read() -> dict[str, Any]:
    """Headline regime read from the latest intel run: the four-state descriptor
    (e.g. 'Potential pivot → tightening'), conviction, weighted evidence shares,
    net lean, the Fed's stated regime (statement-parsed) with its as-of meeting
    date, what changed this run, and a one-paragraph summary.
    Historical/observational evidence only — not investment advice."""
    try:
        doc, prov = load_latest()
        try:
            stated_as_of = _stated_as_of()
        except Exception:
            stated_as_of = None
        return {
            "descriptor": doc.get("inferred_regime"),
            "conviction": doc.get("conviction"),
            "evidence_shares": doc.get("evidence_shares"),
            "net_lean": doc.get("net_lean"),
            "evidence_dir": doc.get("evidence_dir"),
            "stated_regime": doc.get("current_repo_regime"),
            "stated_regime_as_of": stated_as_of,
            "next_fomc_meeting": doc.get("next_fomc_meeting"),
            "new_this_run": doc.get("new_this_run"),
            "n_sources": doc.get("n_sources"),
            "summary": doc.get("summary"),
            "stale": doc.get("stale"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def _quadrant(news_lean: float, bs_lean: float, divergence: bool) -> str:
    if divergence:
        return "bifurcated"
    if news_lean >= 0:
        return "full tightening" if bs_lean > 0 else "rate-led tightening"
    return "bifurcated" if bs_lean > 0 else "full easing"


def get_two_axis_state() -> dict[str, Any]:
    """Two-axis regime map: the policy/news lean (weighted vote-share) on one axis
    and the deterministic balance-sheet/liquidity lean (FRED) on the other, with the
    quadrant name (rate-led tightening / full tightening / full easing / bifurcated)
    and a divergence flag — bifurcated means the Fed's stated rate stance and the
    balance-sheet lean are pulling in opposite directions.
    Historical/observational evidence only — not investment advice."""
    try:
        doc, prov_news = load_latest()
        bs, prov_bs = load_balance_sheet()
        news_lean = float(doc.get("net_lean") or 0.0)
        stated = str(doc.get("current_repo_regime") or "")
        bs_available = bool(bs.get("available"))
        bs_lean = float(bs.get("net_lean") or 0.0) if bs_available else 0.0
        divergence = bs_available and (
            (stated.lower() == "easing" and bs_lean >= DIVERGENCE_THRESHOLD)
            or (stated.lower() == "tightening" and bs_lean <= -DIVERGENCE_THRESHOLD)
        )
        if divergence:
            why = (
                f"The Fed's stated regime is {stated}, but the balance-sheet/liquidity "
                f"lean is {bs_lean:+.2f} ({bs.get('label')}) — rate path and "
                "financial-conditions stance are pulling in opposite directions."
            )
        elif not bs_available:
            why = "Balance-sheet axis unavailable; no divergence call possible this run."
        else:
            why = (
                f"Stated regime {stated} and balance-sheet lean {bs_lean:+.2f} "
                f"({bs.get('label')}) do not conflict beyond the "
                f"±{DIVERGENCE_THRESHOLD} threshold."
            )
        return {
            "news_axis": {
                "net_lean": news_lean,
                "label": doc.get("inferred_regime"),
                "conviction": doc.get("conviction"),
            },
            "balance_sheet_axis": {
                "available": bs_available,
                "net_lean": bs.get("net_lean") if bs_available else None,
                "label": bs.get("label") if bs_available else None,
            },
            "stated_regime": stated,
            "quadrant": _quadrant(news_lean, bs_lean, bool(divergence)),
            "divergence": bool(divergence),
            "why": why,
            "provenance": {"news_axis": prov_news, "balance_sheet_axis": prov_bs},
        }
    except Exception as exc:
        return error_dict(exc)


def get_balance_sheet_axis() -> dict[str, Any]:
    """The deterministic balance-sheet / liquidity axis: per-indicator FRED signals
    (balance sheet size, bank reserves, RRP cushion, 10y yield, repo stress), the
    weighted net lean, and its label. No LLM on this axis.
    Historical/observational evidence only — not investment advice."""
    try:
        bs, prov = load_balance_sheet()
        if not bs.get("available"):
            return {
                "available": False,
                "note": (
                    "Balance-sheet axis not available in the latest run (FRED collection "
                    "did not produce indicators). It populates on the next scheduled "
                    "data run."
                ),
                "provenance": prov,
            }
        return {
            "available": True,
            "net_lean": bs.get("net_lean"),
            "label": bs.get("label"),
            "indicators": bs.get("indicators"),
            "method": bs.get("method"),
            "upstream_source": bs.get("source"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def get_market_pricing_axis() -> dict[str, Any]:
    """The deterministic market-pricing axis: what the MARKET prices for Fed policy,
    from FRED primary series (2y yield momentum, 10y-2y curve slope, 2y-vs-funds-rate
    gap, net liquidity = WALCL - TGA - RRP), the weighted net lean, and its label.
    A hard-data cross-check on both the news lean and the balance-sheet axis — the
    market can disagree with both. No LLM on this axis.
    Historical/observational evidence only — not investment advice."""
    try:
        try:
            doc, prov = load_market_pricing()
        except FileNotFoundError:
            # The axis JSON simply hasn't been produced yet — report a clean pending
            # state (parallel to an {available:false} doc), not an error.
            return {
                "available": False,
                "note": (
                    "Market-pricing axis not produced yet. It populates on the next "
                    "scheduled data run (scripts/collect_market_pricing.py, needs "
                    "FRED_API_KEY)."
                ),
            }
        if not doc.get("available"):
            return {
                "available": False,
                "note": (
                    "Market-pricing axis not available in the latest run (FRED "
                    "collection did not produce indicators). It populates on the next "
                    "scheduled data run."
                ),
                "provenance": prov,
            }
        return {
            "available": True,
            "net_lean": doc.get("net_lean"),
            "label": doc.get("label"),
            "indicators": doc.get("indicators"),
            "method": doc.get("method"),
            "upstream_source": doc.get("source"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_regime_read)
    mcp.tool()(get_two_axis_state)
    mcp.tool()(get_balance_sheet_axis)
    mcp.tool()(get_market_pricing_axis)
