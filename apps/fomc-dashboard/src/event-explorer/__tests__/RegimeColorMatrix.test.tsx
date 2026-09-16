import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import type { FomcEvent } from "../../types";
import { cellStats, RegimeColorMatrix } from "../RegimeColorMatrix";

function ev(p: Partial<FomcEvent>): FomcEvent {
  return {
    date: "2024-01-01", chair: "Powell", regime: "Easing", action: "Hold", ff_target: "x",
    emergency: false, spy_close: 100, spy_pre5: 0, spy_d0: 1, spy_p1: 0, spy_p2: 0, spy_p3: 0,
    spy_p5: 0, spy_p10: 0, tlt_close: 90, tlt_pre5: 0, tlt_d0: 1, tlt_p1: 0, tlt_p2: 0, tlt_p3: 0,
    tlt_p5: 0, tlt_p10: 0, ...p,
  };
}

describe("cellStats", () => {
  it("averages forward windows and counts, ignoring nulls", () => {
    const events = [
      ev({ spy_p5: 1, spy_p10: 2, tlt_p5: -1 }),
      ev({ spy_p5: 3, spy_p10: 4, tlt_p5: null }), // null TLT excluded from its mean
    ];
    const s = cellStats(events);
    expect(s.n).toBe(2);
    expect(s.spyP5).toBe(2);
    expect(s.spyP10).toBe(3);
    expect(s.tltP5).toBe(-1);
  });

  it("returns nulls for an empty bucket", () => {
    const s = cellStats([]);
    expect(s).toEqual({ n: 0, spyP5: null, spyP10: null, tltP5: null });
  });
});

describe("RegimeColorMatrix", () => {
  // Two green (SPY↑ TLT↑) Easing events -> one cell shows count 2 and the SPY +5d/+10d means.
  const events = [
    ev({ regime: "Easing", spy_d0: 1, tlt_d0: 1, spy_p5: 0.42, spy_p10: 0.55, tlt_p5: -1.73 }),
    ev({ regime: "Easing", spy_d0: 1, tlt_d0: 1, spy_p5: 0.42, spy_p10: 0.55, tlt_p5: -1.73 }),
    ev({ regime: "Tightening", spy_d0: -1, tlt_d0: -1, spy_p5: 0.1, spy_p10: 0.2, tlt_p5: 0 }),
  ];

  it("renders forward stats inside the green Easing cell", () => {
    render(<RegimeColorMatrix events={events} />);
    // appears in both the Easing×Green cell and the Column-total cell (all greens are Easing)
    expect(screen.getAllByText("SPY +0.42% / +0.55%").length).toBe(2);
    expect(screen.getAllByText("TLT +5d -1.73%").length).toBe(2);
  });

  it("renders a Column total row", () => {
    render(<RegimeColorMatrix events={events} />);
    expect(screen.getByText("Column total")).toBeInTheDocument();
  });
});
