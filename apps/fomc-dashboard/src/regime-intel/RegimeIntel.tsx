import { useEffect, useState } from "react";
import type { BalanceSheetDoc, FomcEvent, MarketPricingDoc, RegimeIntelDocument } from "../types";
import { loadBalanceSheet, loadEventTruth, loadMarketPricing, loadRegimeIntel } from "../data/load";
import { Scorecard } from "./Scorecard";
import { RegimeQuadrant } from "./RegimeQuadrant";
import { MarketPricing } from "./MarketPricing";
import { BucketCards } from "./BucketCards";
import { NarrativeSummary } from "./NarrativeSummary";
import { NewsFeed } from "./NewsFeed";
import { EvidenceMatrix } from "./EvidenceMatrix";
import { RegimeChecklist } from "./RegimeChecklist";
import { TrendChart, type TrendPoint } from "./TrendChart";
import { DailyLog } from "./DailyLog";
import { PlaybookPanel } from "./PlaybookPanel";

const BASE = import.meta.env.BASE_URL || "/";
const histUrl = `${BASE.replace(/\/$/, "")}/data/regime_intel/history.json`;

function ChangeSinceYesterday({ points }: { points: TrendPoint[] }) {
  if (points.length < 2) return null;
  const cur = points[points.length - 1];
  const prev = points[points.length - 2];
  const delta = cur.net_lean - prev.net_lean;
  const dir = delta > 0.01 ? "more tightening" : delta < -0.01 ? "more easing" : "little changed";
  return (
    <p className="muted tiny" style={{ marginTop: 0 }}>
      Since the prior run the net lean moved {delta >= 0 ? "+" : ""}
      {delta.toFixed(2)} ({dir}).
      {cur.inferred_regime !== prev.inferred_regime &&
        ` Read changed: ${prev.inferred_regime} → ${cur.inferred_regime}.`}
    </p>
  );
}

export function RegimeIntel() {
  const [doc, setDoc] = useState<RegimeIntelDocument | null | undefined>(undefined);
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [bs, setBs] = useState<BalanceSheetDoc | null>(null);
  const [mp, setMp] = useState<MarketPricingDoc | null>(null);
  const [events, setEvents] = useState<FomcEvent[]>([]);

  useEffect(() => {
    loadRegimeIntel().then(setDoc);
    loadBalanceSheet().then(setBs);
    loadMarketPricing().then(setMp);
    loadEventTruth()
      .then((t) => setEvents(t.events ?? []))
      .catch(() => setEvents([]));
    fetch(histUrl, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : { points: [] }))
      .then((h) => setPoints(h.points ?? []))
      .catch(() => setPoints([]));
  }, []);

  if (doc === undefined) return <div className="loading">Loading regime intelligence…</div>;

  if (doc === null) {
    return (
      <div className="empty-state panel">
        <h2>No regime intelligence yet</h2>
        <p>
          The intelligence pipeline has not produced a snapshot. Run{" "}
          <code>python scripts/collect_regime_intel.py</code> then{" "}
          <code>python scripts/score_regime_intel.py</code> (with <code>PPLX_API_KEY</code> set), or
          wait for the scheduled GitHub Action to publish <code>latest.json</code>.
        </p>
      </div>
    );
  }

  return (
    <div>
      {doc.stale && (
        <div className="stale-banner">
          ⚠ Showing the previous snapshot — the latest refresh failed.
          {doc.error_summary ? ` (${doc.error_summary})` : ""}
        </div>
      )}

      <p className="muted tiny" style={{ marginTop: 0 }}>
        Since the last FOMC meeting, is incoming evidence consistent with the current regime, or
        pointing toward a regime change? Evidence-weighted read — not a prediction.
      </p>
      <ChangeSinceYesterday points={points} />

      <Scorecard doc={doc} />

      <div className="section-title">Two-axis regime map</div>
      <RegimeQuadrant doc={doc} bs={bs} />

      <div className="section-title">Market-priced Fed path</div>
      <MarketPricing doc={mp} />

      <div className="section-title">Playbook — next meeting vs. history</div>
      <PlaybookPanel doc={doc} events={events} />

      <div className="section-title">Evidence buckets</div>
      <BucketCards doc={doc} />

      <div className="section-title">Narrative</div>
      <NarrativeSummary doc={doc} />

      {points.length >= 1 && (
        <>
          <div className="section-title">Daily log</div>
          <DailyLog points={points} />
        </>
      )}

      {points.length >= 2 && (
        <>
          <div className="section-title">Net evidence lean trend</div>
          <TrendChart points={points} />
        </>
      )}

      <div className="section-title">Regime-change checklist</div>
      <RegimeChecklist items={doc.checklist ?? []} spytlt={doc.spytlt} />

      <div className="section-title">News &amp; source feed</div>
      <NewsFeed sources={doc.sources} />

      <div className="section-title">Evidence matrix</div>
      <EvidenceMatrix sources={doc.sources} />
    </div>
  );
}
