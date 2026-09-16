"""fomc-intel tool modules. Each module exposes plain functions (importable in tests)
plus a register(mcp) hook that attaches them to the FastMCP server. Phase B action
tools (refresh/ingest/search/diff) get their own modules here, same pattern.
"""

NO_ADVICE = "Historical/observational evidence only — not investment advice."


def error_dict(exc: Exception) -> dict[str, str]:
    """House rule: tools never raise — every failure becomes {"error": ...}."""
    return {"error": f"{type(exc).__name__}: {exc}"}
