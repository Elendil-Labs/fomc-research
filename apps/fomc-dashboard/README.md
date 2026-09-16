# FOMC Dashboard — Event Explorer & Regime Intelligence

A static, Vercel-ready single-page app with two views:

1. **Event Explorer** — the historical empirical layer. Browses every scheduled FOMC
   decision (2018→) and how SPY/TLT reacted on the decision day and over the following
   1/2/3/5/10 sessions. Includes a KPI header, regime/action/chair/color filters, a
   color-day timeline, a regime × color-day matrix, a sortable table, and an event
   detail drawer.
2. **Regime Intelligence** — the forward-looking evidence layer. Answers: *since the
   last FOMC meeting, is incoming evidence consistent with the current regime, or
   pointing toward a regime change?* Scorecard, four evidence buckets, an
   evidence-backed narrative, a news/source feed, an evidence matrix (JSON/CSV export),
   a regime-change checklist, and an aggregate-score trend chart.

> Evidence and regime-risk assessment only — **not investment advice**. Every
> intelligence claim links to its source.

## Color-day rule

Classified from the raw decision-day (`d0`) returns:

| Color  | Condition                         | Label     |
| ------ | --------------------------------- | --------- |
| Green  | SPY d0 ≥ 0 **and** TLT d0 ≥ 0     | SPY↑ TLT↑ |
| Orange | SPY d0 ≥ 0 **and** TLT d0 < 0     | SPY↑ TLT↓ |
| Blue   | SPY d0 < 0 **and** TLT d0 ≥ 0     | SPY↓ TLT↑ |
| Red    | SPY d0 < 0 **and** TLT d0 < 0     | SPY↓ TLT↓ |

Zero counts as "up" (≥ 0). Defined once in `src/lib/colorDay.ts` and unit-tested.

## Local development

```bash
cd apps/fomc-dashboard
npm install
npm run dev        # http://localhost:5173
npm test           # vitest (40 tests: color rule, sort, CSV, filtering, rendering)
npm run typecheck
npm run build      # tsc --noEmit && vite build -> dist/
```

There is **no backend**. All data is static under `public/data/` and fetched at
runtime, so the production build is pure static hosting.

## Data files (`public/data/`)

| File | Produced by | Notes |
| --- | --- | --- |
| `fomc_event_truth.csv` / `.json` | `fomc export-truth` | Event Explorer source; JSON is typed + null-safe |
| `regime_intel/latest.json` | `score_regime_intel.py` | What the Regime page renders |
| `regime_intel/history.json` | `score_regime_intel.py` | Compact aggregate-score series (trend chart) |
| `regime_intel/history/YYYY-MM-DD.json` | `score_regime_intel.py` | Full daily snapshots (audit) |
| `regime_intel/sources.jsonl` | `collect_regime_intel.py` | Append-only normalized source feed |
| `regime_intel/latest_raw.json` | `collect_regime_intel.py` | This run's raw collection (scorer input) |

If `regime_intel/latest.json` is missing, the Regime page renders a friendly empty
state. If the most recent refresh failed, the scorer preserves the previous snapshot
and the page shows a "stale" banner.

## Refreshing the data

From the repo root:

```bash
# 1. (occasional) rebuild the underlying price/event numbers — needs the price API
fomc truth

# 2. re-shape the canonical CSV into the dashboard's CSV+JSON (offline)
fomc export-truth

# 3. collect + score regime intelligence (needs PPLX_API_KEY_fomc)
python scripts/collect_regime_intel.py --model sonar
python scripts/score_regime_intel.py --next-fomc 2026-07-29
```

`PPLX_API_KEY_fomc` is read from the process env, then the repo-root `.env` (never committed).

## Deploying on Vercel

This app lives in a subdirectory of the larger `investment-research` repo. Configure
the Vercel project as:

- **Root directory:** `apps/fomc-dashboard`
- **Framework preset:** Vite
- **Build command:** `npm run build`
- **Output directory:** `dist`
- **Env vars:** none required at runtime (data is committed static JSON). `PPLX_API_KEY_fomc`
  belongs in **GitHub Actions** secrets, not Vercel.

A scheduled GitHub Action (`.github/workflows/refresh-dashboard.yml`, at the **repo
root** because that is the only place GitHub runs workflows) refreshes the data on
weekday mornings and on manual dispatch, commits any changes, and Vercel auto-deploys
on the resulting push.
