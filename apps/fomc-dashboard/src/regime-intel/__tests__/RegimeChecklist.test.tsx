import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { ChecklistItem, SpyTltSignal } from "../../types";
import { RegimeChecklist } from "../RegimeChecklist";

const items: ChecklistItem[] = [
  { id: "inflation_upside", text: "Inflation data surprises to the upside", status: "confirmed" },
  {
    id: "spytlt_confirms",
    text: "SPY/TLT color and rate-market behavior confirm the macro read",
    status: "partial",
  },
];

const spytlt: SpyTltSignal = {
  window_days: 10,
  spy_ret: 0.0281,
  tlt_ret: -0.033,
  as_of: "2026-07-10",
  status: "partial",
};

describe("RegimeChecklist", () => {
  it("shows the SPY/TLT evidence caption on the spytlt_confirms item", () => {
    render(<RegimeChecklist items={items} spytlt={spytlt} />);
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.getByText(/SPY \+2\.8% \/ TLT -3\.3% over 10d/)).toBeInTheDocument();
  });

  it("renders without a caption when the price signal is missing", () => {
    render(<RegimeChecklist items={items} spytlt={null} />);
    expect(screen.queryByText(/over 10d/)).not.toBeInTheDocument();
  });
});
