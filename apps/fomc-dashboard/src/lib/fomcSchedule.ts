// FOMC meeting schedule + Fed communications-blackout date math.
// All comparisons are done on UTC calendar dates (yyyy-mm-dd strings), never local time.

/**
 * Scheduled FOMC decision (second/announcement) days.
 * Extend this list when the Fed publishes the 2027 calendar.
 */
export const FOMC_DECISION_DATES: string[] = [
  "2026-01-28",
  "2026-03-18",
  "2026-04-29",
  "2026-06-17",
  "2026-07-29",
  "2026-09-16",
  "2026-10-28",
  "2026-12-09",
];

/** yyyy-mm-dd of the UTC calendar date for a Date instant. */
function utcIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Midnight-UTC timestamp (ms) for an ISO yyyy-mm-dd date. */
function utcMidnight(iso: string): number {
  return Date.parse(`${iso}T00:00:00Z`);
}

const DAY_MS = 86_400_000;

/** Shift an ISO date by a number of days (UTC-safe). */
function shiftIso(iso: string, days: number): string {
  return new Date(utcMidnight(iso) + days * DAY_MS).toISOString().slice(0, 10);
}

/** UTC day-of-week for an ISO date: 0 = Sunday .. 6 = Saturday. */
function utcDow(iso: string): number {
  return new Date(utcMidnight(iso)).getUTCDay();
}

/** First scheduled decision date on/after `today` (UTC date-compare), or null if the schedule ran out. */
export function nextFomc(today: Date): string | null {
  const t = utcIso(today);
  for (const d of FOMC_DECISION_DATES) {
    if (d >= t) return d;
  }
  return null;
}

/** Whole calendar days from `today` (UTC date) until the ISO date. Negative if past. */
export function daysUntil(iso: string, today: Date): number {
  const todayMid = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.round((utcMidnight(iso) - todayMid) / DAY_MS);
}

/**
 * Start of the Fed external-communications blackout: the SECOND Saturday strictly
 * preceding the decision date. Walk back one day at a time collecting Saturdays.
 * e.g. decision 2026-07-29 (Wed) -> Saturdays 2026-07-25, 2026-07-18 -> returns 2026-07-18.
 */
export function blackoutStart(decisionIso: string): string {
  let cursor = shiftIso(decisionIso, -1);
  let saturdays = 0;
  for (;;) {
    if (utcDow(cursor) === 6) {
      saturdays += 1;
      if (saturdays === 2) return cursor;
    }
    cursor = shiftIso(cursor, -1);
  }
}

/**
 * End of the blackout: the first Thursday strictly after the decision date.
 * e.g. decision 2026-07-29 (Wed) -> 2026-07-30 (Thu).
 */
export function blackoutEnd(decisionIso: string): string {
  let cursor = shiftIso(decisionIso, 1);
  while (utcDow(cursor) !== 4) {
    cursor = shiftIso(cursor, 1);
  }
  return cursor;
}

/** True when `today` (UTC date) falls inside the blackout window, endpoints inclusive. */
export function inBlackout(today: Date, decisionIso: string): boolean {
  const t = utcIso(today);
  return t >= blackoutStart(decisionIso) && t <= blackoutEnd(decisionIso);
}
