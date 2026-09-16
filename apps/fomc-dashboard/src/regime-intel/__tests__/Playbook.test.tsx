import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { FomcEvent, RegimeIntelDocument } from "../../types";
import { conditionEvents, windowStats, playbookTable } from "../../lib/playbook";
import { PlaybookPanel } from "../PlaybookPanel";

function ev(p: Partial<FomcEvent>): FomcEvent {
  return {
    date: "2024-09-18",
    chair: "Powell",
    regime: "Easing",
    action: "Hold",
    ff_target: "5.25-5.50",
    emergency: false,
    spy_close: 500,
    spy_pre5: 0.5,
    spy_d0: 1,
    spy_p1: 0.5,
    spy_p2: 0.6,
    spy_p3: 0.7,
    spy_p5: 1.2,
    spy_p10: 2,
    tlt_close: 95,
    tlt_pre5: -0.2,
    tlt_d0: -0.4,
    tlt_p1: -0.1,
    tlt_p2: 0,
    tlt_p3: 0.2,
    tlt_p5: -0.6,
    tlt_p10: -1,
    ...p,
  };
}

const events: FomcEvent[] = [
  ev({ date: "2024-09-18", regime: "Easing", action: "Cut", spy_p5: 2.34 }),
  ev({ date: "2024-11-07", regime: "Easing", action: "Hold", spy_p5: -1 }),
  ev({ date: "2020-03-15", regime: "Easing", action: "Cut", emergency: true }), // excluded
  ev({ date: "2022-06-15", regime: "Tightening", action: "Hike" }),
  ev({ date: "2018-01-31", regime: "", action: "Hold" }), // empty regime -> Unknown
];

describe("conditionEvents", () => {
  it("filters by regime and excludes emergency meetings", () => {
    const out = conditionEvents(events, { regime: "Easing" });
    expect(out.map((e) => e.date)).toEqual(["2024-09-18", "2024-11-07"]);
  });

  it("optionally filters by action", () => {
    const out = conditionEvents(events, { regime: "Easing", action: "Cut" });
    expect(out.map((e) => e.date)).toEqual(["2024-09-18"]);
  });

  it("treats empty/missing regime as Unknown", () => {
    const out = conditionEvents(events, { regime: "Unknown" });
    expect(out.map((e) => e.date)).toEqual(["2018-01-31"]);
  });
});

describe("windowStats", () => {
  it("computes mean, median, and winRate over one column", () => {
    const set = [ev({ spy_p5: 2 }), ev({ spy_p5: -1 }), ev({ spy_p5: 0.5 })];
    const s = windowStats(set, "spy_p5");
    expect(s.n).toBe(3);
    expect(s.mean).toBe(0.5);
    expect(s.median).toBe(0.5);
    expect(s.winRate).toBeCloseTo(2 / 3);
  });

  it("skips null cells (null-safe)", () => {
    const set = [ev({ spy_p10: null }), ev({ spy_p10: 1 })];
    const s = windowStats(set, "spy_p10");
    expect(s.n).toBe(1);
    expect(s.mean).toBe(1);
    expect(s.winRate).toBe(1);
  });

  it("returns nulls when no observations", () => {
    expect(windowStats([], "tlt_d0")).toEqual({ n: 0, mean: null, median: null, winRate: null });
  });

  it("winRate counts only strictly positive returns", () => {
    const set = [ev({ tlt_p3: 0 }), ev({ tlt_p3: 1 }), ev({ tlt_p3: -1 })];
    expect(windowStats(set, "tlt_p3").winRate).toBeCloseTo(1 / 3);
  });
});

describe("playbookTable", () => {
  it("builds the full spy/tlt grid across all windows", () => {
    const grid = playbookTable(conditionEvents(events, { regime: "Easing" }));
    expect(Object.keys(grid.spy)).toEqual(["d0", "p1", "p3", "p5", "p10"]);
    expect(grid.spy.p5.n).toBe(2);
    expect(grid.spy.p5.mean).toBe(0.67); // (2.34 + -1) / 2
    expect(grid.tlt.d0.mean).toBe(-0.4);
  });
});

// ---------------------------------------------------------------------------

const doc: RegimeIntelDocument = {
  generated_at: "2026-07-20T11:00:00Z",
  window_start: "2026-06-17",
  window_end: "2026-07-20",
  current_repo_regime: "Easing",
  inferred_regime: "Potential pivot → tightening",
  conviction: "Moderate",
  evidence_shares: { easing: 0.2, neutral: 0.2, tightening: 0.6 },
  net_lean: 0.4,
  evidence_dir: "tightening",
  bucket_scores: {
    employment: { shares: { easing: 0.3, neutral: 0.4, tightening: 0.3 }, net: 0, dominant: "neutral", label: "mixed", n: 2, weight_sum: 1 },
    inflation: { shares: { easing: 0.1, neutral: 0.2, tightening: 0.7 }, net: 0.6, dominant: "tightening", label: "leaning tightening", n: 3, weight_sum: 1 },
    fed_communications: { shares: { easing: 0.2, neutral: 0.3, tightening: 0.5 }, net: 0.3, dominant: "tightening", label: "leaning tightening", n: 4, weight_sum: 1 },
    market_pricing: { shares: { easing: 0.2, neutral: 0.3, tightening: 0.5 }, net: 0.3, dominant: "tightening", label: "leaning tightening", n: 2, weight_sum: 1 },
  },
  summary: "Summary.",
  what_would_change_the_call: [],
  sources: [],
};

describe("PlaybookPanel", () => {
  it("renders the conditioning line and the not-investment-advice footer", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-10T12:00:00Z")} />);
    // The regime name is wrapped in <strong>, so match on the paragraph's full text.
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === "P" &&
          /Historical playbook: Easing-regime meetings since 2018 \(n=2, emergencies excluded\)/.test(
            el.textContent ?? "",
          ),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Not investment advice/)).toBeInTheDocument();
  });

  it("shows next meeting + upcoming blackout when outside the blackout window", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-10T12:00:00Z")} />);
    expect(screen.getByText("Jul 29, 2026")).toBeInTheDocument();
    expect(screen.getByText(/19 days away/)).toBeInTheDocument();
    expect(screen.getByText(/Blackout begins Jul 18, 2026/)).toBeInTheDocument();
  });

  it("shows the amber blackout badge when inside the window", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-20T12:00:00Z")} />);
    expect(screen.getByText(/Fed blackout in effect \(ends Jul 30, 2026\)/)).toBeInTheDocument();
  });

  it("shows the schedule-needs-updating note when no future meeting exists", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2027-01-05T12:00:00Z")} />);
    expect(screen.getByText(/schedule needs updating/)).toBeInTheDocument();
  });

  it("shows the pivot caveat when the inferred regime leans against the stated one", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-10T12:00:00Z")} />);
    expect(screen.getByText(/may understate transition risk/)).toBeInTheDocument();
  });

  it("hides the pivot caveat when evidence agrees with the stated regime", () => {
    render(
      <PlaybookPanel
        doc={{ ...doc, inferred_regime: "Easing" }}
        events={events}
        today={new Date("2026-07-10T12:00:00Z")}
      />,
    );
    expect(screen.queryByText(/may understate transition risk/)).not.toBeInTheDocument();
  });

  it("re-conditions the table when an action chip is selected", () => {
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-10T12:00:00Z")} />);
    // All: spy_p5 mean of (2.34, -1) = +0.67% at 50% win rate
    expect(screen.getByText("+0.67% · 50%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Cut/ }));
    // Cut only: spy_p5 = +2.34% at 100%
    expect(screen.getByText("+2.34% · 100%")).toBeInTheDocument();
  });

  it("shows per-action counts and disables empty combos (no Easing-regime hikes)", () => {
    // Sample regime is Easing: 1 Cut + 1 Hold, zero Hikes (a hike starts a Tightening regime).
    render(<PlaybookPanel doc={doc} events={events} today={new Date("2026-07-10T12:00:00Z")} />);
    const hike = screen.getByRole("button", { name: /^Hike \(0\)/ });
    expect(hike).toBeDisabled();
    expect(hike).toHaveAttribute("title", expect.stringContaining("empty by construction"));
    expect(screen.getByRole("button", { name: /^Cut \(1\)/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /^Hold \(1\)/ })).toBeEnabled();
  });
});
