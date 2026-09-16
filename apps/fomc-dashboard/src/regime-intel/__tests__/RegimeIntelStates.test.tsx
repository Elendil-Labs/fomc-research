import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { RegimeIntelDocument } from "../../types";

// Mock the data loader so we can drive the orchestrator's empty/stale branches.
const loadRegimeIntel = vi.fn();
vi.mock("../../data/load", () => ({
  loadRegimeIntel: () => loadRegimeIntel(),
  loadBalanceSheet: () => Promise.resolve(null),
  loadMarketPricing: () => Promise.resolve(null),
  loadEventTruth: () => Promise.resolve({ events: [] }),
}));

import { RegimeIntel } from "../RegimeIntel";

const baseDoc: RegimeIntelDocument = {
  generated_at: "2026-06-23T11:00:00Z",
  window_start: "2026-06-17",
  window_end: "2026-06-23",
  current_repo_regime: "Easing",
  inferred_regime: "Potential pivot → tightening",
  conviction: "High",
  evidence_shares: { easing: 0.1, neutral: 0.15, tightening: 0.75 },
  net_lean: 0.65,
  evidence_dir: "tightening",
  bucket_scores: {
    employment: { shares: { easing: 0.2, neutral: 0.6, tightening: 0.2 }, net: 0, dominant: "neutral", label: "mixed", n: 2, weight_sum: 1 },
    inflation: { shares: { easing: 0.05, neutral: 0.1, tightening: 0.85 }, net: 0.8, dominant: "tightening", label: "strongly tightening", n: 3, weight_sum: 1 },
    fed_communications: { shares: { easing: 0.1, neutral: 0.2, tightening: 0.7 }, net: 0.6, dominant: "tightening", label: "leaning tightening", n: 4, weight_sum: 1 },
    market_pricing: { shares: { easing: 0.1, neutral: 0.2, tightening: 0.7 }, net: 0.6, dominant: "tightening", label: "leaning tightening", n: 2, weight_sum: 1 },
  },
  summary: "Summary text.",
  what_would_change_the_call: [],
  sources: [],
};

beforeEach(() => {
  loadRegimeIntel.mockReset();
  // history.json fetch -> empty points
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ points: [] }) })),
  );
});

describe("RegimeIntel states", () => {
  it("shows the empty state when there is no snapshot", async () => {
    loadRegimeIntel.mockResolvedValue(null);
    render(<RegimeIntel />);
    expect(await screen.findByText(/No regime intelligence yet/)).toBeInTheDocument();
  });

  it("shows the stale banner with the error summary", async () => {
    loadRegimeIntel.mockResolvedValue({
      ...baseDoc,
      stale: true,
      error_summary: "Perplexity timeout",
    });
    render(<RegimeIntel />);
    await waitFor(() => expect(screen.getByText(/previous snapshot/)).toBeInTheDocument());
    expect(screen.getByText(/Perplexity timeout/)).toBeInTheDocument();
  });

  it("renders the scorecard for a healthy snapshot", async () => {
    loadRegimeIntel.mockResolvedValue(baseDoc);
    render(<RegimeIntel />);
    expect(await screen.findByText("Potential pivot → tightening")).toBeInTheDocument();
  });
});
