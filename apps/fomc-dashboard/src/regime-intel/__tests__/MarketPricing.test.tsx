import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { MarketPricingDoc } from "../../types";
import { MarketPricing } from "../MarketPricing";

const mpLoosening: MarketPricingDoc = {
  generated_at: "2026-07-10T13:00:00Z",
  net_lean: -0.3,
  label: "loosening",
  indicators: [
    { id: "DGS2", name: "2y Treasury yield (policy-path momentum)", unit: "%", weight: 0.3,
      latest: 3.55, change_90d: -0.25, signal: -1, detail: "Δ90d -0.25 %",
      note: "market repricing easier policy" },
    { id: "DGS2_DFF", name: "Fed-funds path (2y − funds rate)", unit: "%", weight: 0.3,
      latest: -0.45, signal: -1, detail: "-0.45%", note: "cuts priced in (2y below funds)" },
    { id: "NET_LIQUIDITY", name: "Net liquidity (WALCL − TGA − RRP)", unit: "$M", weight: 0.2,
      latest: 5_800_000, change_90d: -150_000, signal: 1, detail: "Δ90d -150 $B",
      note: "liquidity draining" },
  ],
  method: "m",
  source: "FRED API (api.stlouisfed.org)",
};

describe("MarketPricing", () => {
  it("renders the headline lean and the indicator table", () => {
    render(<MarketPricing doc={mpLoosening} />);
    expect(screen.getByText(/-0.30 \(loosening\)/)).toBeInTheDocument();
    expect(screen.getByText(/2y Treasury yield/)).toBeInTheDocument();
    expect(screen.getByText(/Fed-funds path/)).toBeInTheDocument();
  });

  it("shows the net-liquidity 90d change in $B", () => {
    render(<MarketPricing doc={mpLoosening} />);
    expect(screen.getByText("Net liquidity Δ90d")).toBeInTheDocument();
    // change_90d is -150,000 $M -> -150 $B (exact match: the table detail differs)
    expect(screen.getByText("-150 $B")).toBeInTheDocument();
  });

  it("renders the pending state when the axis has not been produced", () => {
    render(<MarketPricing doc={null} />);
    expect(screen.getByText(/populates on the next scheduled data run/)).toBeInTheDocument();
    expect(screen.queryByText(/loosening/)).not.toBeInTheDocument();
  });

  it("marks unavailable indicators with a dash, not a neutral vote", () => {
    const degraded: MarketPricingDoc = {
      ...mpLoosening,
      coverage: 0.4,
      indicators: [
        mpLoosening.indicators[0],
        { id: "T10Y2Y", name: "Curve slope (10y − 2y)", unit: "%", weight: 0.2,
          latest: null, signal: 0, detail: "unavailable", note: "unavailable" },
      ],
    };
    render(<MarketPricing doc={degraded} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("– neutral")).not.toBeInTheDocument();
    expect(screen.getByText(/Degraded read: only 40% of indicator weight/)).toBeInTheDocument();
  });
});
