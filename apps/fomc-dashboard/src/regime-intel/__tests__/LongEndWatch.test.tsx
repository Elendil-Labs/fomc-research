import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { AuctionDoc, CftcDoc, LongEndDoc, LongEndIndicator } from "../../types";
import {
  LongEndWatch,
  buildBoxes,
  countBoxes,
  fmtK,
  fmtValue,
  stressWithinWindow,
} from "../LongEndWatch";

// ---------- fixtures (mirror the producer schemas) ----------

const ind = (p: Partial<LongEndIndicator> & Pick<LongEndIndicator, "id" | "group">): LongEndIndicator => ({
  name: p.id,
  unit: "%",
  latest: 1,
  as_of: "2026-10-03",
  change_20d: 0,
  threshold: null,
  rule: "",
  checked: null,
  detail: "",
  note: "",
  ...p,
});

const longEnd: LongEndDoc = {
  generated_at: "2026-10-06T12:00:00Z",
  available: true,
  source: "FRED API + NY Fed ACM",
  method: "thresholds vs 2022/2023 long-end lows",
  analogs: {
    "2022-10-24": { DFII10: 1.72, ACMTP10: 0.41, MOVE: 160 },
    "2023-10-19": { DFII10: 2.5, ACMTP10: 0.48, MOVE: 135 },
  },
  summary: {
    checked: 2,
    total: 5,
    valuation_checked: 1,
    valuation_total: 3,
    timing_checked: 1,
    timing_total: 2,
    read: "valuation partially there, timing not yet",
  },
  indicators: [
    ind({ id: "DFII10", name: "10y real yield", group: "valuation", latest: 1.95, threshold: 2.0,
      rule: "≥ 2.00%", checked: false, detail: "below the 2023 low", change_20d: -0.1 }),
    ind({ id: "ACMTP10", name: "10y term premium", group: "valuation", latest: 0.62, threshold: 0.5,
      rule: "≥ 0.50%", checked: true, detail: "term premium rebuilt", change_20d: 0.05 }),
    ind({ id: "T10YIE", name: "10y breakeven", group: "valuation", latest: 2.31, threshold: 2.5,
      rule: "≤ 2.50%", checked: true, detail: "inflation comp contained" }),
    ind({ id: "MOVE", name: "MOVE index", group: "timing", unit: "index", latest: 118, threshold: 130,
      rule: "spike ≥ 130 then fade", checked: false, detail: "no vol spike" }),
    ind({ id: "TWO_YEAR_STALL", name: "2y yield stalled", group: "timing", unit: "wks", latest: null,
      rule: "2y flat 8 wks", checked: null, detail: "unavailable" }),
    ind({ id: "DGS10", name: "10y", group: "context", latest: 4.12, as_of: "2026-10-03" }),
    ind({ id: "DGS30", name: "30y", group: "context", latest: 4.71, as_of: "2026-10-03" }),
    ind({ id: "T10Y2Y", name: "10y−2y", group: "context", latest: 0.55, as_of: "2026-10-03" }),
    ind({ id: "FIVE_THIRTY", name: "30y−5y", group: "context", latest: 1.02, as_of: "2026-10-03" }),
    ind({ id: "MORTGAGE30US", name: "30y mortgage", group: "context", latest: 6.25, as_of: "2026-10-02" }),
  ],
};

const auctionRow = (term: string, date: string, status: "stress" | "watch" | "ok", bc = 2.38) => ({
  cusip: `CUSIP-${term}-${date}`,
  term,
  type: term.includes("Year") ? "Bond" : "Note",
  reopening: false,
  auction_date: date,
  high_yield: 4.5,
  bid_to_cover: bc,
  bc_avg_12m: 2.41,
  indirect_pct: 65.2,
  indirect_avg_12m: 66.0,
  dealer_pct: 14.1,
  dealer_avg_12m: 13.0,
  tail_bp: null,
  flags: status === "ok" ? [] : ["bid_to_cover_low"],
  status,
});

const auctions: AuctionDoc = {
  generated_at: "2026-10-06T12:00:00Z",
  available: true,
  source: "TreasuryDirect auction API",
  method: "b/c, indirect, dealer share vs 12m averages",
  note_on_tail: "Tail vs when-issued is not published; stress is inferred from b/c and takedown.",
  auctions: [
    auctionRow("30-Year", "2026-09-11", "stress", 2.2),
    auctionRow("2-Year", "2026-09-09", "ok"),
    auctionRow("10-Year", "2026-09-10", "watch", 2.3),
    auctionRow("20-Year", "2026-08-20", "ok"),
    auctionRow("30-Year", "2026-08-13", "ok"),
    auctionRow("10-Year", "2026-08-12", "ok"),
  ],
  upcoming: [
    { term: "10-Year", auction_date: "2026-10-08", announcement_date: "2026-10-02",
      offering_amount: 39000000000, reopening: true },
  ],
  summary: {
    last_long_end_stress: "2026-09-11",
    stress_count_90d: 1,
    watch_count_90d: 1,
    next_long_end_auction: { term: "10-Year", auction_date: "2026-10-08" },
    read: "one stress auction in the window",
  },
};

const contract = (id: string, name: string, p: Partial<CftcDoc["contracts"][number]> = {}) => ({
  id,
  name,
  as_of: "2026-09-30",
  open_interest: 5_000_000,
  am_net: 2_531_400,
  am_net_change_1w: -12_000,
  am_net_change_4w: -83_900,
  lf_net: -2_100_000,
  lf_net_change_1w: 5_000,
  lf_net_change_4w: 41_250,
  dealer_net: 100_000,
  am_selling_streak_weeks: 0,
  am_stopped_selling: false,
  lf_net_26w_low: false,
  history: [{ report_date: "2026-09-30", am_net: 2_531_400, lf_net: -2_100_000 }],
  ...p,
});

const cftc: CftcDoc = {
  generated_at: "2026-10-06T12:00:00Z",
  available: true,
  source: "CFTC TFF (Financial Futures)",
  method: "asset-manager and leveraged-fund net vs 4w/26w history",
  contracts: [
    contract("TY", "10y Note", { am_selling_streak_weeks: 3 }),
    contract("US", "T-Bond", { am_stopped_selling: true, am_net_change_4w: 12_000 }),
    contract("UB", "Ultra Bond", { lf_net_26w_low: true }),
    contract("TU", "2y Note"),
  ],
  summary: {
    as_of: "2026-09-30",
    real_money_distribution: true,
    spec_capitulation: true,
    am_stopped_selling_count: 1,
    read: "real money still distributing; specs max short",
  },
};

// ---------- helpers ----------

describe("LongEndWatch helpers", () => {
  it("formats values with units and dashes", () => {
    expect(fmtValue(1.95, "%")).toBe("1.95%");
    expect(fmtValue(118, "index")).toBe("118 index");
    expect(fmtValue(2.5, "")).toBe("2.50");
    expect(fmtValue(null, "%")).toBe("—");
  });

  it("formats signed thousands", () => {
    expect(fmtK(2_531_400)).toBe("+2,531k");
    expect(fmtK(-83_900)).toBe("-84k");
    expect(fmtK(0)).toBe("0k");
    expect(fmtK(null)).toBe("—");
  });

  it("applies the 30-day auction-stress window", () => {
    expect(stressWithinWindow("2026-09-11", "2026-10-06T12:00:00Z")).toBe(true);
    expect(stressWithinWindow("2026-09-06", "2026-10-06T12:00:00Z")).toBe(true); // 30 calendar days
    expect(stressWithinWindow("2026-09-05", "2026-10-06T12:00:00Z")).toBe(false);
    expect(stressWithinWindow(null, "2026-10-06T12:00:00Z")).toBe(false);
    expect(stressWithinWindow("2026-11-01", "2026-10-06T12:00:00Z")).toBe(false); // future
  });

  it("builds boxes from producer rows plus three derived rows, excluding context", () => {
    const boxes = buildBoxes(longEnd, auctions, cftc);
    expect(boxes.map((b) => b.id)).toEqual([
      "DFII10", "ACMTP10", "T10YIE", "MOVE", "TWO_YEAR_STALL",
      "AUCTION_STRESS", "REAL_MONEY_SELLING", "SPEC_CAPITULATION",
    ]);
    const byId = Object.fromEntries(boxes.map((b) => [b.id, b]));
    expect(byId.AUCTION_STRESS.checked).toBe(true); // 2026-09-11 within 30d of 10-06
    expect(byId.REAL_MONEY_SELLING.checked).toBe(false); // still distributing
    expect(byId.SPEC_CAPITULATION.checked).toBe(true);
    expect(byId.TWO_YEAR_STALL.checked).toBeNull();
    expect(byId.DFII10.analogText).toContain("2022: 1.72%");
    expect(byId.DFII10.analogText).toContain("2023: 2.50%");
    expect(byId.T10YIE.analogText).toBeUndefined();
  });

  it("counts only boxes with a verdict and splits by group", () => {
    const counts = countBoxes(buildBoxes(longEnd, auctions, cftc));
    // valuation: DFII10 ✗, ACMTP10 ✓, T10YIE ✓ -> 2/3
    // timing: MOVE ✗, TWO_YEAR_STALL null (excluded), AUCTION ✓, REAL_MONEY ✗, SPEC ✓ -> 2/4
    expect(counts.valuation).toEqual({ checked: 2, total: 3 });
    expect(counts.timing).toEqual({ checked: 2, total: 4 });
    expect(counts).toMatchObject({ checked: 4, total: 7 });
  });

  it("drops derived boxes from the count when their doc is missing", () => {
    expect(countBoxes(buildBoxes(longEnd, null, null))).toMatchObject({ checked: 2, total: 4 });
    expect(countBoxes(buildBoxes(null, auctions, cftc))).toMatchObject({ checked: 2, total: 3 });
    const stale: AuctionDoc = {
      ...auctions,
      summary: { ...auctions.summary, last_long_end_stress: "2026-08-01" },
    };
    expect(countBoxes(buildBoxes(null, stale, null))).toMatchObject({ checked: 0, total: 1 });
  });
});

// ---------- rendering ----------

describe("LongEndWatch", () => {
  it("renders the headline count, split and summary read", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    expect(screen.getByText("Long-end watch: has TLT bottomed?")).toBeInTheDocument();
    expect(screen.getByTestId("le-count")).toHaveTextContent("4 of 7 boxes checked");
    expect(screen.getByTestId("le-split")).toHaveTextContent("valuation 2/3 · timing 2/4");
    expect(screen.getByTestId("le-split")).toHaveTextContent("valuation partially there");
  });

  it("renders every box with group chip, value, rule, mark and analogs", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    const table = screen.getByTestId("le-boxes");
    expect(within(table).getAllByRole("row")).toHaveLength(8);
    expect(within(table).getAllByText("valuation")).toHaveLength(3);
    expect(within(table).getAllByText("timing")).toHaveLength(5);
    expect(within(table).getByText("1.95%")).toBeInTheDocument();
    expect(within(table).getByText("118 index")).toBeInTheDocument();
    expect(within(table).getByText("≥ 0.50%")).toBeInTheDocument();
    expect(within(table).getAllByText("✓")).toHaveLength(4);
    expect(within(table).getAllByText("○")).toHaveLength(3);
    expect(within(table).getAllByTitle("no data")).toHaveLength(1);
    expect(within(table).getByText(/at the 2022: 160 index · 2023: 135 index lows/)).toBeInTheDocument();
    expect(within(table).getByText("Real money stopped selling")).toBeInTheDocument();
    expect(within(table).getByText("Spec capitulation")).toBeInTheDocument();
  });

  it("renders the context line as latest (as_of)", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    const ctx = screen.getByTestId("le-context");
    expect(ctx).toHaveTextContent("10y: 4.12% (Oct 3)");
    expect(ctx).toHaveTextContent("30y mortgage: 6.25% (Oct 2)");
    expect(ctx).toHaveTextContent("30y−5y: 1.02%");
  });

  it("renders the last four long-end auctions, colored by status, plus the next date", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    const strip = screen.getByTestId("le-auctions");
    const items = strip.querySelectorAll("[data-status]");
    expect(items).toHaveLength(4);
    expect(Array.from(items).map((n) => n.getAttribute("data-status"))).toEqual([
      "stress", "watch", "ok", "ok",
    ]);
    expect(strip).not.toHaveTextContent("2-Year");
    expect(strip).toHaveTextContent("30-Year Sep 11: b/c 2.20 vs avg 2.41 · indirects 65.2% · stress");
    const stressTag = within(strip).getByText("stress");
    expect(stressTag).toHaveStyle({ color: "rgb(239, 68, 68)" });
    expect(within(strip).getByText("watch")).toHaveStyle({ color: "rgb(245, 158, 11)" });
    expect(strip).toHaveTextContent("Next long-end auction: 10-Year on Oct 8, 2026");
    expect(strip).toHaveTextContent("Tail vs when-issued is not published");
  });

  it("renders positioning with k-formatted nets, 4w changes and badges", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    const strip = screen.getByTestId("le-positioning");
    expect(strip).toHaveTextContent("10y Note AM +2,531k (-84k 4w) · LF -2,100k (+41k 4w)");
    expect(within(strip).getByText("AM selling 3 wks")).toBeInTheDocument();
    expect(within(strip).getByText("AM stopped")).toBeInTheDocument();
    expect(within(strip).getByText("LF 26w low")).toBeInTheDocument();
    expect(strip).toHaveTextContent("real money still distributing; specs max short");
  });

  it("shows the footer with all three sources and the long-end stamp", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={cftc} />);
    expect(
      screen.getByText(/FRED API \+ NY Fed ACM · TreasuryDirect auction API · CFTC TFF/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Oct 6, 2026/)).toBeInTheDocument();
  });

  it("renders the placeholder when all three docs are missing", () => {
    render(<LongEndWatch longEnd={null} auctions={null} cftc={null} />);
    expect(screen.getByText(/populates on the next scheduled data run/)).toBeInTheDocument();
    expect(screen.queryByTestId("le-boxes")).not.toBeInTheDocument();
  });

  it("degrades gracefully when only the long-end doc is missing", () => {
    render(<LongEndWatch longEnd={null} auctions={auctions} cftc={cftc} />);
    expect(screen.getByTestId("le-count")).toHaveTextContent("2 of 3 boxes checked");
    expect(screen.getByTestId("le-split")).toHaveTextContent("valuation 0/0 · timing 2/3");
    expect(screen.getByText(/valuation\/timing axis pending next data run/)).toBeInTheDocument();
    expect(screen.queryByTestId("le-context")).not.toBeInTheDocument();
    expect(screen.getByTestId("le-auctions")).toBeInTheDocument();
    expect(screen.getByTestId("le-positioning")).toBeInTheDocument();
  });

  it("degrades gracefully when only the auction doc is missing", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={null} cftc={cftc} />);
    expect(screen.getByTestId("le-count")).toHaveTextContent("3 of 6 boxes checked");
    expect(screen.getByText(/Auction monitor pending next data run/)).toBeInTheDocument();
    expect(screen.queryByTestId("le-auctions")).not.toBeInTheDocument();
    const row = screen.getByTestId("le-boxes").querySelector('[data-box="AUCTION_STRESS"]');
    expect(row).toHaveAttribute("data-checked", "pending");
    expect(screen.getByText(/FRED API \+ NY Fed ACM · CFTC TFF/)).toBeInTheDocument();
  });

  it("degrades gracefully when only the CFTC doc is missing", () => {
    render(<LongEndWatch longEnd={longEnd} auctions={auctions} cftc={null} />);
    expect(screen.getByTestId("le-count")).toHaveTextContent("3 of 5 boxes checked");
    expect(screen.getByTestId("le-split")).toHaveTextContent("valuation 2/3 · timing 1/2");
    expect(screen.getByText(/CFTC positioning pending next data run/)).toBeInTheDocument();
    expect(screen.queryByTestId("le-positioning")).not.toBeInTheDocument();
    // "pending" rather than "null": jsdom's selector engine mis-matches [attr="null"].
    expect(screen.getByTestId("le-boxes").querySelectorAll('[data-checked="pending"]')).toHaveLength(3);
  });

  it("does not check the auction box when the last stress is older than 30 days", () => {
    const stale: AuctionDoc = {
      ...auctions,
      summary: { ...auctions.summary, last_long_end_stress: "2026-08-15" },
    };
    render(<LongEndWatch longEnd={longEnd} auctions={stale} cftc={cftc} />);
    expect(screen.getByTestId("le-count")).toHaveTextContent("3 of 7 boxes checked");
    const row = screen.getByTestId("le-boxes").querySelector('[data-box="AUCTION_STRESS"]');
    expect(row).toHaveAttribute("data-checked", "false");
  });
});
