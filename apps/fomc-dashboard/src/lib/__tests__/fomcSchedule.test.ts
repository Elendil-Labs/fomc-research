import { describe, it, expect } from "vitest";
import {
  type FomcMeeting,
  decisionDates,
  nextFomc,
  nextMeeting,
  daysUntil,
  blackoutStart,
  blackoutEnd,
  inBlackout,
} from "../fomcSchedule";

const utc = (iso: string) => new Date(`${iso}T12:00:00Z`);

const SRC = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261112a.htm";

/** A meeting as exported by `fomc export-calendar`. */
function meeting(start: string, end: string, kind: "decision" | "strategy"): FomcMeeting {
  return {
    start,
    end,
    kind,
    decision_date: kind === "decision" ? end : null,
    blackout_start: blackoutStart(end),
    blackout_end: blackoutEnd(end),
    source_url: SRC,
    published: "2026-11-12",
  };
}

// A slice of the real schedule: the last 2026 decision, the 2027 run (with the
// October strategy meeting), and January 2028.
const MEETINGS: FomcMeeting[] = [
  meeting("2026-07-28", "2026-07-29", "decision"),
  meeting("2026-09-15", "2026-09-16", "decision"),
  meeting("2026-12-08", "2026-12-09", "decision"),
  meeting("2027-01-26", "2027-01-27", "decision"),
  meeting("2027-09-14", "2027-09-15", "decision"),
  meeting("2027-10-26", "2027-10-27", "strategy"),
  meeting("2027-11-16", "2027-11-17", "decision"),
  meeting("2028-01-25", "2028-01-26", "decision"),
];

describe("decisionDates", () => {
  it("excludes strategy meetings and sorts ascending", () => {
    expect(decisionDates(MEETINGS)).toEqual([
      "2026-07-29",
      "2026-09-16",
      "2026-12-09",
      "2027-01-27",
      "2027-09-15",
      "2027-11-17",
      "2028-01-26",
    ]);
    expect(decisionDates(MEETINGS)).not.toContain("2027-10-27");
  });
});

describe("nextFomc", () => {
  it("picks 2026-07-29 when today is 2026-07-10", () => {
    expect(nextFomc(MEETINGS, utc("2026-07-10"))).toBe("2026-07-29");
  });

  it("counts a decision day itself as the next meeting", () => {
    expect(nextFomc(MEETINGS, utc("2026-07-29"))).toBe("2026-07-29");
  });

  it("rolls past the last 2026 decision into the 2027 calendar", () => {
    expect(nextFomc(MEETINGS, utc("2026-12-10"))).toBe("2027-01-27");
  });

  it("skips the October 2027 strategy meeting", () => {
    expect(nextFomc(MEETINGS, utc("2027-09-16"))).toBe("2027-11-17");
    expect(nextFomc(MEETINGS, utc("2027-10-01"))).toBe("2027-11-17");
  });

  it("returns null when the schedule has run out", () => {
    expect(nextFomc(MEETINGS, utc("2028-01-27"))).toBeNull();
  });
});

describe("nextMeeting", () => {
  it("finds the strategy meeting when asked for one", () => {
    const m = nextMeeting(MEETINGS, utc("2027-10-01"), "strategy");
    expect(m?.end).toBe("2027-10-27");
    expect(m?.decision_date).toBeNull();
  });

  it("without a kind filter it returns the nearest meeting of any kind", () => {
    expect(nextMeeting(MEETINGS, utc("2027-10-01"))?.end).toBe("2027-10-27");
  });

  it("returns null past the end of the schedule", () => {
    expect(nextMeeting(MEETINGS, utc("2028-02-01"))).toBeNull();
  });
});

describe("daysUntil", () => {
  it("counts whole UTC days", () => {
    expect(daysUntil("2026-07-29", utc("2026-07-10"))).toBe(19);
    expect(daysUntil("2026-07-29", utc("2026-07-29"))).toBe(0);
    expect(daysUntil("2026-07-28", utc("2026-07-29"))).toBe(-1);
  });
});

describe("blackout window", () => {
  it("blackoutStart is the second Saturday preceding the decision", () => {
    expect(blackoutStart("2026-07-29")).toBe("2026-07-18");
    expect(blackoutStart("2026-09-16")).toBe("2026-09-05");
    expect(blackoutStart("2026-12-09")).toBe("2026-11-28");
    expect(blackoutStart("2027-01-27")).toBe("2027-01-16");
  });

  it("blackoutEnd is the first Thursday strictly after the decision", () => {
    expect(blackoutEnd("2026-07-29")).toBe("2026-07-30");
    expect(blackoutEnd("2026-12-09")).toBe("2026-12-10");
    expect(blackoutEnd("2027-01-27")).toBe("2027-01-28");
  });

  it("applies to the strategy meeting too", () => {
    expect(blackoutStart("2027-10-27")).toBe("2027-10-16");
    expect(blackoutEnd("2027-10-27")).toBe("2027-10-28");
  });

  it("inBlackout is inclusive of both boundaries and false just outside", () => {
    const d = "2026-07-29";
    expect(inBlackout(utc("2026-07-17"), d)).toBe(false); // Friday before start
    expect(inBlackout(utc("2026-07-18"), d)).toBe(true); // start (second Saturday)
    expect(inBlackout(utc("2026-07-29"), d)).toBe(true); // decision day
    expect(inBlackout(utc("2026-07-30"), d)).toBe(true); // end (Thursday after)
    expect(inBlackout(utc("2026-07-31"), d)).toBe(false); // Friday after end
  });
});
