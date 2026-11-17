// FOMC meeting schedule date math + Fed communications-blackout windows.
// All comparisons are done on UTC calendar dates (yyyy-mm-dd strings), never local time.
//
// This module deliberately holds NO meeting dates. The schedule is owned by
// packages/fomc/src/fomc/calendar.py and exported to public/data/fomc_calendar.json by
// `fomc export-calendar` (run on every dashboard refresh), so there is exactly one copy
// of the dates in the repo. Load it with loadFomcCalendar() in ../data/load and pass the
// meetings into the helpers below.

export type MeetingKind = "decision" | "strategy";

/** One scheduled meeting, as exported by `fomc export-calendar`. */
export type FomcMeeting = {
  /** First day of the two-day meeting. */
  start: string;
  /** Second day of the meeting. */
  end: string;
  kind: MeetingKind;
  /** Announcement date for a decision meeting; null for a strategy meeting. */
  decision_date: string | null;
  blackout_start: string;
  blackout_end: string;
  source_url: string;
  published: string | null;
  note?: string | null;
};

export type FomcCalendarDoc = {
  generated_at: string;
  as_of: string;
  meetings: FomcMeeting[];
  decision_dates: string[];
  next_decision: string | null;
  provenance: {
    sources: { url: string; published: string | null; covers: string }[];
    coverage: {
      first_decision: string;
      last_decision: string;
      n_decisions: number;
      n_strategy_meetings: number;
    };
    horizon_days: number;
    schedule_warning: string | null;
  };
};

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

/** Policy-decision dates only, ascending. Strategy meetings announce nothing. */
export function decisionDates(meetings: FomcMeeting[]): string[] {
  return meetings
    .map((m) => m.decision_date)
    .filter((d): d is string => !!d)
    .sort();
}

/** First scheduled DECISION date on/after `today` (UTC date-compare), or null. */
export function nextFomc(meetings: FomcMeeting[], today: Date): string | null {
  const t = utcIso(today);
  for (const d of decisionDates(meetings)) {
    if (d >= t) return d;
  }
  return null;
}

/**
 * First meeting whose second day is on/after `today`, optionally of one kind.
 * Pass "strategy" to find the next non-decision meeting.
 */
export function nextMeeting(
  meetings: FomcMeeting[],
  today: Date,
  kind?: MeetingKind,
): FomcMeeting | null {
  const t = utcIso(today);
  const sorted = [...meetings].sort((a, b) => a.end.localeCompare(b.end));
  for (const m of sorted) {
    if (m.end >= t && (!kind || m.kind === kind)) return m;
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
 * preceding the meeting's second day. Walk back one day at a time collecting Saturdays.
 * e.g. decision 2026-07-29 (Wed) -> Saturdays 2026-07-25, 2026-07-18 -> returns 2026-07-18.
 * The blackout applies to every FOMC meeting, strategy meetings included.
 */
export function blackoutStart(meetingEndIso: string): string {
  let cursor = shiftIso(meetingEndIso, -1);
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
 * End of the blackout: the first Thursday strictly after the meeting's second day.
 * e.g. decision 2026-07-29 (Wed) -> 2026-07-30 (Thu).
 */
export function blackoutEnd(meetingEndIso: string): string {
  let cursor = shiftIso(meetingEndIso, 1);
  while (utcDow(cursor) !== 4) {
    cursor = shiftIso(cursor, 1);
  }
  return cursor;
}

/** True when `today` (UTC date) falls inside the blackout window, endpoints inclusive. */
export function inBlackout(today: Date, meetingEndIso: string): boolean {
  const t = utcIso(today);
  return t >= blackoutStart(meetingEndIso) && t <= blackoutEnd(meetingEndIso);
}
