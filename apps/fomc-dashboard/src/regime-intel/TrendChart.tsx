import { netLeanColor } from "../lib/regime";
import { shortDate } from "../lib/format";

export interface TrendPoint {
  date: string;
  net_lean: number; // tightening share - easing share, in [-1, 1]
  inferred_regime?: string;
  conviction?: string;
  new_this_run?: number;
}

// Dependency-free inline SVG line chart of the net evidence lean over time.
export function TrendChart({ points }: { points: TrendPoint[] }) {
  if (points.length < 2) {
    return <div className="empty-state tiny">Not enough history yet for a trend.</div>;
  }
  const W = 640;
  const H = 140;
  const pad = { l: 34, r: 12, t: 12, b: 22 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;
  const lo = -1;
  const hi = 1;

  const x = (i: number) => pad.l + (i / (points.length - 1)) * innerW;
  const y = (v: number) => {
    const clamped = Math.max(lo, Math.min(hi, v));
    return pad.t + (1 - (clamped - lo) / (hi - lo)) * innerH;
  };

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.net_lean)}`).join(" ");
  const zeroY = y(0);
  const last = points[points.length - 1];

  return (
    <div className="panel spark" style={{ padding: 12 }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Net evidence lean trend">
        {/* zero line (balanced) */}
        <line x1={pad.l} x2={W - pad.r} y1={zeroY} y2={zeroY} stroke="#33415588" strokeDasharray="3 3" />
        <text x={4} y={pad.t + 4} fill="#6b7a90" fontSize="10">tight</text>
        <text x={4} y={zeroY + 3} fill="#6b7a90" fontSize="10">0</text>
        <text x={4} y={H - pad.b + 4} fill="#6b7a90" fontSize="10">ease</text>
        {/* path */}
        <path d={line} fill="none" stroke="#5b9dff" strokeWidth={2} />
        {/* points */}
        {points.map((p, i) => (
          <circle key={p.date} cx={x(i)} cy={y(p.net_lean)} r={3} fill={netLeanColor(p.net_lean)}>
            <title>{`${shortDate(p.date)}: net lean ${p.net_lean >= 0 ? "+" : ""}${p.net_lean.toFixed(2)}`}</title>
          </circle>
        ))}
        {/* x labels: first & last */}
        <text x={pad.l} y={H - 4} fill="#6b7a90" fontSize="10">{shortDate(points[0].date)}</text>
        <text x={W - pad.r} y={H - 4} fill="#6b7a90" fontSize="10" textAnchor="end">
          {shortDate(last.date)}
        </text>
      </svg>
    </div>
  );
}
