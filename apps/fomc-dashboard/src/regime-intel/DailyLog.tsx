import type { TrendPoint } from "./TrendChart";
import { descriptorColor, netLeanColor } from "../lib/regime";
import { shortDate } from "../lib/format";

/** Compact one-row-per-refresh log: how the read evolved day to day. Newest first. */
export function DailyLog({ points }: { points: TrendPoint[] }) {
  if (!points.length) return null;
  const rows = [...points].reverse();
  return (
    <div className="table-wrap panel" style={{ padding: 6 }}>
      <table className="daily-log">
        <thead>
          <tr>
            <th className="left">Date</th>
            <th className="left">Regime read</th>
            <th>Net lean</th>
            <th className="left">Conviction</th>
            <th>New</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.date}>
              <td className="left">{shortDate(p.date)}</td>
              <td className="left" style={{ color: descriptorColor(p.inferred_regime ?? "") }}>
                {p.inferred_regime ?? "—"}
              </td>
              <td style={{ color: netLeanColor(p.net_lean) }}>
                {p.net_lean >= 0 ? "+" : ""}
                {p.net_lean.toFixed(2)}
              </td>
              <td className="left">{p.conviction ?? "—"}</td>
              <td>{p.new_this_run ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
