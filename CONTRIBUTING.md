# Contributing to fomc-research

Thanks for helping. This repository is an open FOMC research database plus the tooling
that builds it. Contributions from people and from AI agents are both welcome, and the
rules below apply to both.

## Sign-off (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/) instead
of a CLA. Every commit must carry a `Signed-off-by` line with a real name and email:

```bash
git commit -s -m "Add the 2026-09-16 statement"
```

By signing off you certify that you wrote the change or have the right to submit it
under the repository's licenses (code: PolyForm Noncommercial 1.0.0; data: CC BY 4.0).
Unsigned commits will be asked to be amended before merge.

## Running the tests

Python (root workspace, Python 3.13+, `uv`):

```bash
uv sync
uv run pytest -q
```

Dashboard (Node 20+):

```bash
cd apps/fomc-dashboard && npm ci && npm test
```

Run both before opening a pull request. Keep new Python tests offline (parse and
statistics logic, not live fetches).

## Adding a new FOMC meeting

On or after a decision day:

```bash
uv run fomc fetch           # pull the new statement (and minutes/SEP/transcript when posted)
uv run fomc truth           # rebuild the per-event SPY/TLT truth table (fetches prices into data/market/)
uv run fomc export-truth    # re-shape the canonical CSV into apps/fomc-dashboard/public/data/
```

Then `uv run fomc regime` to confirm the new row appears with the expected action and
regime. The statement parser is hardened: if the newest statement file fails to parse,
`fomc regime` prints a loud ALARM block and exits with code 2, and `fomc status` and
the MCP `get_stated_regime` tool report `stale: true`. The regime is then frozen at the
last parsed meeting. Do not commit a frozen regime. Fix the parser (usually a new
action verb in the statement text; see the gotchas in `AGENTS.md`), add a test in
`packages/fomc/tests/`, and re-run.

Commit the extracted text under `data/fomc/<type>/text/`, the updated manifest, the
regenerated `data/fomc/analysis/*.csv` files and the exported dashboard JSON/CSV
together in one PR. Raw HTML/PDF under `raw/` is git-ignored and must not be added.

## Adding or disputing a regime-intel source

The news feed under `apps/fomc-dashboard/public/data/regime_intel/` is produced by
`scripts/collect_regime_intel.py` and scored by `scripts/score_regime_intel.py`. To
add or correct a source:

- Edit through the collector contract, not by hand-writing prose. Every source must
  conform to the `IntelSource` dataclass in `scripts/_intel_common.py` (see
  `docs/SCHEMA.md`). Keep the `event_key` so the scorer clusters it with other outlets
  covering the same underlying release or statement.
- Never add a verbatim quotation attributed to a named person. `evidence_text` is a
  one-sentence paraphrase in your own words. The scorer refuses to surface any
  attributed-quote span in the summary, and reviewers will reject one in a PR.
- To dispute a source (wrong direction, wrong bucket, misattributed paraphrase), open
  an Issue titled `[source] <src_id or URL>: <what is wrong>` with a link to the
  primary document. Corrections that change scores should be PRs that include the
  regenerated `latest.json`, `history.json` and `history/<date>.json`.

## Data-provenance rules

- Public-domain or CC-compatible material only. Federal Reserve and other U.S.
  government works qualify. Publisher article bodies do not.
- No price series. Do not commit SPY, TLT or any other market history. `data/market/`
  is git-ignored on purpose; the truth table carries only per-event returns and the
  decision-day close.
- No paywalled or copyrighted text. Cite it by URL (as `warsh_manifest.json` does
  for the blocked Warsh items).
- Every derived table must be reproducible from a command in this repo. Do not
  hand-edit anything under `data/fomc/analysis/` or `apps/fomc-dashboard/public/data/`.
- See `docs/PROVENANCE.md` for the source-by-source record.

## Secrets

- Never commit `.env`, API keys or tokens. `.gitignore` excludes `.env`; check
  `git diff --cached` before every commit anyway.
- CI uses two repository secrets: `PPLX_API_KEY_fomc` (Perplexity, news collection)
  and `FRED_API_KEY` (FRED API, balance-sheet and market-pricing axes). Both scripts
  degrade gracefully without a key (the scorer preserves the previous snapshot flagged
  `stale`, the FRED axes write `available: false`).
- Pull requests from forks do not receive repository secrets. If your PR refreshes
  data, run the pipeline locally with your own keys and include the regenerated JSON
  in the PR.

## For agents

AI agents (Claude Code, Codex, and others) are first-class contributors here. Read
`AGENTS.md` and `docs/SCHEMA.md` before touching data.

- Open an Issue with a structured title: `[data]`, `[meeting]`, `[source]`, `[bug]`
  or `[question]`, followed by a one-line summary. Put the evidence (command output,
  file path, primary-source URL) in the body.
- Propose data changes as pull requests that contain the regenerated files, since CI
  will not run the paid collectors for you.
- When you cite this repository's data in your own output, carry the `provenance`
  block that every MCP tool returns (`data_as_of`, `retrieved_at`, `source`,
  `is_stale`) so readers can tell how fresh the evidence was.
- Do not paste `evidence_text` as if it were a quote from the publisher. It is a
  machine paraphrase.

## Style

Type hints on function signatures, dataclasses or TypedDicts over raw dicts, small
focused functions, `ruff` clean (`uv run ruff check .`). Commit messages explain why,
not what. No emojis.
