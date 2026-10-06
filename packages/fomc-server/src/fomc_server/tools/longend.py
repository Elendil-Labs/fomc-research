"""Long-end tools: the "has the long end bottomed" scorecard (FRED valuation +
timing indicators), the Treasury auction monitor, CFTC Treasury-futures
positioning, and the composite watch that merges all three into one checklist."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fomc_server._data import Doc, load_auctions, load_cftc, load_long_end
from fomc_server._provenance import _parse_iso
from fomc_server.tools import error_dict

# A long-end auction counts as "recent stress" for the composite watch when it
# printed within this many days of the auction-monitor snapshot.
AUCTION_STRESS_WINDOW_DAYS = 30

# The 10y contract anchors the real-money detail line in the composite watch.
BENCHMARK_CONTRACT = "UST_10Y"

LONG_END_FILES = ("long_end_axis", "auction_monitor", "cftc_positioning")


def _pending(name: str, script: str) -> dict[str, Any]:
    return {
        "available": False,
        "note": (
            f"{name} not produced yet. It populates on the next scheduled data run "
            f"({script})."
        ),
    }


# --------------------------------------------------------------------------- axis


def get_long_end_axis() -> dict[str, Any]:
    """The deterministic long-end scorecard: FRED primary-series indicators split
    into VALUATION boxes (10y real yield, ACM term premium, breakevens, MOVE) and
    TIMING boxes (2y yield stall, 10y/30y level, 10y-2y and 5s30s slope, mortgage
    rate), each with its threshold rule and checked/unchecked state, the summary
    counts, and the 2022-10 / 2023-10 cycle-high analog readings for comparison.
    Historical/observational evidence only — not investment advice."""
    try:
        try:
            doc, prov = load_long_end()
        except FileNotFoundError:
            return _pending("Long-end axis", "scripts/collect_long_end.py, needs FRED_API_KEY")
        if not doc.get("available"):
            return {
                "available": False,
                "note": (
                    "Long-end axis not available in the latest run (FRED collection did "
                    "not produce indicators). It populates on the next scheduled data run."
                ),
                "provenance": prov,
            }
        return {
            "available": True,
            "summary": doc.get("summary"),
            "analogs": doc.get("analogs"),
            "indicators": doc.get("indicators"),
            "method": doc.get("method"),
            "upstream_source": doc.get("source"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


# ----------------------------------------------------------------------- auctions


def _norm_term(term: Any) -> str:
    """'10-Year' / '10Y' / '10 yr' / '10-year' all collapse to '10y'."""
    s = str(term or "").strip().lower().replace("-", "").replace(" ", "")
    for suffix in ("years", "year", "yrs", "yr"):
        if s.endswith(suffix):
            s = s[: -len(suffix)] + "y"
            break
    return s


def get_auction_monitor(terms: list[str] | None = None, limit: int = 12) -> dict[str, Any]:
    """Treasury coupon auction results, newest first: per auction the high yield,
    bid-to-cover and indirect/dealer takedown vs their 12-month averages, the tail
    (when a when-issued reference exists), the stress flags, and a status
    (stress / watch / ok). Optional `terms` filter (e.g. ["10-Year", "30-Year"];
    spelling-tolerant, default all terms), `limit` keeps the newest N. Also returns
    the upcoming auction calendar and the stress summary (last long-end stress,
    90-day stress/watch counts, next long-end auction).
    Historical/observational evidence only — not investment advice."""
    try:
        if limit < 1:
            return {"error": f"limit must be >= 1, got {limit}"}
        doc, prov = load_auctions()
        if not doc.get("available"):
            return {
                "available": False,
                "note": (
                    "Auction monitor not available in the latest run (TreasuryDirect "
                    "collection did not produce results). It populates on the next "
                    "scheduled data run."
                ),
                "provenance": prov,
            }
        auctions = [a for a in (doc.get("auctions") or []) if isinstance(a, dict)]
        available_terms = sorted({str(a.get("term")) for a in auctions if a.get("term")})
        wanted = {_norm_term(t) for t in terms} if terms else None
        if wanted is not None:
            unknown = sorted(wanted - {_norm_term(t) for t in available_terms})
            if unknown and len(unknown) == len(wanted):
                return {
                    "error": (
                        f"no auctions match terms {sorted(wanted)}; "
                        f"available terms: {available_terms}"
                    )
                }
            auctions = [a for a in auctions if _norm_term(a.get("term")) in wanted]
        auctions.sort(key=lambda a: str(a.get("auction_date") or ""), reverse=True)
        total = len(auctions)
        auctions = auctions[:limit]
        return {
            "available": True,
            "terms": terms if terms else available_terms,
            "n_auctions": len(auctions),
            "n_matching": total,
            "auctions": auctions,
            "upcoming": doc.get("upcoming"),
            "summary": doc.get("summary"),
            "note_on_tail": doc.get("note_on_tail"),
            "method": doc.get("method"),
            "upstream_source": doc.get("source"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


# --------------------------------------------------------------------------- cftc


def _strip_history(contract: Doc) -> Doc:
    return {k: v for k, v in contract.items() if k != "history"}


def get_cftc_positioning(
    contract: str | None = None, include_history: bool = False
) -> dict[str, Any]:
    """CFTC Treasury-futures positioning (Traders in Financial Futures): per
    contract (UST_10Y, ULTRA_10Y, UST_BOND, ULTRA_BOND) the asset-manager,
    leveraged-fund and dealer net positions with 1-week and 4-week changes, the
    asset-manager selling streak and whether it has stopped, and whether
    leveraged-fund net is at a 26-week low; plus the summary flags (real-money
    distribution, spec capitulation). Optional `contract` filter by id;
    `include_history=True` adds the 12-week am_net/lf_net series per contract.
    Historical/observational evidence only — not investment advice."""
    try:
        doc, prov = load_cftc()
        if not doc.get("available"):
            return {
                "available": False,
                "note": (
                    "CFTC positioning not available in the latest run (COT collection "
                    "did not produce contracts). It populates on the next scheduled "
                    "data run."
                ),
                "provenance": prov,
            }
        contracts = [c for c in (doc.get("contracts") or []) if isinstance(c, dict)]
        ids = [str(c.get("id")) for c in contracts]
        if contract is not None:
            want = contract.strip().upper()
            contracts = [c for c in contracts if str(c.get("id", "")).upper() == want]
            if not contracts:
                return {"error": f"unknown contract {contract!r}; available: {ids}"}
        if not include_history:
            contracts = [_strip_history(c) for c in contracts]
        return {
            "available": True,
            "contracts": contracts,
            "contract_ids": ids,
            "include_history": bool(include_history),
            "summary": doc.get("summary"),
            "method": doc.get("method"),
            "upstream_source": doc.get("source"),
            "provenance": prov,
        }
    except Exception as exc:
        return error_dict(exc)


# -------------------------------------------------------------------------- watch


Loaded = tuple[Doc | None, dict[str, Any] | None, str | None]


def _load_or_missing(name: str, loader: Any) -> Loaded:
    """(doc, provenance, missing_reason). A missing/unparseable file or an
    {available:false} doc both count as missing — the composite never raises."""
    try:
        doc, prov = loader()
    except Exception as exc:
        return None, None, f"{name}: {type(exc).__name__}: {exc}"
    if not doc.get("available"):
        return None, prov, f"{name}: available=false"
    return doc, prov, None


def _to_date(value: Any) -> date | None:
    dt = _parse_iso(str(value)) if value else None
    if dt is not None:
        return dt.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _stress_ref(summary: Doc, auctions: list[Doc]) -> tuple[str | None, str | None]:
    """(auction_date, term) of the last long-end stress auction, from the summary
    (string date or {term, auction_date} object), term resolved from the list."""
    ref = summary.get("last_long_end_stress")
    if not ref:
        return None, None
    if isinstance(ref, dict):
        return (
            str(ref.get("auction_date") or "") or None,
            str(ref.get("term") or "") or None,
        )
    ref_date = str(ref)
    for a in auctions:
        if str(a.get("auction_date")) == ref_date and a.get("status") == "stress":
            return ref_date, str(a.get("term") or "") or None
    for a in auctions:
        if str(a.get("auction_date")) == ref_date:
            return ref_date, str(a.get("term") or "") or None
    return ref_date, None


def _auction_box(doc: Doc | None) -> Doc:
    box: Doc = {
        "id": "AUCTION_STRESS",
        "name": "Recent long-end auction stress",
        "group": "timing",
        "checked": None,
        "detail": "auction_monitor unavailable",
    }
    if doc is None:
        return box
    summary = doc.get("summary") or {}
    auctions = [a for a in (doc.get("auctions") or []) if isinstance(a, dict)]
    ref_date, term = _stress_ref(summary, auctions)
    if ref_date is None:
        box["checked"] = False
        box["detail"] = "no long-end auction stress on record"
        return box
    stress_day = _to_date(ref_date)
    snapshot = _to_date(doc.get("generated_at")) or datetime.now(timezone.utc).date()
    if stress_day is None:
        box["detail"] = f"last long-end stress {ref_date!r} is not a parseable date"
        return box
    age = (snapshot - stress_day).days
    recent = 0 <= age <= AUCTION_STRESS_WINDOW_DAYS
    box["checked"] = recent
    label = f"{term} auction" if term else "long-end auction"
    box["detail"] = (
        f"last long-end stress: {label} on {ref_date} ({age}d before snapshot; "
        f"window {AUCTION_STRESS_WINDOW_DAYS}d) — "
        + ("recent, box checked" if recent else "older than window, box unchecked")
    )
    return box


def _contract_by_id(doc: Doc, cid: str) -> Doc | None:
    for c in doc.get("contracts") or []:
        if isinstance(c, dict) and str(c.get("id", "")).upper() == cid:
            return c
    return None


def _fmt_signed(value: Any) -> str:
    try:
        return f"{int(round(float(value))):+,}"
    except (TypeError, ValueError):
        return "n/a"


def _cftc_boxes(doc: Doc | None) -> list[Doc]:
    rm: Doc = {
        "id": "REAL_MONEY_SELLING",
        "name": "Asset managers have stopped selling",
        "group": "timing",
        "checked": None,
        "detail": "cftc_positioning unavailable",
    }
    spec: Doc = {
        "id": "SPEC_CAPITULATION",
        "name": "Leveraged-fund capitulation",
        "group": "timing",
        "checked": None,
        "detail": "cftc_positioning unavailable",
    }
    if doc is None:
        return [rm, spec]
    summary = doc.get("summary") or {}
    contracts = [c for c in (doc.get("contracts") or []) if isinstance(c, dict)]
    n_contracts = len(contracts)
    bench = _contract_by_id(doc, BENCHMARK_CONTRACT)
    bench_delta = _fmt_signed(bench.get("am_net_change_4w")) if bench else "n/a"

    distribution = summary.get("real_money_distribution")
    if distribution is None:
        rm["detail"] = "summary.real_money_distribution missing"
    else:
        rm["checked"] = not bool(distribution)
        stopped = summary.get("am_stopped_selling_count")
        rm["detail"] = (
            f"asset managers stopped selling on {stopped}/{n_contracts} contracts; "
            f"{BENCHMARK_CONTRACT} asset-manager net Δ4w {bench_delta} contracts; "
            + (
                "real-money distribution still running"
                if distribution
                else "no real-money distribution flag"
            )
        )

    capitulation = summary.get("spec_capitulation")
    if capitulation is None:
        spec["detail"] = "summary.spec_capitulation missing"
    else:
        spec["checked"] = bool(capitulation)
        lows = [str(c.get("id")) for c in contracts if c.get("lf_net_26w_low")]
        lf_delta = _fmt_signed(bench.get("lf_net_change_4w")) if bench else "n/a"
        spec["detail"] = (
            f"leveraged-fund net at 26-week low on {len(lows)}/{n_contracts} contracts"
            + (f" ({', '.join(lows)})" if lows else "")
            + f"; {BENCHMARK_CONTRACT} leveraged-fund net Δ4w {lf_delta} contracts"
        )
    return [rm, spec]


def _axis_boxes(doc: Doc | None) -> list[Doc]:
    if doc is None:
        return []
    boxes: list[Doc] = []
    for ind in doc.get("indicators") or []:
        if not isinstance(ind, dict) or ind.get("group") not in ("valuation", "timing"):
            continue
        checked = ind.get("checked")
        boxes.append(
            {
                "id": ind.get("id"),
                "name": ind.get("name"),
                "group": ind.get("group"),
                "checked": bool(checked) if checked is not None else None,
                "detail": ind.get("detail"),
            }
        )
    return boxes


def _max_generated_at(docs: list[Doc | None]) -> str | None:
    best: tuple[datetime, str] | None = None
    for doc in docs:
        if not doc:
            continue
        raw = doc.get("generated_at")
        dt = _parse_iso(raw)
        if dt is None:
            continue
        if best is None or dt > best[0]:
            best = (dt, str(raw))
    return best[1] if best else None


def get_long_end_watch() -> dict[str, Any]:
    """The composite "has the long end bottomed" scorecard: one checklist merging
    the long-end axis VALUATION and TIMING boxes (real yield, term premium,
    breakevens, MOVE, 2y stall, 10y/30y, curve slopes, mortgage rate) with three
    flow boxes — AUCTION_STRESS (a long-end auction tailed/stressed within the
    last 30 days), REAL_MONEY_SELLING (asset managers have STOPPED net selling
    Treasury futures) and SPEC_CAPITULATION (leveraged-fund net at a 26-week low).
    Returns the boxes, checked/total counts by group, a one-sentence read, which
    source files were unavailable, and per-file provenance. Degrades box by box:
    a missing file leaves its boxes unknown rather than failing the call.
    Historical/observational evidence only — not investment advice."""
    try:
        axis, prov_axis, miss_axis = _load_or_missing("long_end_axis", load_long_end)
        auct, prov_auct, miss_auct = _load_or_missing("auction_monitor", load_auctions)
        cftc, prov_cftc, miss_cftc = _load_or_missing("cftc_positioning", load_cftc)

        boxes = _axis_boxes(axis) + [_auction_box(auct)] + _cftc_boxes(cftc)
        scored = [b for b in boxes if b["checked"] is not None]
        checked = sum(1 for b in scored if b["checked"])
        val = [b for b in scored if b["group"] == "valuation"]
        tim = [b for b in scored if b["group"] == "timing"]
        val_checked = sum(1 for b in val if b["checked"])
        tim_checked = sum(1 for b in tim if b["checked"])
        unknown = len(boxes) - len(scored)
        missing = [m for m in (miss_axis, miss_auct, miss_cftc) if m]

        read = (
            f"{checked} of {len(scored)} boxes checked; valuation boxes "
            f"{val_checked}/{len(val)}, timing boxes {tim_checked}/{len(tim)}"
        )
        if unknown:
            read += f"; {unknown} unknown"
        if missing:
            read += f"; missing: {', '.join(m.split(':')[0] for m in missing)}"
        read += "."

        return {
            "as_of": _max_generated_at([axis, auct, cftc]),
            "boxes": boxes,
            "checked": checked,
            "total": len(scored),
            "unknown": unknown,
            "valuation_checked": val_checked,
            "valuation_total": len(val),
            "timing_checked": tim_checked,
            "timing_total": len(tim),
            "read": read,
            "missing": missing,
            "provenance": {
                "long_end_axis": prov_axis,
                "auction_monitor": prov_auct,
                "cftc_positioning": prov_cftc,
            },
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(get_long_end_axis)
    mcp.tool()(get_auction_monitor)
    mcp.tool()(get_cftc_positioning)
    mcp.tool()(get_long_end_watch)
