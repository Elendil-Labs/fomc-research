# AGENTS.md

Onboarding for any AI agent or developer picking up this repository. Tool-agnostic:
nothing here assumes a particular agent or IDE. Read this first, then `README.md`
(overview and catalog) and `docs/SCHEMA.md` (field-level contracts) before you touch
any data file.

---

## 1. What this project is

An open FOMC research database and tooling. It collects Federal Reserve primary
sources, derives a hiking/easing regime flag from the statements, builds a per-event
table of how SPY (equities) and TLT (long Treasuries) traded around every FOMC
decision since 2018, and maintains a daily scored feed of intermeeting evidence
(news, FRED balance-sheet data, FRED market-pricing data). The same data is served
over MCP (`fomc-intel`) and as a static dashboard.

Current state: working. Corpus spans 2018-01-31 to present; the truth table holds
70 events (Yellen 1, Powell 67, Warsh 2). All analysis runs from the CLI.

---

## 2. Setup and run

- Python 3.13+, package manager `uv`. Do not use `pip` or the system Python.
- One-time, from the repo root: `uv sync`. This builds the root `.venv/` and installs
  the `fomc` and `fomc-server` workspace packages plus the `fomc` and `fomc-intel`
  console scripts.
- Run anything with `uv run <cmd>`:
  ```bash
  uv run fomc status                 # current regime + SPY/TLT playbook
  uv run fomc --help                 # list commands
  uv run pytest -q                   # full offline suite
  ```
- Equivalent to `uv run fomc <x>`: `uv run python -m fomc.<module>`.
- Node 20+ for the dashboard: `cd apps/fomc-dashboard && npm ci && npm test`.
- Optional keys, in a repo-root `.env` (never committed): `PPLX_API_KEY_fomc` for the
  news collector, `FRED_API_KEY` for the two FRED axes. Everything else is offline.

---

## 3. Command surface (`fomc <command>`)

Thin dispatcher in `packages/fomc/src/fomc/cli.py`; each command delegates to its
module's `main(argv)`, so `uv run fomc <cmd> --help` shows that command's options.

| Command | Module | What it does |
|---|---|---|
| `status` | `status.py` | Start here. Current regime, last meeting's SPY/TLT move, regime-conditioned dip playbook. Forward-looking. |
| `regime` | `regime.py` | Build/print the hiking vs easing timeline; writes `regime_timeline.csv`. Exposes `regime_on(date)`. Exit 2 with an ALARM when the newest statement fails to parse. |
| `truth` | `truth.py` | Per-event SPY/TLT source-truth table; writes `fomc_event_truth.csv` + `.md`. Fetches prices into `data/market/`. |
| `export-truth` | `export_truth.py` | Offline re-shape of the canonical CSV into `apps/fomc-dashboard/public/data/` (CSV + typed JSON). |
| `study` | `event_study.py` | SPY/TLT returns 5d before and after each FOMC; aggregates and conditional tables. |
| `dips` | `dip_analysis.py` | The "SPY fell on the decision day" cohort, by horizon and drop depth. |
| `backtest` | `backtest.py` | Decision-day reversal rules with per-trade P&L, t-stats, stability split. |
| `fetch` | `fetch.py` | Download FOMC statements/minutes/SEP/press-conf from federalreserve.gov. |
| `speeches` | `speeches.py` | Download Fed speeches and testimony by speaker (default Powell). |
| `warsh` | `warsh.py` | Download curated free Warsh primary text (he is off the Fed site). |

The reusable primitive everything conditions on: `regime_on(date) -> {regime, action,
target_low, target_high, as_of}` in `regime.py`. Analysis modules compose by importing
`load_prices` and `load_event_dates` from `event_study.py` and `build_timeline` /
`regime_on` from `regime.py`.

Pipeline scripts (`scripts/`, stdlib only so CI needs nothing extra):

| Script | Needs | Writes |
|---|---|---|
| `collect_regime_intel.py --model sonar` | `PPLX_API_KEY_fomc` | `regime_intel/latest_raw.json`, appends `sources.jsonl` |
| `score_regime_intel.py [--next-fomc DATE]` | nothing | `regime_intel/latest.json`, `history.json`, `history/<date>.json` |
| `collect_balance_sheet.py` | `FRED_API_KEY` | `regime_intel/balance_sheet.json` |
| `collect_market_pricing.py` | `FRED_API_KEY` | `regime_intel/market_pricing_axis.json` |
| `export_event_truth_json.py` | nothing | thin wrapper over `fomc export-truth` |

---

## 4. Layout

```
fomc-research/
├── AGENTS.md  README.md  CONTRIBUTING.md  NOTICE  LICENSE  LICENSE-DATA
├── pyproject.toml            # uv workspace root; .venv/ lives here (git-ignored)
├── docs/                     # SCHEMA.md (field contracts), PROVENANCE.md (sources + licensing)
├── packages/
│   ├── fomc/                 # analysis package: src/fomc/*.py + tests/
│   └── fomc-server/          # MCP server `fomc-intel`: src/fomc_server/ + tests/
├── scripts/                  # regime-intel collector/scorer, FRED axes + tests/
├── apps/fomc-dashboard/      # Vite + React + TS static app
│   └── public/data/          # what the app and the MCP server read (tracked, generated)
│       ├── fomc_event_truth.{csv,json}
│       └── regime_intel/{latest.json, history.json, history/, balance_sheet.json,
│                         market_pricing_axis.json, sources.jsonl}
├── data/fomc/
│   ├── <type>/raw/           # raw HTML/PDF: GIT-IGNORED, reproducible via `fomc fetch`
│   ├── <type>/text/          # extracted plain text: TRACKED
│   │     types: statement, minutes, sep, press_conference_transcript, speech, testimony
│   ├── warsh/                # warsh_dossier.md + primary text + warsh_manifest.json
│   ├── manifest.json         # FOMC meeting-doc index (+ speeches_manifest.json)
│   └── analysis/             # generated tables; see analysis/README.md
├── data/market/              # yfinance SPY/TLT cache: GIT-IGNORED, created on first `fomc truth`
└── .github/workflows/        # weekday 07:30 ET data refresh
```

---

## 5. Key findings (so you do not re-derive or misuse them)

- The dip edge is regime-dependent; this is the core result. "SPY fell on the
  decision day, buy it" works in Easing regimes (SPY +5d about +0.39%, 61% win, n=18)
  but not in Tightening (about -0.25%, 41% win, n=17). The full-sample average (about
  +0.08%) is a mirage: two opposite regimes cancelling. TLT splits the same way.
- A smaller (2020-2026-only) sample made the dip edge look strong (+0.56% at 5d);
  extending to Powell's full term (from 2018-03-21) collapsed it. Always use the full
  sample.
- `tlt_fade` (short TLT after FOMC) is the most horizon-robust rule but weak (t about 1).
- None of these clear |t| of about 2. They are tendencies, not proven alpha. No
  transaction costs.

---

## 6. Gotchas / non-obvious facts

- Regime parsing depends on statement verbs. `regime.py` matches raise/lower/maintain
  and also `keep`/`leave`; the 2020-21 ZLB statements say "decided to keep", and
  omitting those silently drops the entire zero-rate era. If you touch the parser,
  re-check `uv run fomc regime` spans against history.
- The parser is hardened. If the newest statement in `data/fomc/statement/text/`
  fails to parse, `fomc regime` prints an ALARM and exits 2, and `get_stated_regime`
  reports `stale: true`. The regime is then frozen at the last parsed meeting. Never
  commit in that state; fix the parser and add a test.
- Price seam. SPY/TLT history is fetched from yfinance (`auto_adjust=False`, raw close)
  into `data/market/`. Re-running on a later date changes the most recent rows of any
  table that depends on prices. `fomc export-truth` is offline on purpose so the
  dashboard JSON is byte-for-byte reproducible from the committed CSV.
- `fomc status` uses the real clock; pass `--date YYYY-MM-DD` to evaluate as of a
  past date.
- Warsh's press-conference transcript is the Fed's PRELIMINARY same-day version.
  The FINAL posts weeks later; re-run `fomc fetch` then to replace it.
- Four Warsh documents are intentionally not included (three Hoover Institution
  items, including the "Inflation Is a Choice" interview transcript, and a WSJ
  op-ed; all copyrighted). They are cited by URL only in
  `data/fomc/warsh/warsh_manifest.json`. The interview still appears under
  `documents` there with a `text_path` that does not exist in this repo; that is
  deliberate. Do not add their text.
- Verify fetched bytes are the claimed type. An earlier pass reported Hoover PDFs as
  downloaded when the bytes were HTML 404 pages. Check content-type or magic bytes,
  not just HTTP 200.
- Weekend/holiday FOMC actions (the Sunday 2020-03-15 cut, for example) roll to the
  next trading session for return math; they are flagged `emergency` and excluded from
  aggregates.
- `evidence_text` in the news feed is a machine paraphrase from the collector model,
  not publisher text. The scorer's summary cites publisher + title only and refuses
  attributed-quote spans. Do the same in anything you write from this data.
- `raw/` directories and `data/market/` are git-ignored (large, reproducible). Tracked
  truth = `text/` + manifests + `analysis/` + `apps/fomc-dashboard/public/data/`.

---

## 7. Data provenance

- All FOMC documents come directly from `federalreserve.gov` (statements, minutes,
  SEP, press-conference transcripts, speeches, testimony). `fetch.py` is link-driven
  (it scrapes the FOMC calendar and materials pages), so it captures off-schedule
  meetings. These are U.S. government works in the public domain.
- Warsh material comes from `banking.senate.gov` (U.S. government works) plus a
  sourced, dated dossier; see `warsh_dossier.md` and `warsh_manifest.json`.
- FRED series (WALCL, WRESBAL, RRPONTSYD, DGS2, DGS10, T10Y2Y, DFF, SOFR, IORB,
  WTREGEN) feed the two deterministic axes; only latest values, 90-day changes and
  signals are stored.
- Market data: yfinance at run time, never committed.
- Full record and licensing: `docs/PROVENANCE.md` and `NOTICE`.

---

## 8. Testing and verification

```bash
uv run pytest -q                              # everything: packages/fomc, packages/fomc-server, scripts/tests
uv run pytest packages/fomc/tests -q          # analysis package only
cd apps/fomc-dashboard && npm ci && npm test  # frontend
```

Smoke check the pipeline end to end:

```bash
uv run fomc regime && uv run fomc truth && uv run fomc export-truth && uv run fomc status
```

Expected: regime spans print without an ALARM, the truth table reports 70 events
(more after each new meeting), the export reports the same count, and `status` shows
the current stated regime. If the spans look wrong, suspect the statement parser
(gotcha 1).

---

## 9. How agents should collaborate here

- Read `docs/SCHEMA.md` before reading or writing any data file. Field names there are
  derived from the files, and the MCP tools return the same shapes.
- Propose data changes as pull requests that include the regenerated JSON/CSV.
  Pull requests from forks do not get CI secrets, so the paid collectors will not run
  for you.
- Use Issues with structured titles: `[data]`, `[meeting]`, `[source]`, `[bug]`,
  `[question]`. Put file paths, command output and primary-source URLs in the body.
- Every MCP tool returns a `provenance` block: `{data_as_of, retrieved_at, source,
  is_stale}` (stale after 36 hours). Carry it into anything you produce from this data
  so a reader can tell how fresh the evidence was.
- Sign commits off (`git commit -s`); see `CONTRIBUTING.md`.

---

## 10. Open items / suggested next steps

- Make `--regime` / `--action` first-class filters on `dips` / `backtest` / `study`
  (currently the split is computed only inside `status`).
- Re-fetch Warsh's FINAL press-conference transcript once the Fed posts it.
- Add speakers beyond Powell to `fomc speeches` and to the corpus search.

---

## 11. Code conventions

- Type hints on function signatures; dataclasses/TypedDicts over raw dicts for
  structured data. Keep functions small and focused.
- Network code: polite delay, browser-like User-Agent, handle non-200 gracefully.
- New features get offline tests (`packages/fomc/tests/`, `packages/fomc-server/tests/`,
  `scripts/tests/`): parse and statistics logic, not live fetches.
- Generated artifacts go under `data/fomc/analysis/` and
  `apps/fomc-dashboard/public/data/`; do not hand-edit them.
- MCP tools return dicts and never raise; errors come back as `{"error": "..."}`.
