# fomc-intel — the FOMC dashboard as an MCP server

A local MCP server (stdio) over the repository data: the Fed's **stated**
regime (parsed from its own statements), what the weighted news evidence and the
deterministic FRED balance-sheet axis currently **lean**, what historically happened
to SPY/TLT around FOMC decisions under comparable conditions — plus live pipeline
tools to refresh the intel and ingest a new meeting on decision day.

## The 16 tools

### Read (12)
| Tool | What it returns |
| --- | --- |
| `get_fomc_guide` | Methodology orientation — call first each session |
| `get_regime_read` | Headline read: descriptor, conviction, net lean, stated regime |
| `get_two_axis_state` | News axis × balance-sheet axis, quadrant, divergence flag |
| `get_balance_sheet_axis` | The deterministic FRED indicators behind the second axis |
| `get_market_pricing_axis` | What the market prices for the Fed path (2y momentum, curve, 2y-vs-funds, net liquidity) |
| `get_playbook` | Next meeting, blackout window, conditional SPY/TLT stats |
| `get_event_history` | Filtered per-event truth table (regime/action/chair/color) |
| `get_news_evidence` | The scored sources behind the news axis |
| `get_daily_log` | Daily net-lean / inferred-regime history |
| `get_checklist` | What-would-change-the-call checklist |
| `get_stated_regime` | Statement-parsed regime on any date + parser audit/ALARM |
| `get_fomc_calendar` | 2026 decision dates, blackout windows, data coverage |

### Corpus (2)
| Tool | What it returns |
| --- | --- |
| `search_fed_corpus` | Regex/substring search over statements, minutes, speeches, testimony and the Warsh set (2018→), newest first, «»-marked snippets |
| `diff_statements` | The classic Fed-watcher redline: added/removed sentences and changed pairs between two statements (default: newest vs previous) |

### Pipeline (2 — these run live subprocesses)
| Tool | What it does |
| --- | --- |
| `refresh_intel` | Collect fresh news (Perplexity) → re-score the evidence → refresh the FRED balance-sheet axis; reports before/after regime read + delta |
| `ingest_meeting` | Meeting-day: fetch the new statement → rebuild the SPY/TLT truth table → re-export dashboard JSON → (default) re-run the news pipeline; surfaces the statement-parser STALE ALARM instead of failing |

## Setup

From the repo root, `uv sync` the package once (it also wires the lab's `fomc`
package as an editable path dependency):

```sh
uv sync --project packages/fomc-server
```

`claude_desktop_config.json`:

```json
{"mcpServers": {"fomc-intel": {"command": "uv", "args": ["run", "--project", "<path-to-repo>/packages/fomc-server", "fomc-intel"]}}}
```

### Keys for the pipeline tools

The read and corpus tools need no keys. The pipeline tools resolve keys from the
repo-root `.env` (the scripts read it themselves; the server only checks the key
*names* up front so you get a clear error instead of a silent empty run):

- `PPLX_API_KEY_fomc` (or `PPLX_API_KEY`) — required by `refresh_intel` and the
  news step of `ingest_meeting`
- `FRED_API_KEY` — the balance-sheet step (its failure is non-fatal)

`ingest_meeting` additionally requires the lab's own venv
(the repo-root `.venv` — create with `uv sync`); `refresh_intel`
prefers it and falls back to the server's interpreter (the return dict says which
was used).

## Meeting-day playbook

One prompt on decision day:

1. `ingest_meeting` — pull the new statement, rebuild truth, re-anchor the news window
2. `diff_statements` — what the Committee actually changed vs last meeting
3. `get_regime_read` — the refreshed two-axis read
4. `get_playbook` — conditional SPY/TLT base rates under the (possibly new) stated regime

### `publish=true`

`refresh_intel(publish=true)` / `ingest_meeting(publish=true)` stage **only**
`apps/fomc-dashboard/public/data`, commit as
`jingerzz <21320706+jingerzz@users.noreply.github.com>`, then fetch/rebase/push to
`origin/main` (up to 3 attempts). Nothing staged → no commit. Nothing else in the
worktree is ever touched.

## Remote hosting

`fomc-intel --transport http --port 8848` exists for remote hosting later (e.g. a Zo
box); stdio is the default.

---

Historical/observational evidence only — not investment advice.

© 2026 Elendil Labs
