import { describe, it, expect } from "vitest";
import { sortBy } from "../sort";

interface Row {
  d: string;
  v: number | null;
}

const rows: Row[] = [
  { d: "a", v: 3 },
  { d: "b", v: -1 },
  { d: "c", v: null },
  { d: "d", v: 2 },
];

describe("sortBy", () => {
  it("sorts ascending with nulls sunk to the bottom", () => {
    const out = sortBy(rows, "v", "asc").map((r) => r.d);
    expect(out).toEqual(["b", "d", "a", "c"]);
  });
  it("sorts descending with nulls still sunk to the bottom", () => {
    const out = sortBy(rows, "v", "desc").map((r) => r.d);
    expect(out).toEqual(["a", "d", "b", "c"]);
  });
  it("sorts strings", () => {
    expect(sortBy(rows, "d", "desc").map((r) => r.d)).toEqual(["d", "c", "b", "a"]);
  });
  it("is stable for equal keys", () => {
    const eq = [
      { d: "x", v: 1 },
      { d: "y", v: 1 },
      { d: "z", v: 1 },
    ];
    expect(sortBy(eq, "v", "asc").map((r) => r.d)).toEqual(["x", "y", "z"]);
  });
});
