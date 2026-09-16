import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { BalanceSheetDoc, RegimeIntelDocument } from "../../types";
import { RegimeQuadrant } from "../RegimeQuadrant";

function doc(p: Partial<RegimeIntelDocument>): RegimeIntelDocument {
  return {
    generated_at: "2026-06-26T13:00:00Z",
    window_start: "2026-06-17",
    window_end: "2026-06-26",
    current_repo_regime: "Easing",
    inferred_regime: "Potential pivot → tightening",
    conviction: "High",
    evidence_shares: { easing: 0.1, neutral: 0.2, tightening: 0.7 },
    net_lean: 0.49,
    evidence_dir: "tightening",
    bucket_scores: {} as RegimeIntelDocument["bucket_scores"],
    summary: "",
    what_would_change_the_call: [],
    sources: [],
    ...p,
  };
}

const bsTight: BalanceSheetDoc = {
  generated_at: "2026-06-26T13:00:00Z",
  net_lean: 0.4,
  label: "tightening",
  indicators: [
    { id: "WALCL", name: "Fed balance sheet", unit: "$M", weight: 0.28, latest: 6735645,
      signal: 1, detail: "Δ90d -40,000 $M", note: "shrinking (QT)" },
  ],
  method: "m",
  source: "FRED",
};

describe("RegimeQuadrant", () => {
  it("flags divergence when Fed is easing but the balance sheet is tightening", () => {
    render(<RegimeQuadrant doc={doc({ current_repo_regime: "Easing" })} bs={bsTight} />);
    expect(screen.getByText(/Divergence/)).toBeInTheDocument();
    expect(screen.getByText(/Fed balance sheet/)).toBeInTheDocument();
  });

  it("does NOT flag divergence when both point the same way", () => {
    render(
      <RegimeQuadrant
        doc={doc({ current_repo_regime: "Tightening" })}
        bs={bsTight}
      />,
    );
    expect(screen.queryByText(/Divergence/)).not.toBeInTheDocument();
  });

  it("renders without balance-sheet data (axis not produced yet)", () => {
    render(<RegimeQuadrant doc={doc({})} bs={null} />);
    expect(screen.getByText("Fed's stated regime")).toBeInTheDocument();
    expect(screen.queryByText(/Divergence/)).not.toBeInTheDocument();
  });
});
