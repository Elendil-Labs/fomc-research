import { describe, it, expect } from "vitest";
import { parseEventTruthCsv, escapeCsv, toCsv } from "../csv";

const CSV = `date,chair,regime,action,ff_target,emergency,spy_close,spy_d0,tlt_d0,spy_p10
2018-01-31,Yellen,Unknown,Hold,1.25-1.50,False,281.9,0.05,0.59,
2020-03-15,Powell,Easing,Cut,0.00-0.25,True,-2.0,-1.5,2.3,4.1`;

describe("parseEventTruthCsv", () => {
  const rows = parseEventTruthCsv(CSV);

  it("parses the right number of rows", () => {
    expect(rows).toHaveLength(2);
  });
  it("keeps string columns as strings", () => {
    expect(rows[0].chair).toBe("Yellen");
    expect(rows[0].ff_target).toBe("1.25-1.50");
  });
  it("coerces numeric columns to numbers", () => {
    expect(rows[0].spy_close).toBe(281.9);
    expect(rows[1].spy_d0).toBe(-1.5);
  });
  it("coerces emergency to boolean", () => {
    expect(rows[0].emergency).toBe(false);
    expect(rows[1].emergency).toBe(true);
  });
  it("maps empty numeric cells to null (missing forward window)", () => {
    expect(rows[0].spy_p10).toBeNull();
    expect(rows[1].spy_p10).toBe(4.1);
  });
});

describe("csv escaping", () => {
  it("quotes fields containing commas and quotes", () => {
    expect(escapeCsv('a,b')).toBe('"a,b"');
    expect(escapeCsv('she said "hi"')).toBe('"she said ""hi"""');
    expect(escapeCsv("plain")).toBe("plain");
    expect(escapeCsv(null)).toBe("");
  });
  it("builds a full CSV document", () => {
    const out = toCsv(["a", "b"], [[1, "x,y"]]);
    expect(out).toBe('a,b\n1,"x,y"\n');
  });
});
