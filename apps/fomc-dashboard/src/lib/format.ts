// Small display helpers shared across the UI.

/** Render a percentage return like "+1.23%" / "-0.45%"; em-dash for missing. */
export function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

/** Render a raw price/level; em-dash for missing. */
export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

/** Sign class for coloring positive/negative/neutral text. */
export function signClass(v: number | null | undefined): "pos" | "neg" | "flat" {
  if (v === null || v === undefined || Number.isNaN(v)) return "flat";
  if (v > 0) return "pos";
  if (v < 0) return "neg";
  return "flat";
}

/** "2026-06-23T12:00:00Z" -> "Jun 23, 2026". Falls back to the raw string. */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Relative-age label for freshness chips: "today", "3d ago", "2w ago". */
export function ageLabel(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const days = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 14) return `${days}d ago`;
  if (days < 60) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}
