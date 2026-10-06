// Shared domain types for both the Event Explorer and the Regime Intelligence feed.

// ----- Event Explorer (sourced from fomc_event_truth.json) -----

export const FORWARD_HORIZONS = [1, 2, 3, 5, 10] as const;
export type Horizon = (typeof FORWARD_HORIZONS)[number];

/** One scheduled FOMC decision plus SPY/TLT reactions. Numeric cells may be null. */
export interface FomcEvent {
  date: string; // ISO yyyy-mm-dd
  chair: string;
  regime: string; // Tightening | Easing | Unknown | ...
  action: string; // Hike | Hold | Cut
  ff_target: string;
  emergency: boolean;
  spy_close: number | null;
  spy_pre5: number | null;
  spy_d0: number | null;
  spy_p1: number | null;
  spy_p2: number | null;
  spy_p3: number | null;
  spy_p5: number | null;
  spy_p10: number | null;
  tlt_close: number | null;
  tlt_pre5: number | null;
  tlt_d0: number | null;
  tlt_p1: number | null;
  tlt_p2: number | null;
  tlt_p3: number | null;
  tlt_p5: number | null;
  tlt_p10: number | null;
}

export interface EventTruthDocument {
  generated_at: string;
  source: string;
  count: number;
  first_event_date: string | null;
  latest_event_date: string | null;
  columns: string[];
  events: FomcEvent[];
}

// ----- Regime Intelligence (sourced from regime_intel/latest.json) -----

export type Bucket =
  | "employment"
  | "inflation"
  | "fed_communications"
  | "market_pricing"
  | "other";

export type Direction = "easing" | "neutral" | "tightening";
export type Importance = "low" | "medium" | "high";
export type Confidence = "low" | "medium" | "high";
/** Evidentiary tier — what KIND of claim a source is, most → least authoritative. */
export type ClaimType =
  | "documented_fact"
  | "official_data"
  | "sell_side_scenario"
  | "interpretation";
/** Capitalized display variant used for the document-level scorecard fields. */
export type ConfidenceLabel = "Low" | "Medium" | "High";

/** -2 strongly easing .. 0 mixed .. +2 strongly tightening. */
export type SourceScore = -2 | -1 | 0 | 1 | 2;

export interface IntelSource {
  id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string; // ISO timestamp
  bucket: Bucket;
  direction: Direction;
  score: SourceScore;
  importance: Importance;
  confidence: Confidence;
  /** Evidentiary tier: documented fact / official data > sell-side scenario > interpretation. */
  claim_type?: ClaimType;
  evidence_text: string;
  why_it_matters: string;
  /** True when this is an official primary source (Fed/BLS/BEA/Treasury/FRED/CME). */
  official?: boolean;
  /** True when this source first entered the feed in the most recent pipeline run. */
  is_new?: boolean;
  /** ISO timestamp of the run in which this source first appeared. */
  first_seen_at?: string;
}

/** Weighted share of evidence pointing each way (sums to ~1). */
export interface DirectionShares {
  easing: number;
  neutral: number;
  tightening: number;
}

/** Per-bucket directional read (vote-share, not an averaged magnitude). */
export interface BucketLean {
  shares: DirectionShares;
  net: number; // tightening - easing, in [-1, 1]
  dominant: Direction;
  label: string; // "leaning tightening" etc.
  n: number;
  weight_sum: number;
}

export type ConvictionLevel = "Low" | "Moderate" | "High";

// ----- Balance-sheet / liquidity axis (data-driven, from FRED) -----

export interface BalanceSheetIndicator {
  id: string;
  name: string;
  unit: string;
  weight: number;
  latest: number | null;
  as_of?: string;
  change_90d?: number;
  signal: number; // -1 loosening, 0 neutral, +1 tightening
  detail: string;
  note: string;
}

export interface BalanceSheetDoc {
  generated_at: string;
  /** False when no FRED key is set or FRED is unreachable; UI then shows "axis pending". */
  available?: boolean;
  reason?: string;
  net_lean: number; // tightening positive, -1..1
  label: string; // loosening | neutral | tightening
  indicators: BalanceSheetIndicator[];
  method?: string;
  source: string;
}

// ----- Market-pricing axis (data-driven, from FRED): what the market prices for Fed policy -----

export interface MarketPricingIndicator {
  id: string;
  name: string;
  unit: string;
  weight: number;
  latest: number | null;
  as_of?: string;
  prior_as_of?: string;
  change_90d?: number;
  signal: number; // -1 loosening, 0 neutral, +1 tightening
  detail: string;
  note: string;
}

export interface MarketPricingDoc {
  generated_at: string;
  /** False when no FRED key is set or FRED is unreachable; UI then shows "axis pending". */
  available?: boolean;
  reason?: string;
  net_lean: number; // tightening positive, -1..1, over live indicators only
  label: string; // loosening | neutral | tightening
  /** Weight share of indicators that produced data; < 1 means a degraded (renormalized) lean. */
  coverage?: number;
  indicators: MarketPricingIndicator[];
  method?: string;
  source: string;
}

export interface ChecklistItem {
  id: string;
  text: string;
  status: "confirmed" | "partial" | "not_confirmed" | "unknown";
}

/** Evidence behind the spytlt_confirms checklist item (trailing-trend heuristic). */
export interface SpyTltSignal {
  window_days: number;
  spy_ret: number; // simple return over window_days trading days, e.g. 0.0281
  tlt_ret: number;
  as_of: string;
  status: ChecklistItem["status"];
}

export interface RegimeIntelDocument {
  generated_at: string;
  window_start: string;
  window_end: string;
  current_repo_regime: string; // regime the Event Explorer says we are in
  /** 4-state descriptor: "Easing" | "Tightening" | "Potential pivot → tightening" | "→ easing". */
  inferred_regime: string;
  conviction: ConvictionLevel;
  evidence_shares: DirectionShares;
  net_lean: number; // tightening - easing share, in [-1, 1]
  evidence_dir: Direction;
  bucket_scores: Record<
    "employment" | "inflation" | "fed_communications" | "market_pricing",
    BucketLean
  >;
  summary: string;
  what_would_change_the_call: string[];
  checklist?: ChecklistItem[];
  /** Price evidence behind the spytlt_confirms item; null when the fetch failed. */
  spytlt?: SpyTltSignal | null;
  next_fomc_meeting?: string | null;
  run_id?: string;
  new_this_run?: number;
  /** Set by the pipeline when a refresh failed and we are showing the prior snapshot. */
  stale?: boolean;
  error_summary?: string | null;
  sources: IntelSource[];
}

// ----- Long-end watch (has TLT bottomed?): rates valuation/timing, auctions, CFTC positioning -----

export type LongEndGroup = "valuation" | "timing" | "context";

/** One box on the long-end checklist (FRED/ACM-derived). `checked` is null when no data. */
export interface LongEndIndicator {
  id: string;
  name: string;
  unit: string;
  group: LongEndGroup;
  latest: number | null;
  as_of?: string | null;
  change_20d: number | null;
  threshold: number | null;
  rule: string;
  checked: boolean | null;
  detail: string;
  note: string;
}

/** Values of the three valuation gauges at a historical long-end bottom (e.g. 2022-10-24). */
export interface LongEndAnalog {
  DFII10: number | null;
  ACMTP10: number | null;
  MOVE: number | null;
}

export interface LongEndSummary {
  checked: number;
  total: number;
  valuation_checked: number;
  valuation_total: number;
  timing_checked: number;
  timing_total: number;
  read: string;
}

export interface LongEndDoc {
  generated_at: string;
  /** False when the producer could not fetch its inputs; UI then shows "pending". */
  available?: boolean;
  reason?: string;
  source: string;
  method?: string;
  analogs: Record<string, LongEndAnalog>;
  summary: LongEndSummary;
  indicators: LongEndIndicator[];
}

export type AuctionStatus = "stress" | "watch" | "ok";

/** One Treasury coupon auction result vs its trailing-12-month averages. */
export interface AuctionRow {
  cusip: string;
  term: string; // "10-Year", "20-Year", "30-Year", ...
  type: string;
  reopening: boolean;
  auction_date: string; // ISO yyyy-mm-dd
  high_yield: number | null;
  bid_to_cover: number | null;
  bc_avg_12m: number | null;
  indirect_pct: number | null;
  indirect_avg_12m: number | null;
  dealer_pct: number | null;
  dealer_avg_12m: number | null;
  /** Tail vs when-issued is not published by TreasuryDirect; always null. */
  tail_bp: number | null;
  flags: string[];
  status: AuctionStatus;
}

export interface UpcomingAuction {
  term: string;
  auction_date: string;
  announcement_date?: string | null;
  offering_amount?: number | string | null;
  reopening?: boolean;
}

export interface AuctionSummary {
  last_long_end_stress: string | null;
  stress_count_90d: number;
  watch_count_90d: number;
  next_long_end_auction: { term: string; auction_date: string } | null;
  read: string;
}

export interface AuctionDoc {
  generated_at: string;
  available?: boolean;
  reason?: string;
  source: string;
  method?: string;
  note_on_tail?: string;
  /** Newest first. */
  auctions: AuctionRow[];
  upcoming: UpcomingAuction[];
  summary: AuctionSummary;
}

export interface CftcHistoryPoint {
  report_date: string;
  am_net: number | null;
  lf_net: number | null;
}

/** CFTC TFF positioning for one Treasury futures contract (net = long − short, contracts). */
export interface CftcContract {
  id: string;
  name: string;
  as_of: string;
  open_interest: number | null;
  am_net: number | null;
  am_net_change_1w: number | null;
  am_net_change_4w: number | null;
  lf_net: number | null;
  lf_net_change_1w: number | null;
  lf_net_change_4w: number | null;
  dealer_net: number | null;
  am_selling_streak_weeks: number;
  am_stopped_selling: boolean;
  lf_net_26w_low: boolean;
  history: CftcHistoryPoint[];
}

export interface CftcSummary {
  as_of: string;
  real_money_distribution: boolean;
  spec_capitulation: boolean;
  am_stopped_selling_count: number;
  read: string;
}

export interface CftcDoc {
  generated_at: string;
  available?: boolean;
  reason?: string;
  source: string;
  method?: string;
  contracts: CftcContract[];
  summary: CftcSummary;
}
