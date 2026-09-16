// Color-day classification — the empirical heart of the Event Explorer.
//
// A "color day" summarizes the joint SPY/TLT reaction on the FOMC decision day (d0):
//   Green  = SPY d0 >= 0 and TLT d0 >= 0   (SPY↑ TLT↑) — risk-on, rates rally together
//   Orange = SPY d0 >= 0 and TLT d0 <  0   (SPY↑ TLT↓) — stocks up, bonds down
//   Blue   = SPY d0 <  0 and TLT d0 >= 0   (SPY↓ TLT↑) — flight to bonds
//   Red    = SPY d0 <  0 and TLT d0 <  0   (SPY↓ TLT↓) — broad de-risking
//
// Zero counts as "up" (>= 0), matching the truth-table convention.

import type { FomcEvent } from "../types";

export type ColorDay = "green" | "orange" | "blue" | "red";

export interface ColorInfo {
  color: ColorDay;
  label: string; // e.g. "SPY↑ TLT↑"
  hex: string;
}

export const COLOR_META: Record<ColorDay, { label: string; hex: string; name: string }> = {
  green: { label: "SPY↑ TLT↑", hex: "#22c55e", name: "Green" },
  orange: { label: "SPY↑ TLT↓", hex: "#f59e0b", name: "Orange" },
  blue: { label: "SPY↓ TLT↑", hex: "#3b82f6", name: "Blue" },
  red: { label: "SPY↓ TLT↓", hex: "#ef4444", name: "Red" },
};

/** Classify from raw d0 returns. Returns null when either leg is missing. */
export function classifyColor(spyD0: number | null, tltD0: number | null): ColorDay | null {
  if (spyD0 === null || tltD0 === null) return null;
  const spyUp = spyD0 >= 0;
  const tltUp = tltD0 >= 0;
  if (spyUp && tltUp) return "green";
  if (spyUp && !tltUp) return "orange";
  if (!spyUp && tltUp) return "blue";
  return "red";
}

export function colorInfo(event: FomcEvent): ColorInfo | null {
  const color = classifyColor(event.spy_d0, event.tlt_d0);
  if (!color) return null;
  return { color, label: COLOR_META[color].label, hex: COLOR_META[color].hex };
}

export const ALL_COLORS: ColorDay[] = ["green", "orange", "blue", "red"];
