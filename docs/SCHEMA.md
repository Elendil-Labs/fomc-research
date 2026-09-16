# Data schema

Field-level contracts for every tracked data file an agent is likely to read or
regenerate. Field names below are taken from the files as committed, not from
memory. Return fields are in percent unless stated otherwise. `dN`, `pN` and `+Nd`
all mean N trading sessions relative to the FOMC decision day. Dates are ISO 8601
(`YYYY-MM-DD`); timestamps are ISO 8601 with a UTC offset.

Contents

1. `fomc_event_truth.json` / `.csv`
2. `regime_timeline.csv`
3. `regime_intel/latest.json` (and `history/YYYY-MM-DD.json`)
4. `regime_intel/history.json`
5. `regime_intel/balance_sheet.json`
6. `regime_intel/market_pricing_axis.json`
7. `regime_intel/sources.jsonl` and `latest_raw.json`
8. Manifests
9. MCP `provenance` block

---

## 1. `fomc_event_truth.json` / `fomc_event_truth.csv`

Canonical: `data/fomc/analysis/fomc_event_truth.csv` (built by `fomc truth`).
Dashboard copies: `apps/fomc-dashboard/public/data/fomc_event_truth.csv` (byte-for-byte
copy) and `fomc_event_truth.json` (typed, built by `fomc export-truth`).

JSON envelope:

| Field | Type | Meaning |
|---|---|---|
| `generated_at` | timestamp | When the export ran. |
| `source` | string | Repo-relative path of the canonical CSV. |
| `count` | int | Number of rows in `events`. |
| `first_event_date` | date | Earliest `date` (currently `2018-01-31`). |
| `latest_event_date` | date | Latest `date`. Also anchors the regime-intel window (`window_start`). |
| `columns` | string[] | Column order, identical to the CSV header. |
| `events` | object[] | One row per FOMC event, schema below. |

Row fields (22 columns, in order). In the CSV every cell is text; in the JSON the
first five are strings, `emergency` is a boolean, and every other column is a float
or `null` when the value is missing (for example horizons that have not happened yet
for the newest meeting).

| Field | Type | Meaning |
|---|---|---|
| `date` | date | FOMC decision date (statement release). Weekend/holiday emergency actions keep their calendar date; return math rolls to the next trading session. |
| `chair` | string | `Yellen`, `Powell` or `Warsh`. |
| `regime` | string | Regime in effect after this meeting: `Tightening`, `Easing`, or `Unknown` (only the 2018-01-31 hold, before the first parsed directional move). Holds inherit; the last directional move sets the regime. |
| `action` | string | `Hike`, `Cut` or `Hold`. |
| `ff_target` | string | Fed funds target range after the meeting, `"low-high"` in percent, e.g. `"3.50-3.75"`. |
| `emergency` | bool | `true` for off-schedule actions (the two March 2020 cuts). Excluded from aggregates. |
| `spy_close` | float | SPY closing price on the decision day (raw close, not adjusted). USD. |
| `spy_pre5` | float | SPY return over the 5 sessions ending on the session before decision day, percent. |
| `spy_d0` | float | SPY return on the decision day (close-to-close), percent. |
| `spy_p1` | float | SPY return from decision-day close to close 1 session later, percent. |
| `spy_p2` | float | Same, 2 sessions later. |
| `spy_p3` | float | Same, 3 sessions later. |
| `spy_p5` | float | Same, 5 sessions later. |
| `spy_p10` | float | Same, 10 sessions later. |
| `tlt_close` | float | TLT closing price on the decision day. USD. |
| `tlt_pre5`, `tlt_d0`, `tlt_p1`, `tlt_p2`, `tlt_p3`, `tlt_p5`, `tlt_p10` | float | TLT returns, same definitions as the SPY columns. |

Color-day rule (used by the dashboard, `fomc status`, and `get_event_history`,
computed from `spy_d0` and `tlt_d0`; zero counts as up):

| Color | SPY day 0 | TLT day 0 |
|---|---|---|
| `green` | >= 0 | >= 0 |
| `orange` | >= 0 | < 0 |
| `blue` | < 0 | >= 0 |
| `red` | < 0 | < 0 |

`null` when either day-0 return is missing.

Current counts (2026-09): 70 events; Powell 67, Warsh 2, Yellen 1; Easing 38,
Tightening 31, Unknown 1; Hold 44, Hike 15, Cut 11; 2 emergencies.

---

## 2. `regime_timeline.csv`

`data/fomc/analysis/regime_timeline.csv`, built by `fomc regime` from the statement
text. One row per FOMC statement that states a target range.

| Field | Type | Meaning |
|---|---|---|
| `date` | date | Statement date. |
| `action` | string | `Hike`, `Cut` or `Hold`, parsed from the statement verb (raise / lower / maintain / keep / leave). |
| `regime` | string | `Tightening`, `Easing` or `Unknown`, as in the truth table. |
| `target_low` | float | Lower bound of the target range, percent. |
| `target_high` | float | Upper bound, percent. |
| `target_mid` | float | Midpoint, percent. |
| `change_bps` | int or empty | Change in `target_mid` versus the previous row, basis points. Empty on the first row. |
| `trailing_12m_bps` | int or empty | Cumulative change in `target_mid` over the trailing 12 months, basis points. Empty until 12 months of history exist. |

The Python primitive `regime_on(date)` returns `{regime, action, target_low,
target_high, as_of}` for any date by looking up the last row on or before it.

---

## 3. `regime_intel/latest.json`

`apps/fomc-dashboard/public/data/regime_intel/latest.json`, built by
`scripts/score_regime_intel.py` from `latest_raw.json`. Every run also writes a full
copy to `history/YYYY-MM-DD.json` with exactly the same keys.

### Top level

| Field | Type | Meaning |
|---|---|---|
| `generated_at` | timestamp | When the scorer ran. |
| `run_id` | timestamp | `generated_at` of the collector run being scored. |
| `window_start` | date | Start of the intermeeting evidence window = `latest_event_date` of the truth table. Sources published before it are dropped, so the feed resets at each FOMC meeting. |
| `window_end` | date | Scoring date. |
| `current_repo_regime` | string | The statement-derived regime (`Easing` / `Tightening`) the read is anchored to. |
| `inferred_regime` | string | Four-state descriptor: `Easing`, `Tightening` (evidence confirms the stated regime), `Potential pivot → tightening`, `Potential pivot → easing` (evidence points against it), or `Mixed`. |
| `conviction` | string | `Low`, `Moderate` or `High`, from the margin of the leading share and the number of distinct events. |
| `evidence_shares` | object | `{easing, neutral, tightening}` weighted vote shares, each 0..1, summing to 1. |
| `net_lean` | float | `tightening - easing` share, -1..+1. Positive leans tightening. |
| `evidence_dir` | string | `easing`, `neutral` or `tightening`: the direction with the largest share. |
| `next_fomc_meeting` | date or null | Next scheduled decision date, from the MCP calendar. |
| `new_this_run` | int | Sources first seen in this run. |
| `n_sources` | int | Sources in the window feed. |
| `n_events` | int | Distinct event clusters (votes). |
| `stale` | bool | `true` when collection failed and the previous snapshot was re-emitted. |
| `error_summary` | string or null | Why the run is stale, if it is. |
| `bucket_scores` | object | Per-bucket breakdown, below. |
| `summary` | string | Generated prose read. Cites sources as `per <publisher>: <title>`; never includes `evidence_text`. |
| `what_would_change_the_call` | string[] | Conditions that would flip the read. Currently a fixed list of four. |
| `checklist` | object[] | Regime-change checklist, below. |
| `spytlt` | object | Market-confirmation signal, below. |
| `scoring` | object | The weights used, for transparency, below. |
| `sources` | object[] | Every source in the window, schema below. |

### `bucket_scores`

Keys: `employment`, `inflation`, `fed_communications`, `market_pricing`. Each value:

| Field | Type | Meaning |
|---|---|---|
| `shares` | object | `{easing, neutral, tightening}` weighted shares within the bucket. |
| `net` | float | `tightening - easing` within the bucket. |
| `dominant` | string | Direction with the largest share. |
| `label` | string | One of `strongly tightening`, `leaning tightening`, `strongly easing`, `leaning easing`, `mixed`, `no directional signal`. "Strongly" means the leading side holds at least 75% of the directional (non-neutral) share. |
| `n` | int | Distinct event clusters in the bucket. |
| `n_sources` | int | Sources in the bucket. |
| `weight_sum` | float | Sum of source weights in the bucket. |

### `sources[]` element

Produced by the collector under the `IntelSource` contract in
`scripts/_intel_common.py`, then annotated by the merge step.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | `src_NNN`, assigned by recency each run. Not stable across runs; use `url` as identity. |
| `title` | string | Article or document title as reported by the collector. |
| `publisher` | string | Publisher name. |
| `url` | string | Direct link. Identity key for de-duplication. |
| `published_at` | timestamp | Publication time, best estimate. |
| `bucket` | string | `employment`, `inflation`, `fed_communications`, `market_pricing` or `other`. |
| `direction` | string | `easing` (supports more cuts), `neutral`, `tightening` (fewer cuts or hikes). This is the only thing that votes. |
| `score` | int | -2..+2 magnitude assigned by the model. Reported but not averaged into the read. |
| `importance` | string | `low`, `medium`, `high`. |
| `confidence` | string | `low`, `medium`, `high`. |
| `claim_type` | string | `documented_fact`, `official_data`, `sell_side_scenario` or `interpretation`. Discounts narrative relative to fact. |
| `event_key` | string | Lowercase snake_case id of the underlying release/statement (e.g. `2026_08_bls_employment_situation`). Sources sharing a key form one voting cluster. Empty string = singleton cluster. |
| `evidence_text` | string | One-sentence MACHINE-GENERATED PARAPHRASE written by the collector model (Perplexity `sonar`) under a contract that forbids verbatim quotation. Not publisher text. Unverified; may misattribute. Never present it as a quote. |
| `why_it_matters` | string | One machine-generated sentence linking the item to the Fed reaction function. Same caveat. |
| `official` | bool | Publisher matched an official-source hint (Fed, BLS, BEA, Treasury, FRED, CME). |
| `collected_at` | timestamp | When the collector first fetched it (absent on a few legacy rows). |
| `first_seen_at` | timestamp | When it first entered the window feed. |
| `is_new` | bool | First appeared in this run. |

### `spytlt`

| Field | Type | Meaning |
|---|---|---|
| `window_days` | int | Trading days the trend is measured over (10). |
| `spy_ret` | float | SPY return over the window, as a fraction (not percent). |
| `tlt_ret` | float | TLT return over the window, as a fraction. |
| `as_of` | date | Last close used. |
| `status` | string | `confirmed`, `partial`, `not_confirmed` or `unknown`: whether the SPY/TLT move agrees with the evidence lean. Moves smaller than 0.5% read as flat. |

### `checklist[]`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | One of `comm_deemphasize_easing`, `comm_inflation_over_labor`, `pricing_removes_cuts`, `twoy_rises`, `inflation_upside`, `employment_firm`, `spytlt_confirms`. |
| `text` | string | Human wording of the condition. |
| `status` | string | `confirmed`, `partial` or `not_confirmed`, derived from the bucket nets (and `spytlt.status` for the last item). |

### `scoring`

Documents the model so a reader can reproduce the shares.

| Field | Type | Meaning |
|---|---|---|
| `method` | string | Weighted vote-share over direction, one vote per event cluster. |
| `clustering` | string | One vote per `event_key`; representative = max-weight source. |
| `tier_weights` | object | `{fed: 2.0, official: 1.5, news: 1.0}` by publisher. |
| `claim_type_weights` | object | `{documented_fact: 1.0, official_data: 1.0, sell_side_scenario: 0.6, interpretation: 0.4}`. |
| `importance_weights` | object | `{high: 1.0, medium: 0.6, low: 0.3}`. |
| `confidence_weights` | object | `{high: 1.0, medium: 0.7, low: 0.4}`. |
| `recency_decay` | string | `0-7d: 1.0, 8-14d: 0.75, 15-30d: 0.5, >30d: 0.25`, floored at 0.5 for Fed/official sources. |

Source weight = tier x claim_type x importance x confidence x recency.

### `what_would_change_the_call[]`

Plain strings. The current four are fixed in `score_regime_intel.py`
(`build_summary`): a second upside inflation surprise, 2Y yields rising further, a
Fed official pushing back on cuts, and futures repricing toward hikes.

---

## 4. `regime_intel/history.json`

Compact daily series for the trend chart and daily log.

| Field | Type | Meaning |
|---|---|---|
| `description` | string | Fixed description string. |
| `points` | object[] | One per scoring day, appended by the scorer. |

Each point:

| Field | Type | Meaning |
|---|---|---|
| `date` | date | Scoring date. |
| `net_lean` | float | As in `latest.json`. |
| `inferred_regime` | string | As in `latest.json`. |
| `conviction` | string | As in `latest.json`. |
| `new_this_run` | int | As in `latest.json`. |

---

## 5. `regime_intel/balance_sheet.json`

Deterministic balance-sheet / liquidity axis from FRED, built by
`scripts/collect_balance_sheet.py`. No LLM involved.

| Field | Type | Meaning |
|---|---|---|
| `generated_at` | timestamp | Run time. |
| `available` | bool | `false` when `FRED_API_KEY` is unset or FRED failed; then `indicators` is empty and the dashboard shows "axis pending". |
| `net_lean` | float | Weighted mean of indicator signals, -1..+1. Positive = tightening. |
| `label` | string | `tightening`, `neutral` or `loosening`. |
| `indicators` | object[] | Five rows, below. |
| `method` | string | Fixed description. |
| `source` | string | `FRED API (api.stlouisfed.org)`. |

Indicator rows (ids and weights): `WALCL` Fed balance sheet, $M, 0.28;
`WRESBAL` bank reserves, $M, 0.22; `RRPONTSYD` reverse-repo cushion, $B, 0.15;
`DGS10` 10y Treasury yield, %, 0.20; `SOFR_IORB` SOFR minus IORB spread, bp, 0.15.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Series id or derived id. |
| `name` | string | Human name. |
| `unit` | string | `$M`, `$B`, `%` or `bp`. |
| `weight` | float | Weight in `net_lean`. |
| `latest` | float | Latest observation (or spread). |
| `as_of` | date | Date of the latest observation. |
| `change_90d` | float | Change versus about 90 days earlier (change-mode indicators only). |
| `signal` | int | -1 loosening, 0 neutral, +1 tightening. |
| `detail` | string | Human-readable value or change. |
| `note` | string | Why it got that signal (e.g. `draining`, `near-depleted (QT cushion gone)`, `neutral`). |

---

## 6. `regime_intel/market_pricing_axis.json`

Deterministic market-pricing axis from FRED, built by
`scripts/collect_market_pricing.py`. Same envelope as `balance_sheet.json` plus:

| Field | Type | Meaning |
|---|---|---|
| `coverage` | float | Fraction of indicator weight that had data (1.0 = complete). |

Indicator rows (ids and weights): `DGS2` 2y yield 90-day momentum, %, 0.30;
`T10Y2Y` curve slope 10y minus 2y, %, 0.20; `DGS2_DFF` 2y minus effective fed funds
(hikes or cuts priced), %, 0.30; `NET_LIQUIDITY` WALCL minus TGA (WTREGEN) minus RRP,
$M, 0.20. Row fields as in section 5, with `prior_as_of` (date of the comparison
observation) present on change-mode rows.

---

## 7. `regime_intel/sources.jsonl` and `latest_raw.json`

`sources.jsonl`: append-only audit feed. One JSON object per line, the `IntelSource`
fields plus `collected_at`. Never rewritten; the merge step de-duplicates by
normalized URL and by the first eight words of the title.

`latest_raw.json`: the collector's output for the most recent run:
`{generated_at, window_start, window_end, model, errors[], error, new_this_run,
sources[]}`. Input to the scorer; not read by the dashboard.

---

## 8. Manifests

`data/fomc/manifest.json`: `{generated_at, source, doc_count, ok_count, documents[]}`.
Each document: `doc_type` (`statement`, `minutes`, `sep`,
`press_conference_transcript`), `meeting_date`, `suffix`, `url`, `ext`, `raw_path`,
`text_path`, `http_status`, `byte_size`, `sha256`, `fetched_at`, `error`. A 404 row is
a real absence on the Fed site (for example no press conference at some 2018
meetings), not a fetch failure.

`data/fomc/speeches_manifest.json`: same envelope plus `by_speaker`; documents carry
`speaker` and `speech_date` instead of `meeting_date`.

`data/fomc/warsh/warsh_manifest.json`: `{generated_at, note, doc_count, ok_count,
documents[], blocked[]}`. Documents add `slug`, `date`, `title`, `venue`, `doc_type`,
`text_chars`. `blocked[]` lists items cited by URL only (copyrighted or unreachable).
The Hoover interview transcript is listed under `documents` but its `text_path` is
intentionally absent from this repository (copyrighted); see `docs/PROVENANCE.md`.

Extracted text lives at `text_path`; `raw_path` is git-ignored.

---

## 9. MCP `provenance` block

Every data-bearing `fomc-intel` tool response includes:

| Field | Type | Meaning |
|---|---|---|
| `data_as_of` | timestamp or null | The underlying document's `generated_at`, else its file mtime. |
| `retrieved_at` | timestamp | When the tool answered. |
| `source` | string | Repo-relative path of the file the answer came from. |
| `is_stale` | bool | `true` when `data_as_of` is older than 36 hours or unknown. |

Carry this block forward when you cite the data.
