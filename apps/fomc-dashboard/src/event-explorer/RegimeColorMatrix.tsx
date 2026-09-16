import type { FomcEvent } from "../types";
import { ALL_COLORS, classifyColor, COLOR_META, type ColorDay } from "../lib/colorDay";
import { pct } from "../lib/format";

// Each matrix cell summarizes the FORWARD performance of the events that landed in
// that regime × color-day bucket: how SPY/TLT traded in the sessions AFTER the color
// day (not the d0 used to classify it). Mirrors the original explorer's matrix.
export interface CellStats {
  n: number;
  spyP5: number | null; // mean SPY +5d
  spyP10: number | null; // mean SPY +10d
  tltP5: number | null; // mean TLT +5d
}

function mean(xs: Array<number | null>): number | null {
  const v = xs.filter((x): x is number => x !== null && !Number.isNaN(x));
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

/** Pure aggregation over a set of events — exported for tests. */
export function cellStats(events: FomcEvent[]): CellStats {
  return {
    n: events.length,
    spyP5: mean(events.map((e) => e.spy_p5)),
    spyP10: mean(events.map((e) => e.spy_p10)),
    tltP5: mean(events.map((e) => e.tlt_p5)),
  };
}

function CellBody({ stats }: { stats: CellStats }) {
  if (stats.n === 0) return <span className="muted">0</span>;
  return (
    <div className="cell-stats">
      <div className="cell-count">{stats.n}</div>
      <div className="tiny">
        SPY {pct(stats.spyP5)} / {pct(stats.spyP10)}
      </div>
      <div className="tiny muted">TLT +5d {pct(stats.tltP5)}</div>
    </div>
  );
}

/** regime (rows) × color-day (cols) matrix with forward SPY/TLT stats per cell. */
export function RegimeColorMatrix({ events }: { events: FomcEvent[] }) {
  const classed = events.filter((e) => classifyColor(e.spy_d0, e.tlt_d0));
  const regimes = Array.from(new Set(classed.map((e) => e.regime || "Unknown"))).sort();

  const inCell = (regime: string, color: ColorDay) =>
    classed.filter((e) => (e.regime || "Unknown") === regime && classifyColor(e.spy_d0, e.tlt_d0) === color);
  const inColumn = (color: ColorDay) => classed.filter((e) => classifyColor(e.spy_d0, e.tlt_d0) === color);

  return (
    <div className="table-wrap">
      <table className="matrix">
        <thead>
          <tr>
            <th className="rowhead">Regime \ Reaction</th>
            {ALL_COLORS.map((c) => (
              <th key={c}>
                <span className="dot" style={{ background: COLOR_META[c].hex }} />
                {COLOR_META[c].name}
                <div className="tiny muted">{COLOR_META[c].label}</div>
              </th>
            ))}
            <th>Row total</th>
          </tr>
        </thead>
        <tbody>
          {regimes.map((r) => {
            const rowEvents = classed.filter((e) => (e.regime || "Unknown") === r);
            return (
              <tr key={r}>
                <td className="rowhead">{r}</td>
                {ALL_COLORS.map((c) => (
                  <td key={c}>
                    <CellBody stats={cellStats(inCell(r, c))} />
                  </td>
                ))}
                <td className="cell-count">{rowEvents.length}</td>
              </tr>
            );
          })}
          <tr className="totals-row">
            <td className="rowhead">Column total</td>
            {ALL_COLORS.map((c) => (
              <td key={c}>
                <CellBody stats={cellStats(inColumn(c))} />
              </td>
            ))}
            <td className="cell-count">{classed.length}</td>
          </tr>
        </tbody>
      </table>
      <p className="tiny muted" style={{ marginTop: 8 }}>
        Each cell: event count · mean SPY <strong>+5d / +10d</strong> · mean TLT <strong>+5d</strong>
        — forward returns in the sessions <em>after</em> that color day (the day itself sets the
        color). Row/grand totals show counts.
      </p>
    </div>
  );
}
