import { describe, it, expect } from "vitest";
import {
  FOMC_DECISION_DATES,
  nextFomc,
  daysUntil,
  blackoutStart,
  blackoutEnd,
  inBlackout,
} from "../fomcSchedule";

const utc = (iso: string) => new Date(`${iso}T12:00:00Z`);

describe("nextFomc", () => {
  it("picks 2026-07-29 when today is 2026-07-10", () => {
    expect(nextFomc(utc("2026-07-10"))).toBe("2026-07-29");
  });

  it("counts a decision day itself as the next meeting", () => {
    expect(nextFomc(utc("2026-07-29"))).toBe("2026-07-29");
  });

  it("returns null when the schedule has run out", () => {
    expect(nextFomc(utc("2026-12-10"))).toBeNull();
  });

  it("schedule is sorted ascending (nextFomc relies on it)", () => {
    expect([...FOMC_DECISION_DATES].sort()).toEqual(FOMC_DECISION_DATES);
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
  });

  it("blackoutEnd is the first Thursday strictly after the decision", () => {
    expect(blackoutEnd("2026-07-29")).toBe("2026-07-30");
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
