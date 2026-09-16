import { describe, it, expect } from "vitest";
import { classifyColor, colorInfo, COLOR_META } from "../colorDay";
import type { FomcEvent } from "../../types";

describe("classifyColor", () => {
  it("greens when both SPY and TLT are up", () => {
    expect(classifyColor(0.5, 0.3)).toBe("green");
  });
  it("oranges when SPY up, TLT down", () => {
    expect(classifyColor(0.5, -0.3)).toBe("orange");
  });
  it("blues when SPY down, TLT up", () => {
    expect(classifyColor(-0.5, 0.3)).toBe("blue");
  });
  it("reds when both down", () => {
    expect(classifyColor(-0.5, -0.3)).toBe("red");
  });
  it("treats exactly zero as up (>= 0)", () => {
    expect(classifyColor(0, 0)).toBe("green");
    expect(classifyColor(0, -0.1)).toBe("orange");
    expect(classifyColor(-0.1, 0)).toBe("blue");
  });
  it("returns null when either leg is missing", () => {
    expect(classifyColor(null, 0.3)).toBeNull();
    expect(classifyColor(0.3, null)).toBeNull();
    expect(classifyColor(null, null)).toBeNull();
  });
});

describe("colorInfo", () => {
  it("attaches the canonical label/hex", () => {
    const e = { spy_d0: 1, tlt_d0: -1 } as FomcEvent;
    const info = colorInfo(e);
    expect(info?.color).toBe("orange");
    expect(info?.label).toBe(COLOR_META.orange.label);
    expect(info?.hex).toBe(COLOR_META.orange.hex);
  });
  it("returns null for missing data", () => {
    expect(colorInfo({ spy_d0: null, tlt_d0: 1 } as FomcEvent)).toBeNull();
  });
});
