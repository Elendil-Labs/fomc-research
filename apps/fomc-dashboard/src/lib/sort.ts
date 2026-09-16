// Generic, null-safe table sorting used by the event table.

export type SortDir = "asc" | "desc";

/**
 * Stable sort by a key. null/undefined always sink to the bottom regardless of dir,
 * so "missing forward window" rows never masquerade as the best/worst performers.
 */
export function sortBy<T>(rows: T[], key: keyof T, dir: SortDir): T[] {
  const sign = dir === "asc" ? 1 : -1;
  return rows
    .map((row, i) => [row, i] as const)
    .sort(([a, ia], [b, ib]) => {
      const va = a[key];
      const vb = b[key];
      const aMissing = va === null || va === undefined;
      const bMissing = vb === null || vb === undefined;
      if (aMissing && bMissing) return ia - ib;
      if (aMissing) return 1;
      if (bMissing) return -1;
      if (va < vb) return -1 * sign;
      if (va > vb) return 1 * sign;
      return ia - ib; // stable tiebreak on original index
    })
    .map(([row]) => row);
}
