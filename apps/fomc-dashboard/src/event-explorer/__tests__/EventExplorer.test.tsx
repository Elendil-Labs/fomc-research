import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import type { FomcEvent } from "../../types";
import { applyFilters } from "../EventExplorer";
import { emptyFilters } from "../Filters";
import { EventTable } from "../EventTable";
import { EventDrawer } from "../EventDrawer";

function ev(p: Partial<FomcEvent>): FomcEvent {
  return {
    date: "2024-01-01",
    chair: "Powell",
    regime: "Tightening",
    action: "Hold",
    ff_target: "5.25-5.50",
    emergency: false,
    spy_close: 100,
    spy_pre5: 0,
    spy_d0: 1,
    spy_p1: 1,
    spy_p2: 1,
    spy_p3: 1,
    spy_p5: 1,
    spy_p10: 1,
    tlt_close: 90,
    tlt_pre5: 0,
    tlt_d0: 1,
    tlt_p1: 1,
    tlt_p2: 1,
    tlt_p3: 1,
    tlt_p5: 1,
    tlt_p10: 1,
    ...p,
  };
}

const events: FomcEvent[] = [
  ev({ date: "2020-03-15", chair: "Powell", regime: "Easing", action: "Cut", spy_d0: -2, tlt_d0: 3 }),
  ev({ date: "2018-03-21", chair: "Powell", regime: "Tightening", action: "Hike", spy_d0: -1, tlt_d0: -1 }),
  ev({ date: "2018-01-31", chair: "Yellen", regime: "Unknown", action: "Hold", spy_d0: 0.5, tlt_d0: 0.6 }),
];

describe("applyFilters", () => {
  it("returns all when no filters set", () => {
    expect(applyFilters(events, emptyFilters())).toHaveLength(3);
  });
  it("filters by chair", () => {
    const f = { ...emptyFilters(), chairs: new Set(["Yellen"]) };
    expect(applyFilters(events, f).map((e) => e.date)).toEqual(["2018-01-31"]);
  });
  it("filters by action and regime together (AND across groups)", () => {
    const f = { ...emptyFilters(), actions: new Set(["Cut"]), regimes: new Set(["Easing"]) };
    expect(applyFilters(events, f)).toHaveLength(1);
  });
  it("filters by color day (blue = SPY down, TLT up)", () => {
    const f = { ...emptyFilters(), colors: new Set(["blue" as const]) };
    expect(applyFilters(events, f).map((e) => e.date)).toEqual(["2020-03-15"]);
  });
});

describe("EventTable", () => {
  it("renders a row per event with color label", () => {
    render(<EventTable events={events} onSelect={() => {}} />);
    expect(screen.getAllByRole("row")).toHaveLength(events.length + 1); // + header
    expect(screen.getByText("Blue")).toBeInTheDocument();
    expect(screen.getByText("Red")).toBeInTheDocument();
  });

  it("sorts by SPY d0 ascending then descending on header clicks", () => {
    render(<EventTable events={events} onSelect={() => {}} />);
    const header = screen.getByText("SPY d0");
    fireEvent.click(header); // ascending
    let bodyRows = screen.getAllByRole("row").slice(1);
    let firstDate = within(bodyRows[0]).getByText(/2020|2018/).textContent;
    expect(firstDate).toMatch(/2020/); // -2 is smallest
    fireEvent.click(header); // descending
    bodyRows = screen.getAllByRole("row").slice(1);
    firstDate = within(bodyRows[0]).getByText(/2020|2018/).textContent;
    expect(firstDate).toMatch(/2018/); // +0.5 is largest (Yellen)
  });

  it("invokes onSelect when a row is clicked", () => {
    let picked: string | null = null;
    render(<EventTable events={events} onSelect={(e) => (picked = e.date)} />);
    fireEvent.click(screen.getByText("Yellen"));
    expect(picked).toBe("2018-01-31");
  });
});

describe("EventDrawer", () => {
  it("shows em-dash for missing forward windows", () => {
    const e = ev({ spy_p10: null, tlt_p10: null });
    render(<EventDrawer event={e} onClose={() => {}} />);
    // both p10 cells render as em-dash
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("renders nothing when no event is selected", () => {
    const { container } = render(<EventDrawer event={null} onClose={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
