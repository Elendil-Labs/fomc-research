// Level ladders for the analog page. Rows come from the author's copy (not the data file)
// so the "What to do" column and the range labels match the published text exactly; the
// current price is inserted in order so the reader sees where the tape sits on the ladder.

export interface LadderRow {
  /** Sort key (the lower bound for a range). */
  key: number;
  /** Display price or range, verbatim from the copy. */
  price: string;
  what: string;
  action?: string;
  /** True for the inserted "you are here" row. */
  current?: boolean;
}

export type LadderSide = "resistance" | "support" | "current";

export function sideOf(row: LadderRow, current: number): LadderSide {
  if (row.current) return "current";
  return row.key >= current ? "resistance" : "support";
}

/**
 * Sort high to low and insert the current price as its own row. A level equal to the
 * current price sorts above it (it counts as resistance, not yet reclaimed).
 */
export function buildLadder(
  rows: LadderRow[],
  current: number,
  currentLabel: string,
  digits = 0,
): LadderRow[] {
  const here: LadderRow = { key: current, price: current.toFixed(digits), what: currentLabel, current: true };
  return [...rows, here].sort((a, b) => {
    if (b.key !== a.key) return b.key - a.key;
    // tie: the real level first, the marker second
    return (a.current ? 1 : 0) - (b.current ? 1 : 0);
  });
}
