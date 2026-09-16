// Runtime data loaders. All data is static under public/data and fetched at runtime;
// there is no backend. Vite serves public/ at the site root, so paths are absolute.

import type {
  BalanceSheetDoc,
  EventTruthDocument,
  MarketPricingDoc,
  RegimeIntelDocument,
} from "../types";

const BASE = import.meta.env.BASE_URL || "/";

function url(path: string): string {
  return `${BASE.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(url(path), { cache: "no-cache" });
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export function loadEventTruth(): Promise<EventTruthDocument> {
  return fetchJson<EventTruthDocument>("data/fomc_event_truth.json");
}

/**
 * Regime intel may legitimately not exist yet (pipeline never run). Callers treat a
 * null result as "no intelligence data yet" and render the empty state.
 */
export async function loadRegimeIntel(): Promise<RegimeIntelDocument | null> {
  try {
    return await fetchJson<RegimeIntelDocument>("data/regime_intel/latest.json");
  } catch {
    return null;
  }
}

/**
 * Balance-sheet / liquidity axis (FRED-derived). Returns null when the axis hasn't been
 * produced or is unavailable (no FRED key / FRED outage) so the UI shows a clean
 * "axis pending" state instead of broken indicator rows.
 */
export async function loadBalanceSheet(): Promise<BalanceSheetDoc | null> {
  try {
    const doc = await fetchJson<BalanceSheetDoc>("data/regime_intel/balance_sheet.json");
    return doc.available === false ? null : doc;
  } catch {
    return null;
  }
}

/**
 * Market-pricing axis (FRED-derived): what the market prices for the Fed path. Returns
 * null when the axis hasn't been produced or is unavailable (no FRED key / FRED outage)
 * so the UI shows a clean "axis pending" state instead of broken indicator rows.
 */
export async function loadMarketPricing(): Promise<MarketPricingDoc | null> {
  try {
    const doc = await fetchJson<MarketPricingDoc>("data/regime_intel/market_pricing_axis.json");
    return doc.available === false ? null : doc;
  } catch {
    return null;
  }
}
