#!/usr/bin/env python3
"""fomc-intel — local MCP server over the fomc-research FOMC regime data.

Phase A: 11 READ-ONLY tools (guide, regime read, two-axis state, balance sheet,
playbook, event history, news evidence, daily log, checklist, stated regime,
calendar). Phase B: 4 more — corpus search + statement redline (read-only) and the
live pipeline tools refresh_intel / ingest_meeting (subprocess runners, optional
git publish of the dashboard data).

Run (stdio, zero-config default):
    uv run --project packages/fomc-server fomc-intel
Run (streamable HTTP):
    uv run --project packages/fomc-server fomc-intel --transport http --port 8848
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP

from fomc_server.tools import corpus, events, guide, news, pipeline, playbook, regime, stated

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8848

mcp = FastMCP("fomc-intel")

guide.register(mcp)
regime.register(mcp)
playbook.register(mcp)
events.register(mcp)
news.register(mcp)
stated.register(mcp)
corpus.register(mcp)
pipeline.register(mcp)


def main(argv: list[str] | None = None) -> None:
    """Entry point for the `fomc-intel` console script."""
    parser = argparse.ArgumentParser(
        prog="fomc-intel",
        description=(
            "Read-only MCP server over the FOMC regime dashboard data "
            "(stdio by default; --transport http for streamable HTTP)."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="stdio (default, for Claude Desktop/Code) or http (streamable HTTP)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"HTTP host (default {DEFAULT_HOST})")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"HTTP port (default {DEFAULT_PORT})"
    )
    args = parser.parse_args(argv)

    if args.transport == "http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
