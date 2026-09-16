# fomc-research

An open FOMC research database and the tooling that builds it. The database holds
the Federal Reserve's own words (statements, minutes, projections, transcripts,
speeches, testimony, 2018 to present), a regime flag parsed from those statements,
a per-meeting table of how SPY and TLT reacted around every decision, and a daily,
scored feed of intermeeting evidence (news, FRED balance-sheet data, market pricing).
Agents such as Claude Code, Codex and others can read it from disk, query it over
MCP, and contribute back through pull requests. Humans get the same data as a
dashboard.

Live dashboard: https://fomc-dashboard-woad.vercel.app

> Picking this up as an agent or developer? Read [AGENTS.md](AGENTS.md) first, then
> [docs/SCHEMA.md](docs/SCHEMA.md) before touching any data file.

## Quick start

Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Elendil-Labs/fomc-research
cd fomc-research
uv sync
uv run fomc status        # current stated regime + last meeting's SPY/TLT move + dip playbook
uv run fomc --help        # every command
```

The first `uv run fomc truth` fetches SPY/TLT history from Yahoo Finance into a
git-ignored `data/market/` cache. Everything else runs offline from the committed data.

## Read the data without cloning

Every dataset is a committed file, so an agent that can fetch a URL can use it
directly. Base URL: `https://raw.githubusercontent.com/Elendil-Labs/fomc-research/main/`

```bash
curl -s https://raw.githubusercontent.com/Elendil-Labs/fomc-research/main/apps/fomc-dashboard/public/data/fomc_event_truth.json
curl -s https://raw.githubusercontent.com/Elendil-Labs/fomc-research/main/apps/fomc-dashboard/public/data/regime_intel/latest.json
```

Field definitions are in [docs/SCHEMA.md](docs/SCHEMA.md). Check `generated_at` (regime
intel) and the last row of the truth table before relying on freshness. A short
machine-readable index of the repo is in [llms.txt](llms.txt).

## Data catalog

All data is licensed CC BY 4.0 (see [LICENSE-DATA](LICENSE-DATA)). A GitHub Actions
cron refreshes the intelligence feeds every weekday at about 07:30 ET and commits the
result; the FOMC corpus and truth table are refreshed on meeting days.

| Path | What | License | Refresh |
|---|---|---|---|
| `data/fomc/statement/text/` | Post-meeting policy statements, plain text (2018 to present) | Public domain (Fed), arrangement CC BY 4.0 | Meeting day (`fomc fetch`) |
| `data/fomc/minutes/text/` | Meeting minutes | same | ~3 weeks after each meeting |
| `data/fomc/sep/text/` | Summary of Economic Projections (dot plot tables) | same | Quarterly meetings |
| `data/fomc/press_conference_transcript/text/` | Chair press-conference transcripts | same | Meeting day (preliminary), final weeks later |
| `data/fomc/speech/text/`, `data/fomc/testimony/text/` | Chair speeches and Congressional testimony | same | `fomc speeches` |
| `data/fomc/warsh/` | Warsh confirmation testimony, QFR responses, dossier, manifest with blocked items | U.S. Senate works; dossier CC BY 4.0 | Manual (`fomc warsh`) |
| `data/fomc/manifest.json`, `speeches_manifest.json` | Document index: URL, sha256, byte size, fetch status | CC BY 4.0 | With each fetch |
| `data/fomc/analysis/regime_timeline.csv` | One row per rate decision: action, regime, target range | CC BY 4.0 | `fomc regime` |
| `data/fomc/analysis/fomc_event_truth.csv` | One row per FOMC event: regime, action, SPY/TLT returns pre-5d, day 0, +1/2/3/5/10 | CC BY 4.0 | `fomc truth` |
| `data/fomc/analysis/*.md`, `event_windows.csv`, `dip_events.csv`, `reversal_trades.csv` | Event study, dip cohort and backtest outputs | CC BY 4.0 | `fomc study`, `dips`, `backtest` |
| `apps/fomc-dashboard/public/data/fomc_event_truth.{csv,json}` | Dashboard copy of the truth table (typed JSON) | CC BY 4.0 | `fomc export-truth`, every cron run |
| `apps/fomc-dashboard/public/data/regime_intel/latest.json` | Scored intermeeting evidence: regime read, bucket scores, checklist, sources | CC BY 4.0 | Weekday 07:30 ET cron |
| `.../regime_intel/history.json`, `history/YYYY-MM-DD.json` | Daily net-lean series and full daily snapshots | CC BY 4.0 | Weekday cron |
| `.../regime_intel/balance_sheet.json` | Deterministic FRED balance-sheet axis (WALCL, WRESBAL, RRPONTSYD, DGS10, SOFR-IORB) | CC BY 4.0; FRED cited | Weekday cron |
| `.../regime_intel/market_pricing_axis.json` | Deterministic FRED market-pricing axis (DGS2, 10y-2y, 2y-DFF, net liquidity) | CC BY 4.0; FRED cited | Weekday cron |
| `.../regime_intel/sources.jsonl` | Append-only audit feed of every collected source | CC BY 4.0 | Weekday cron |
| `data/market/` | SPY/TLT daily history from yfinance | Not redistributed (git-ignored) | Run time |

Field-by-field documentation: [docs/SCHEMA.md](docs/SCHEMA.md). Source provenance:
[docs/PROVENANCE.md](docs/PROVENANCE.md).

## The `fomc` CLI

Thin dispatcher in `packages/fomc/src/fomc/cli.py`; each command delegates to its
module, so `uv run fomc <cmd> --help` shows that command's options.

| Command | Module | What it does |
|---|---|---|
| `status` | `status.py` | Start here. Current regime, last meeting's SPY/TLT move, regime-conditioned dip playbook. |
| `regime` | `regime.py` | Build and print the hiking vs easing timeline; writes `regime_timeline.csv`. Exposes `regime_on(date)`. Exit code 2 with an ALARM if the newest statement fails to parse. |
| `truth` | `truth.py` | Per-event SPY/TLT source-truth table; writes `fomc_event_truth.csv` and `.md`. |
| `export-truth` | `export_truth.py` | Re-shape the canonical CSV into the dashboard's `public/data/` CSV and typed JSON (offline). |
| `study` | `event_study.py` | SPY/TLT returns 5 sessions before and after each FOMC; aggregates and conditional tables. |
| `dips` | `dip_analysis.py` | The "SPY fell on the decision day" cohort by horizon and drop depth. |
| `backtest` | `backtest.py` | Decision-day reversal rules with per-trade P&L, t-stats, stability split. |
| `fetch` | `fetch.py` | Download statements, minutes, SEP and press-conference transcripts from federalreserve.gov. |
| `speeches` | `speeches.py` | Download Fed speeches and testimony by speaker (default Powell). |
| `warsh` | `warsh.py` | Download the curated, freely available Warsh primary text. |

## MCP server: `fomc-intel`

`packages/fomc-server` exposes the database as an MCP server (stdio by default) with
16 tools: 12 read tools (`get_fomc_guide`, `get_regime_read`, `get_two_axis_state`,
`get_balance_sheet_axis`, `get_market_pricing_axis`, `get_playbook`,
`get_event_history`, `get_news_evidence`, `get_daily_log`, `get_checklist`,
`get_stated_regime`, `get_fomc_calendar`), 2 corpus tools (`search_fed_corpus`,
`diff_statements`) and 2 live pipeline tools (`refresh_intel`, `ingest_meeting`).
Every data-bearing response carries a `provenance` block (`data_as_of`,
`retrieved_at`, `source`, `is_stale`). Details in
[packages/fomc-server/README.md](packages/fomc-server/README.md).

Claude Code (`.mcp.json` or `claude mcp add`) and Claude Desktop
(`claude_desktop_config.json`) use the same JSON:

```json
{"mcpServers":{"fomc-intel":{"command":"uv","args":["run","--project","<path-to-repo>/packages/fomc-server","fomc-intel"]}}}
```

Run `uv sync` once from the repo root first. The read and corpus tools need no keys;
the pipeline tools need `PPLX_API_KEY_fomc` and optionally `FRED_API_KEY` in a
repo-root `.env`. For remote hosting, `fomc-intel --transport http --port 8848`
serves the same tools over HTTP.

## Key findings

These are the owner's own results from the committed tables. Do not re-derive them on
a subsample.

- The dip edge is regime-dependent; this is the core result. "SPY fell on the
  decision day, buy it" works in Easing regimes (SPY +5d about +0.39%, 61% win, n=18)
  but not in Tightening (about -0.25%, 41% win, n=17). The full-sample average
  (about +0.08%) is two opposite regimes cancelling. TLT splits the same way.
- A smaller 2020-2026-only sample made the dip edge look strong (+0.56% at 5d).
  Extending to Powell's full term from 2018-03-21 collapsed it. Always use the full
  sample.
- `tlt_fade` (short TLT after FOMC) is the most horizon-robust rule but weak (t about 1).
- None of these clear |t| of about 2. They are tendencies, not proven alpha. No
  transaction costs are modeled.

## Dashboard

`apps/fomc-dashboard/` is a static Vite + React + TypeScript app with two views: the
Event Explorer (historical SPY/TLT reactions from the truth table) and the Regime
Intelligence feed (whether incoming employment, inflation, Fed-communication and
market-pricing evidence keeps the current regime or points toward a change). Every
claim links to its source.

```bash
cd apps/fomc-dashboard && npm ci && npm run dev    # http://localhost:5173
npm test
```

## What is not here

This public repository is the research database and its tooling only. It does not
contain:

- The proprietary Color Day SPY/TLT trading engine (signals, sizing, execution).
- Narrative and LinkedIn content built on this research.
- Broker integrations or any order-placement code.

Nothing in this repository places trades or is wired to a broker.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Commits need a DCO sign-off (`git commit -s`).
Issues use structured titles: `[data]`, `[meeting]`, `[source]`, `[bug]`, `[question]`.

## License

- Code (`packages/`, `scripts/`, `apps/` except `public/data/`, `.github/`):
  [PolyForm Noncommercial License 1.0.0](LICENSE). Free for personal, research,
  educational, nonprofit and government use; commercial use needs a separate license
  from Elendil Labs.
- Data (`data/`, `apps/fomc-dashboard/public/data/`):
  [Creative Commons Attribution 4.0 International](LICENSE-DATA). Attribute as:
  `FOMC Research database © 2026 Elendil Labs, CC BY 4.0, https://github.com/Elendil-Labs/fomc-research`
- Third-party provenance: [NOTICE](NOTICE) and [docs/PROVENANCE.md](docs/PROVENANCE.md).

## Disclaimer

Proprietary research, not investment advice. Everything here is historical and
observational evidence on a sample of roughly 70 FOMC events. It is not a
recommendation to buy or sell anything, and past reactions do not predict future ones.

© 2026 Elendil Labs.
