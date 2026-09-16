# Provenance and licensing, source by source

What is in this repository, where it came from, what license it is under, and what
is deliberately left out. The short version is in `NOTICE`; this is the long one.

Repository licensing: code under PolyForm Noncommercial 1.0.0 (`LICENSE`); data under
CC BY 4.0 (`LICENSE-DATA`), attribution string
`FOMC Research database © 2026 Elendil Labs, CC BY 4.0, https://github.com/Elendil-Labs/fomc-research`.
The CC BY license covers Elendil Labs' selection, arrangement, extraction and derived
tables. It does not and cannot restrict the underlying U.S. government works, which
remain in the public domain.

## 1. Federal Reserve documents

| What | Where in repo | Origin | Rights |
|---|---|---|---|
| FOMC post-meeting statements | `data/fomc/statement/text/` | federalreserve.gov (FOMC calendar and historical materials pages) | U.S. government work, public domain |
| FOMC minutes | `data/fomc/minutes/text/` | federalreserve.gov | same |
| Summary of Economic Projections | `data/fomc/sep/text/` | federalreserve.gov (PDF projection tables) | same |
| Chair press-conference transcripts | `data/fomc/press_conference_transcript/text/` | federalreserve.gov (PDF) | same |
| Chair speeches | `data/fomc/speech/text/` | federalreserve.gov speeches index | same |
| Chair testimony | `data/fomc/testimony/text/` | federalreserve.gov testimony index | same |

Method: `fomc fetch` and `fomc speeches` are link-driven. They scrape the official
calendar and index pages for real document URLs rather than guessing, so off-schedule
items (the March 2020 emergency meetings) are captured. Each document is saved raw
(HTML or PDF, git-ignored) and as extracted plain text (tracked). `manifest.json` and
`speeches_manifest.json` record the URL, sha256, byte size, HTTP status and fetch time
for every document, including 404s, so any file can be re-verified against the source.

Known limitation: the newest press-conference transcript may be the Fed's preliminary
same-day version until the final is posted and re-fetched.

## 2. U.S. Senate documents (Warsh)

| What | Where in repo | Origin | Rights |
|---|---|---|---|
| Confirmation opening statement / written testimony, 2026-04-21 | `data/fomc/warsh/text/2026-04-21_senate_testimony.txt` | banking.senate.gov (PDF) | U.S. government work |
| Combined Questions for the Record responses, 2026-04-23 | `data/fomc/warsh/text/2026-04-23_qfr_responses.txt` | banking.senate.gov (PDF) | U.S. government work |

`data/fomc/warsh/warsh_dossier.md` is an Elendil Labs summary of Warsh's public record
with dated citations; it is CC BY 4.0 like the rest of the data and quotes nothing at
length.

## 3. Intentionally excluded Warsh material

Cited by URL only in `data/fomc/warsh/warsh_manifest.json`; their text is not in this
repository:

- Hoover Institution: "Inflation Is a Choice: Warsh on Fixing the Federal Reserve"
  interview transcript (Uncommon Knowledge, 2025-07-08). Copyrighted by the Hoover
  Institution. The manifest lists it under `documents` because it was reachable, but
  its `text_path` is intentionally absent here.
- Hoover Institution: "Commanding Heights: Central Banks at a Crossroads" (G30 spring
  lecture, 2025-04-25). In `blocked`: copyrighted, and the PDF URL 404s.
- Hoover Institution: "Reinvigorating Economic Governance" (Cogan and Warsh,
  2022-03-01). In `blocked`: copyrighted, and the PDF URL 404s.
- Wall Street Journal: "The Federal Reserve's Broken Leadership" op-ed by Kevin Warsh
  (2025-11-16). In `blocked`: paywalled and copyrighted.

Do not add the text of these items. If you need them, read them at the cited URL.

## 4. FRED series

The balance-sheet and market-pricing axes are computed by
`scripts/collect_balance_sheet.py` and `scripts/collect_market_pricing.py` from the
FRED API (api.stlouisfed.org), Federal Reserve Bank of St. Louis.

| Series | Used for |
|---|---|
| `WALCL` | Fed total assets (balance-sheet axis; net liquidity) |
| `WRESBAL` | Bank reserves |
| `RRPONTSYD` | Overnight reverse repo |
| `DGS2` | 2-year Treasury yield (momentum; 2y minus funds) |
| `DGS10` | 10-year Treasury yield (term-premium proxy; curve slope) |
| `T10Y2Y` | 10y minus 2y slope (computed from DGS10 and DGS2) |
| `DFF` | Effective federal funds rate |
| `SOFR` | Secured overnight financing rate (repo stress spread) |
| `IORB` | Interest on reserve balances (repo stress spread) |
| `WTREGEN` | Treasury General Account (net liquidity) |

What is stored: per indicator, the latest value, its date, a 90-day change where
applicable, a -1/0/+1 signal and a short note. The FRED series themselves are not
redistributed. FRED data is used and cited under the FRED terms of use
(https://fred.stlouisfed.org/legal/); some underlying series are produced by third
parties and carry their own terms, which is a further reason the raw observations
stay out of the repo.

## 5. SPY and TLT prices

Not redistributed. The repository contains:

- In the truth table (`fomc_event_truth.csv/.json`): per-event return percentages
  and the closing price of SPY and TLT on each of roughly 70 FOMC decision days.
- Nothing else. No daily series, no intraday data.

At run time `fomc truth`, `fomc study`, `fomc dips`, `fomc backtest` and the scorer's
SPY/TLT confirmation signal fetch daily history from Yahoo Finance through the
`yfinance` library (`auto_adjust=False`, raw close) into `data/market/`, which is
git-ignored. Users are responsible for complying with Yahoo's terms of service. Because
the cache is refetched, tables that depend on recent prices can change in their newest
rows when regenerated on a later date.

## 6. Regime-intelligence news feed

`apps/fomc-dashboard/public/data/regime_intel/` (`latest.json`, `history/*.json`,
`sources.jsonl`, `latest_raw.json`) is produced by `scripts/collect_regime_intel.py`
calling the Perplexity API (`sonar` model) with twelve search prompts across four
buckets, then scored by `scripts/score_regime_intel.py`.

What is stored per source: `title`, `url`, `publisher`, `published_at`, machine-assigned
`bucket`, `direction`, `score`, `importance`, `confidence`, `claim_type`, `event_key`,
an `official` flag, feed bookkeeping (`collected_at`, `first_seen_at`, `is_new`), and
two short generated fields, `evidence_text` and `why_it_matters`.

What is not stored: article bodies, excerpts, or any publisher text beyond the title.
Titles and publisher names appear for citation and remain the property of their
publishers.

### The collector's evidence contract

The collector's prompt (see `JSON_CONTRACT` in `scripts/collect_regime_intel.py`)
requires each source to conform to the `IntelSource` dataclass in
`scripts/_intel_common.py` and states, for `evidence_text`:

> one concise factual sentence IN YOUR OWN WORDS. NEVER include a direct quotation
> attributed to a named person; reconstructed quotes misattribute speech; paraphrase
> the substance instead.

It also requires a stable `event_key` per underlying release or statement so that
many outlets covering the same event cast one vote, a `claim_type` separating
documented fact and official data from sell-side scenarios and interpretation, and
prefers official primary sources (Federal Reserve, BLS, BEA, Treasury, FRED, CME) over
commentary. The normalizer (`normalize_source`) drops anything without a title and URL
and coerces every enumerated field to a valid value.

### Known limitation: machine paraphrases can misattribute

`evidence_text` and `why_it_matters` are generated by a language model from search
results. They can garble numbers, merge two articles, or attribute a statement to the
wrong speaker. A live instance was found where a mangled Powell quote from one source
was carried into the public summary for two runs. Since then:

- The scorer's `summary` cites sources only as `per <publisher>: <title>` and never
  emits `evidence_text` (`_exemplar` in `score_regime_intel.py`).
- The scorer refuses any title containing an attributed-quote span
  (`contains_attributed_quote`), because scoring cannot verify quotes against the
  primary source.
- Only `direction` votes; the model's -2..+2 `score` is reported but not averaged,
  because magnitude is the least stable thing the model produces run to run.

Treat `evidence_text` as an unverified lead, not evidence. If a claim matters, open
the `url` and read the primary document. To dispute a source, open a `[source]` Issue
with the primary-source link.

## 7. Derived tables

Everything under `data/fomc/analysis/` and `apps/fomc-dashboard/public/data/` is
generated by a command in this repository from the sources above (see
`data/fomc/analysis/README.md` for the command per file). They are Elendil Labs
works licensed CC BY 4.0. Do not hand-edit them; regenerate them.

## 8. Secrets and services

The pipeline uses two third-party services with keys: Perplexity
(`PPLX_API_KEY_fomc`) and FRED (`FRED_API_KEY`). Keys live in a git-ignored `.env`
locally and in repository secrets in CI. No key, token or account identifier is
committed. Both scripts degrade to a clearly flagged state (`stale: true` or
`available: false`) rather than failing when a key is absent.
