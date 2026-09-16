// Pure conditional-stats helpers for the Playbook panel: "given the current stated
// regime, what historically happened around FOMC decisions like the next one?"
// Historical conditional evidence only — not a forecast, not investment advice.

import type { FomcEvent } from "../types";

/** Return windows shown in the playbook grid, in display order. */
export const PLAYBOOK_WINDOWS = ["d0", "p1", "p3", "p5", "p10"] as const;
export type PlaybookWindow = (typeof PLAYBOOK_WINDOWS)[number];

export type PlaybookAsset = "spy" | "tlt";

/** Numeric return column of a FomcEvent, e.g. "spy_p5". */
export type ReturnKey = `${PlaybookAsset}_${PlaybookWindow}`;

export interface ConditionOptions {
  regime: string;
  action?: string;
}

/**
 * Filter events to the conditioning set: same regime (empty/missing regime is
 * treated as "Unknown"), optionally same action, and NEVER emergency meetings —
 * unscheduled decisions are a different animal and would pollute the base rates.
 */
export function conditionEvents(events: FomcEvent[], opts: ConditionOptions): FomcEvent[] {
  const wantRegime = opts.regime || "Unknown";
  return events.filter((e) => {
    if (e.emergency) return false;
    if ((e.regime || "Unknown") !== wantRegime) return false;
    if (opts.action && e.action !== opts.action) return false;
    return true;
  });
}

export interface WindowStats {
  n: number;
  mean: number | null;
  median: number | null;
  /** Share of observations > 0, in [0, 1]. Null when n = 0. */
  winRate: number | null;
}

function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

/** Null-safe summary stats over one return column. */
export function windowStats(events: FomcEvent[], key: ReturnKey): WindowStats {
  const vals: number[] = [];
  for (const e of events) {
    const v = e[key];
    if (typeof v === "number" && !Number.isNaN(v)) vals.push(v);
  }
  const n = vals.length;
  if (n === 0) return { n: 0, mean: null, median: null, winRate: null };

  const mean = round2(vals.reduce((a, b) => a + b, 0) / n);
  const sorted = [...vals].sort((a, b) => a - b);
  const mid = Math.floor(n / 2);
  const median = round2(n % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2);
  const winRate = vals.filter((v) => v > 0).length / n;
  return { n, mean, median, winRate };
}

export type PlaybookGrid = Record<PlaybookAsset, Record<PlaybookWindow, WindowStats>>;

/** Full SPY/TLT × window stats grid for an (already conditioned) event set. */
export function playbookTable(events: FomcEvent[]): PlaybookGrid {
  const build = (asset: PlaybookAsset): Record<PlaybookWindow, WindowStats> => {
    const row = {} as Record<PlaybookWindow, WindowStats>;
    for (const w of PLAYBOOK_WINDOWS) {
      row[w] = windowStats(events, `${asset}_${w}` as ReturnKey);
    }
    return row;
  };
  return { spy: build("spy"), tlt: build("tlt") };
}
