import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DailyLog } from "../DailyLog";
import type { TrendPoint } from "../TrendChart";

const points: TrendPoint[] = [
  { date: "2026-06-24", net_lean: 0.23, inferred_regime: "Potential pivot → tightening", conviction: "Moderate", new_this_run: 9 },
  { date: "2026-06-25", net_lean: 0.4, inferred_regime: "Potential pivot → tightening", conviction: "High", new_this_run: 13 },
];

describe("DailyLog", () => {
  it("renders a row per point, newest first", () => {
    render(<DailyLog points={points} />);
    const bodyRows = screen.getAllByRole("row").slice(1); // drop header
    expect(bodyRows).toHaveLength(2);
    // newest (06-25) on top
    expect(within(bodyRows[0]).getByText(/Jun 25/)).toBeInTheDocument();
    expect(within(bodyRows[0]).getByText("High")).toBeInTheDocument();
    expect(within(bodyRows[0]).getByText("+0.40")).toBeInTheDocument();
  });

  it("falls back to dashes for points missing conviction/new", () => {
    render(<DailyLog points={[{ date: "2026-06-23", net_lean: 0.1 }]} />);
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("renders nothing for an empty series", () => {
    const { container } = render(<DailyLog points={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
