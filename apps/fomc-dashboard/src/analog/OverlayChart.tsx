import { useRef, useState } from "react";
import type { AnalogPoint } from "../types";

// Dependency-free inline SVG overlay: SPY % from peak, 2026 path on top of the 2018 path,
// x = trading days from the peak. Series colors are literal hex values validated for the
// dark panel surface; every piece of text uses the theme's text tokens, never a series color.

export const COLOR_2026 = "#3987e5";
export const COLOR_2018 = "#d95926";

const X_MAX = 72;
const Y_HI = 2;
const Y_LO = -22;

/**
 * Selective 2018 annotations: the turns a reader needs to find on the orange line. Keyed by
 * date (the copy names dates), with the label placed where it clears both lines.
 */
const EVENTS_2018: { date: string; label: string; dx: number; dy: number; anchor: "start" | "middle" | "end" }[] = [
  { date: "2018-10-11", label: "200-day break", dx: -9, dy: 4, anchor: "end" },
  { date: "2018-10-29", label: "-10% low", dx: 0, dy: 16, anchor: "middle" },
  { date: "2018-11-07", label: "reclaims 200-day, fails", dx: 7, dy: -6, anchor: "start" },
  { date: "2018-12-19", label: "Dec 19 hike", dx: -9, dy: 4, anchor: "end" },
  { date: "2018-12-24", label: "-20% low", dx: 0, dy: 16, anchor: "middle" },
];

/** 2026 calendar, in trading days from the October 6 peak. */
const MARKERS_2026: { t: number; label: string }[] = [
  { t: 45, label: "Dec 9 FOMC" },
  { t: 47, label: "CR expiry" },
  { t: 48, label: "Cook hearing" },
];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2019-01-04" -> "Jan 4" (no Date parsing: avoids timezone drift). */
export function monthDay(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${MONTHS[m - 1]} ${d}`;
}

export function pctLabel(v: number): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

/** Direct end label for the 2026 line, computed from the last point of the series. */
export function endLabel2026(last: AnalogPoint): string {
  return `2026: day ${last.t}, ${pctLabel(last.spy)}`;
}

export function endLabel2018(p: AnalogPoint): string {
  return `2018: ${monthDay(p.date)} 'patient', ${pctLabel(p.spy)}`;
}

interface Props {
  s2018: AnalogPoint[];
  s2026: AnalogPoint[];
}

export function OverlayChart({ s2018, s2026 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoverT, setHoverT] = useState<number | null>(null);

  const W = 820;
  const H = 400;
  const pad = { l: 44, r: 190, t: 36, b: 34 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;

  const x = (t: number) => pad.l + (Math.max(0, Math.min(X_MAX, t)) / X_MAX) * innerW;
  const y = (v: number) => {
    const c = Math.max(Y_LO, Math.min(Y_HI, v));
    return pad.t + (1 - (c - Y_LO) / (Y_HI - Y_LO)) * innerH;
  };

  const path18 = s2018.filter((p) => p.t <= X_MAX);
  const path26 = s2026.filter((p) => p.t <= X_MAX);
  if (path18.length < 2 || path26.length < 1) {
    return <div className="empty-state tiny">Not enough analog history to draw the overlay.</div>;
  }
  const line = (pts: AnalogPoint[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.t).toFixed(1)},${y(p.spy).toFixed(1)}`).join(" ");

  const last26 = path26[path26.length - 1];
  const last18 = path18[path18.length - 1];
  const by18 = new Map(path18.map((p) => [p.t, p]));
  const by26 = new Map(path26.map((p) => [p.t, p]));
  const byDate18 = new Map(path18.map((p) => [p.date, p]));
  // The 2026 end label floats above the marker (the 2018 line owns the band beside it);
  // a hairline leader ties the two together.
  const label26Y = Math.min(y(last26.spy) - 30, y(-2.0));

  const yTicks = [0, -5, -10, -15, -20];
  const xTicks = [0, 10, 20, 30, 40, 50, 60, 70];

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const el = svgRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    if (r.width === 0) return;
    const px = ((e.clientX - r.left) / r.width) * W;
    const t = Math.round(((px - pad.l) / innerW) * X_MAX);
    setHoverT(t < 0 || t > X_MAX ? null : t);
  };

  const hover = hoverT === null ? null : { t: hoverT, p18: by18.get(hoverT), p26: by26.get(hoverT) };
  const tipLines: string[] = [];
  if (hover) {
    tipLines.push(`Day ${hover.t} from peak`);
    if (hover.p18) {
      tipLines.push(`2018  ${pctLabel(hover.p18.spy)}  ${monthDay(hover.p18.date)}`);
      if (hover.p18.event) tipLines.push(`  ${hover.p18.event}`);
    }
    if (hover.p26) {
      tipLines.push(`2026  ${pctLabel(hover.p26.spy)}  ${monthDay(hover.p26.date)}`);
      if (hover.p26.event) tipLines.push(`  ${hover.p26.event}`);
    }
  }
  const tipW = 200;
  const tipH = 14 * tipLines.length + 12;
  const tipX = hover ? (x(hover.t) + 12 + tipW > W - pad.r + 40 ? x(hover.t) - 12 - tipW : x(hover.t) + 12) : 0;
  const tipY = pad.t + 8;

  return (
    <div className="panel analog-chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width="100%"
        role="img"
        aria-label="SPY percent from peak, 2026 overlaid on 2018, trading days from the peak"
        onMouseMove={onMove}
        onMouseLeave={() => setHoverT(null)}
      >
        {/* gridlines */}
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--border)"
              strokeWidth={v === 0 ? 1.5 : 1}
            />
            <text x={pad.l - 8} y={y(v) + 3.5} fill="var(--muted)" fontSize="11" textAnchor="end">
              {v === 0 ? "0" : `${v}%`}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <g key={`x${t}`}>
            <line x1={x(t)} x2={x(t)} y1={pad.t} y2={H - pad.b} stroke="var(--border)" strokeWidth={1} />
            <text x={x(t)} y={H - pad.b + 16} fill="var(--muted)" fontSize="11" textAnchor="middle">
              {t}
            </text>
          </g>
        ))}
        <text x={pad.l + innerW / 2} y={H - 4} fill="var(--muted)" fontSize="11" textAnchor="middle">
          trading days from the peak
        </text>
        <text
          x={12}
          y={pad.t + innerH / 2}
          fill="var(--muted)"
          fontSize="11"
          textAnchor="middle"
          transform={`rotate(-90 12 ${pad.t + innerH / 2})`}
        >
          SPY, % from peak
        </text>

        {/* 2026 calendar markers (days from the Oct 6 peak), labeled once at the top */}
        {MARKERS_2026.map((m) => (
          <line
            key={m.t}
            x1={x(m.t)}
            x2={x(m.t)}
            y1={pad.t}
            y2={H - pad.b}
            stroke="var(--muted-2)"
            strokeOpacity={0.55}
            strokeDasharray="2 4"
          />
        ))}
        <text x={x(MARKERS_2026[0].t)} y={pad.t - 8} fill="var(--muted)" fontSize="10.5" textAnchor="middle">
          {`2026: ${MARKERS_2026.map((m) => `${m.label} (day ${m.t})`).join(" · ")}`}
        </text>

        {/* series */}
        <path d={line(path18)} fill="none" stroke={COLOR_2018} strokeWidth={2} strokeLinejoin="round" />
        <path d={line(path26)} fill="none" stroke={COLOR_2026} strokeWidth={2.5} strokeLinejoin="round" />

        {/* 2018 event dots */}
        {EVENTS_2018.map((ev) => {
          const p = byDate18.get(ev.date);
          if (!p) return null;
          return (
            <g key={ev.date}>
              <circle cx={x(p.t)} cy={y(p.spy)} r={4} fill={COLOR_2018} stroke="var(--panel)" strokeWidth={1.5} />
              <text
                x={x(p.t) + ev.dx}
                y={y(p.spy) + ev.dy}
                fill="var(--muted)"
                fontSize="10.5"
                textAnchor={ev.anchor}
              >
                {ev.label}
              </text>
            </g>
          );
        })}

        {/* end markers + direct labels */}
        <circle cx={x(last18.t)} cy={y(last18.spy)} r={6} fill={COLOR_2018} stroke="var(--panel)" strokeWidth={2} />
        <text x={x(last18.t) + 10} y={y(last18.spy) + 4} fill="var(--text)" fontSize="12" fontWeight={600}>
          {endLabel2018(last18)}
        </text>
        <line
          x1={x(last26.t)}
          x2={x(last26.t)}
          y1={y(last26.spy) - 7}
          y2={label26Y + 2}
          stroke="var(--muted-2)"
          strokeWidth={1}
        />
        <circle cx={x(last26.t)} cy={y(last26.spy)} r={6} fill={COLOR_2026} stroke="var(--panel)" strokeWidth={2} />
        <text x={x(last26.t) + 8} y={label26Y} fill="var(--text)" fontSize="12" fontWeight={600}>
          {endLabel2026(last26)}
        </text>

        {/* legend (bottom-left: both lines start at 0% in the top-left corner) */}
        <g transform={`translate(${pad.l + 10}, ${H - pad.b - 26})`} fontSize="11.5">
          <line x1={0} x2={22} y1={0} y2={0} stroke={COLOR_2026} strokeWidth={2.5} />
          <text x={28} y={4} fill="var(--text)">2026, from Oct 6</text>
          <line x1={0} x2={22} y1={18} y2={18} stroke={COLOR_2018} strokeWidth={2} />
          <text x={28} y={22} fill="var(--text)">2018, from Sep 20</text>
        </g>

        {/* hover layer */}
        {hover && (
          <g pointerEvents="none">
            <line x1={x(hover.t)} x2={x(hover.t)} y1={pad.t} y2={H - pad.b} stroke="var(--muted)" strokeWidth={1} />
            {hover.p18 && (
              <circle cx={x(hover.t)} cy={y(hover.p18.spy)} r={4.5} fill={COLOR_2018} stroke="var(--panel)" strokeWidth={2} />
            )}
            {hover.p26 && (
              <circle cx={x(hover.t)} cy={y(hover.p26.spy)} r={4.5} fill={COLOR_2026} stroke="var(--panel)" strokeWidth={2} />
            )}
            <rect x={tipX} y={tipY} width={tipW} height={tipH} rx={6} fill="var(--panel-2)" stroke="var(--border)" />
            {tipLines.map((ln, i) => (
              <text
                key={i}
                x={tipX + 10}
                y={tipY + 16 + i * 14}
                fill={i === 0 ? "var(--text)" : "var(--muted)"}
                fontSize="11"
                fontWeight={i === 0 ? 600 : 400}
                style={{ whiteSpace: "pre" }}
              >
                {ln}
              </text>
            ))}
          </g>
        )}
      </svg>
    </div>
  );
}
