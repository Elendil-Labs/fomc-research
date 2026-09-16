// Regime-intelligence display helpers. The Python scorer is the canonical producer of
// the descriptor, shares, and net lean; these helpers only map those to UI labels/colors.

import type { Bucket, ClaimType, Direction } from "../types";

/** Color for the 4-state regime descriptor. */
export function descriptorColor(label: string): string {
  if (label.startsWith("Potential pivot → tightening")) return "#f59e0b"; // amber: drifting hawkish
  if (label.startsWith("Potential pivot → easing")) return "#3b82f6"; // blue: drifting dovish
  if (label === "Tightening") return "#ef4444";
  if (label === "Easing") return "#22c55e";
  return "#94a3b8"; // Mixed / unknown
}

/** Color for a net-lean value in [-1, 1] (negative = easing, positive = tightening). */
export function netLeanColor(net: number): string {
  if (net <= -0.25) return "#22c55e";
  if (net < 0.25) return "#94a3b8";
  if (net < 0.6) return "#f59e0b";
  return "#ef4444";
}

/** Color for a bucket's dominant direction. */
export function leanColor(dominant: Direction): string {
  return DIRECTION_META[dominant].color;
}

export const BUCKET_META: Record<Bucket, { label: string; short: string }> = {
  employment: { label: "Employment", short: "Jobs" },
  inflation: { label: "Inflation", short: "Prices" },
  fed_communications: { label: "Fed communications", short: "Fed" },
  market_pricing: { label: "Market pricing", short: "Markets" },
  other: { label: "Other", short: "Other" },
};

export const DIRECTION_META: Record<Direction, { label: string; color: string }> = {
  easing: { label: "Easing", color: "#22c55e" },
  neutral: { label: "Neutral", color: "#94a3b8" },
  tightening: { label: "Tightening", color: "#ef4444" },
};

/** Evidentiary-tier badge labels + colors (documented fact → interpretation). */
export const CLAIM_TYPE_META: Record<ClaimType, { label: string; color: string }> = {
  documented_fact: { label: "fact", color: "#22c55e" },
  official_data: { label: "official data", color: "#5b9dff" },
  sell_side_scenario: { label: "scenario", color: "#f59e0b" },
  interpretation: { label: "interpretation", color: "#94a3b8" },
};

/** Format a 0..1 share as a whole percent. */
export function pctShare(v: number): string {
  return `${Math.round(v * 100)}%`;
}
