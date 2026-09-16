import { useEffect, useMemo, useState } from "react";
import type { EventTruthDocument, FomcEvent } from "../types";
import { loadEventTruth } from "../data/load";
import { classifyColor } from "../lib/colorDay";
import { Filters, emptyFilters, type FilterState } from "./Filters";
import { Timeline } from "./Timeline";
import { RegimeColorMatrix } from "./RegimeColorMatrix";
import { EventTable } from "./EventTable";
import { EventDrawer } from "./EventDrawer";

/** Pure filter predicate — exported for tests. */
export function applyFilters(events: FomcEvent[], f: FilterState): FomcEvent[] {
  return events.filter((e) => {
    if (f.regimes.size && !f.regimes.has(e.regime || "Unknown")) return false;
    if (f.actions.size && !f.actions.has(e.action)) return false;
    if (f.chairs.size && !f.chairs.has(e.chair)) return false;
    if (f.colors.size) {
      const c = classifyColor(e.spy_d0, e.tlt_d0);
      if (!c || !f.colors.has(c)) return false;
    }
    return true;
  });
}

const uniq = (xs: string[]) => Array.from(new Set(xs.filter(Boolean)));

export function EventExplorer() {
  const [doc, setDoc] = useState<EventTruthDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(emptyFilters());
  const [selected, setSelected] = useState<FomcEvent | null>(null);

  useEffect(() => {
    loadEventTruth().then(setDoc).catch((e) => setError(String(e)));
  }, []);

  const events = doc?.events ?? [];
  const filtered = useMemo(() => applyFilters(events, filters), [events, filters]);

  const regimes = useMemo(() => uniq(events.map((e) => e.regime || "Unknown")).sort(), [events]);
  const actions = useMemo(() => uniq(events.map((e) => e.action)).sort(), [events]);
  const chairs = useMemo(() => uniq(events.map((e) => e.chair)).sort(), [events]);

  if (error) return <div className="empty-state">Could not load event data: {error}</div>;
  if (!doc) return <div className="loading">Loading FOMC event truth…</div>;

  return (
    <div>
      <section className="page-intro">
        <h1 className="page-headline">
          How SPY &amp; TLT trade FOMC decisions — and where rates head next
        </h1>
        <p className="page-lead">
          A summary of how SPY and TLT have reacted to every FOMC decision since 2018, and what
          those reactions have tended to imply for the days ahead. Historically, decision days that
          keep the easing cycle intact — <strong>easing green</strong> (SPY↑ TLT↑) and{" "}
          <strong>easing red</strong> (SPY↓ TLT↓) — have carried a{" "}
          <strong>positive SPY skew 5–10 sessions later</strong>, while{" "}
          <strong>easing blue</strong> (SPY↓ TLT↑) and <strong>tightening green</strong> days have
          skewed <strong>negative</strong> in the sessions immediately after. For a forward-looking
          read between meetings, the <strong>Regime Intelligence</strong> tab carries a source-linked
          news feed on employment, inflation, Fed communications, and rate pricing.
        </p>
      </section>

      <Filters
        filters={filters}
        regimes={regimes}
        actions={actions}
        chairs={chairs}
        onChange={setFilters}
      />

      <div className="section-title">Timeline</div>
      <Timeline events={filtered} onSelect={setSelected} />

      <div className="section-title">Regime × color-day matrix</div>
      <div className="panel" style={{ padding: 12 }}>
        <RegimeColorMatrix events={filtered} />
      </div>

      <div className="section-title">Events ({filtered.length})</div>
      <div className="panel" style={{ padding: 6 }}>
        <EventTable events={filtered} onSelect={setSelected} />
      </div>

      <EventDrawer event={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
