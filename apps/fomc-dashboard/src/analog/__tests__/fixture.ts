import type { AnalogDoc, AnalogPoint } from "../../types";

function pt(t: number, date: string, spy: number, sma200_pct: number, event?: string): AnalogPoint {
  return { t, date, spy, tlt: 0, spy_close: 100 * (1 + spy / 100), sma200_pct, event };
}

/** Small but shape-complete fixture; the 2026 path ends on day 22 at -5.92% (SPY 733.00). */
export const fixtureDoc: AnalogDoc = {
  generated_at: "2026-11-06T15:07:45+00:00",
  peak_2018: { date: "2018-09-20", spy: 293.58 },
  peak_2026: { date: "2026-10-06", spy: 779.09 },
  series_2018: [
    pt(0, "2018-09-20", 0, 6.9),
    pt(9, "2018-10-03", -0.6, 6.0, "Powell: long way from neutral"),
    pt(14, "2018-10-10", -5.2, 0.75, "-3.3% day"),
    pt(15, "2018-10-11", -7.29, -1.48, "First close below 200d"),
    pt(27, "2018-10-29", -10.12, -4.51, "Oct low, -10%"),
    pt(33, "2018-11-06", -6.29, -0.35, "Midterms"),
    pt(34, "2018-11-07", -4.28, 1.79, "Relief rally fails at 200d"),
    pt(62, "2018-12-19", -14.42, -8.77, "Fed hikes, autopilot"),
    pt(65, "2018-12-24", -20.18, -14.76, "Low, -20%"),
    pt(72, "2019-01-04", -14.03, -7.88, "Powell: patient"),
    pt(80, "2019-01-16", -8.0, -2.0),
  ],
  series_2026: [
    pt(0, "2026-10-06", 0, 7.98),
    pt(10, "2026-10-20", -1.0, 6.5),
    { t: 22, date: "2026-11-05", spy: -5.92, tlt: 6.02, spy_close: 733.0, sma200_pct: 0.39, event: "-4.4% day, AI de-rating" },
  ],
  key_dates_2026: { fomc_dec: "2026-12-09", cr_expiry: "2026-12-11", nvda: "2026-11-17", cook_hearing: "2026-12-14" },
  levels: {
    spy: { resistance: [[745.9, "61.8%"]], support: [[730.2, "200-day"]] },
    es: { resistance: [[7490, "Daily pivot"]], support: [[7353, "200-day"]] },
  },
};
