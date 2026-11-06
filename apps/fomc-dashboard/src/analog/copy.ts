// The published copy for the 4Q'18 analog page, verbatim. Numbers and sentences are the
// author's; do not paraphrase here. Anything computed from data lives in Analog2018.tsx.

export const TITLE = "What if 4Q'26 looks like 4Q'18?";

export const INTRO: string[] = [
  "Bottom line, November 6, 2026: the setup rhymes with the fourth quarter of 2018 in the three things that mattered then, a Fed tightening into a falling market, a break of the 200-day led by technology, and a political calendar with a shutdown date in December. It differs in the two things that ended 2018, a Fed that could pivot because core inflation was 1.9 percent, and a credit market that broke. Core PCE is 3.1 percent today and high-yield spreads did not move on Thursday. So the shape of the next six weeks can look like 2018 while the exit looks nothing like it. The level that decides which is the 200-day, SPY 730 and ES 7353, and the first failed rally back to it from underneath is the signal to respect.",
  "SPY closed Thursday at 733.00, down 4.41 percent, a bottom-two-tenths-of-a-percent day since 2010, and 5.9 percent below the October 6 high of 779.09. ES settled 7373, VIX 28.18, the 2-year 4.46 percent. Twenty-two trading days after the peak in 2018 the index was 6.3 percent down. The two paths are within half a point of each other at the same day count.",
];

export interface LeadParagraph {
  lead: string;
  body: string;
}

export const REASONS_HEADING = "Five reasons it rhymes, strongest first";

export const REASONS: LeadParagraph[] = [
  {
    lead: "The Fed is tightening into the drawdown and has said conditions are loose.",
    body: "On October 3, 2018 Powell said rates were \"a long way from neutral.\" On October 28, 2026 Warsh said \"while overall financial conditions are tighter, I'm unwilling and unable to call them tight,\" with two of twelve voters dissenting for a hike. In both years the December hike was priced above 70 percent while the market fell, and Richmond's Barkin repeated on Thursday, the day of the 4.4 percent drop, that he expects further hikes at a gradual pace. The 2018 error was the December 19 hike into a market already 14 percent off its high, with the balance sheet on \"automatic pilot.\" December 9 is that decision point.",
  },
  {
    lead: "The chart is tracing the same template.",
    body: "2018 ran peak on September 20, a 3.3 percent shock day on October 10, the first close below the 200-day on October 11, and a 10 percent low on October 29. The 200-day then became the ceiling and capped both rallies, on November 7 and December 3, before the December leg to minus 20 percent. 2026 ran peak on October 6, a 4.4 percent shock day on November 5, and a close 0.4 percent above the 200-day. In our 70-event FOMC table the first close below the 200-day after six months above it (11 cases since 2010) produced an average lowest close of 7.1 percent below the break within 40 days, even though 64 percent of cases were higher 20 days later. The break gets tested lower before it resolves, and the bounce in between was where 2018 did most of its damage to anyone who bought the first dip.",
  },
  {
    lead: "The leadership cohort is breaking on its own earnings.",
    body: "Semis fell 12 percent on Thursday, the Nasdaq entered a correction, and the Magnificent Seven reported slower earnings growth than the other 493 companies for the first time since 2022 (22.6 versus 32.6 percent, FactSet, November 3). The capex bill is now being financed rather than expensed: Meta raised about 37 billion dollars of preferred and forward equity, Oracle raised 20 billion, Amazon's trailing free cash flow is negative 42 billion. In 2018 the same cohort led the index down with the forward multiple at 14.2 at the low. Today it is 18.7 after Thursday, so the valuation cushion under the leaders is thinner than it was.",
  },
  {
    lead: "The political calendar is a near-copy.",
    body: "Democrats took the House on November 6, 2018 and the government shut down on December 22. Democrats took both chambers on November 3, 2026 and the continuing resolution expires on December 11. Tariffs were the swing variable then (the December 1 G20 truce) and are now (a tariff repeal bill in the House's first hundred hours, with a presidential veto promised). A president publicly at odds with his own Fed chair's board is common to both.",
  },
  {
    lead: "Oil is collapsing in both.",
    body: "WTI went from 76 dollars on October 3, 2018 to about 42 on December 24. It has gone from 103 in mid-September to about 89 this week, down 14 percent in five sessions on Iran deal hopes. A falling oil price helped the 2018 Fed find its pivot, and it is the one input that could give this Fed a data-based reason to hold in December.",
  },
];

export const DIFFERENT_HEADING = "The two strongest arguments that this time is different";

export const DIFFERENT: LeadParagraph[] = [
  {
    lead: "Credit and breadth say sector de-rating, and 2018 needed a liquidation.",
    body: "High-yield spreads sit near 3.3 percent and the HYG ETF fell 0.3 percent on a day the index fell 4.4 percent. In 2018 spreads blew out to 5.4 percent and December had zero high-yield issuance, the first such month since 2008. Equal-weight SPY is up 2.4 percent over the last 20 sessions while cap-weight is down 5.3 percent, so 493 stocks are being bought while seven are being sold. The economy is not the problem either: Q3 GDP printed 3.4 percent, October payrolls came in at 165 thousand against 59 expected on Friday morning, unemployment is 4.1 percent, and Q3 earnings are growing 30 percent with 2027 estimates up 16 percent. A 4 percent down day with the index still above its 200-day has happened once since 2010 outside the pandemic, February 5, 2018, and the index was 3.4 percent higher 20 days later. Across all twelve 4 percent days since 2010, the 20-day forward return averaged plus 3.1 percent with 83 percent of cases positive.",
  },
  {
    lead: "Bonds are already doing the hedging the 2018 market waited two months for.",
    body: "The 2-year has fallen from 4.67 to 4.46 percent since the October 28 meeting and TLT rose on Thursday. In 2018 TLT was flat to down from the September peak until November 28 and did not rally until Powell blinked. The rates market has pre-priced relief, and oil's 14 percent drop lowers the headline inflation path into the December meeting. If Warsh holds on December 9 with that cover, the 2018 catalyst for the final leg never arrives, and the June value area at ES 7232 to 7268 is where the flush would end rather than the 6900s.",
  },
];

export const HONEST_WEIGHT =
  "The honest weight: the bull case has the better fundamentals and the bear case has the better chart and the worse Fed. Core PCE of 3.1 percent is the fact that keeps the two from resolving quickly, because it removes the pivot that rescued 2018 and leaves the market to find its own floor.";

export const TEMPLATE_HEADING = "The 2018 template";

export interface TemplateRow {
  day: number;
  what: string;
  spy: string;
  sma: string;
}

export const TEMPLATE_2018: TemplateRow[] = [
  { day: 0, what: "Sep 20 peak, 293.58", spy: "0.0%", sma: "" },
  { day: 9, what: "Oct 3, Powell \"long way from neutral\"", spy: "-0.6%", sma: "" },
  { day: 14, what: "Oct 10, -3.3% day", spy: "-5.2%", sma: "0.7% above" },
  { day: 15, what: "Oct 11, first close below", spy: "-7.3%", sma: "broken" },
  { day: 27, what: "Oct 29, October low", spy: "-10.1%", sma: "4.5% below" },
  { day: 34, what: "Nov 7, post-midterm rally", spy: "-4.3%", sma: "rally failed at it" },
  { day: 48, what: "Nov 28, Powell \"just below neutral\"", spy: "-6.5%", sma: "" },
  { day: 51, what: "Dec 3, December high", spy: "-4.9%", sma: "failed at it again" },
  { day: 62, what: "Dec 19, hike, \"autopilot\"", spy: "-14.4%", sma: "" },
  { day: 65, what: "Dec 24, low, 234.34", spy: "-20.2%", sma: "TLT +3.6% from peak date" },
  { day: 72, what: "Jan 4, Powell \"patient\"", spy: "-14.0%", sma: "" },
];

export const TEMPLATE_NOTE =
  "2026 is at day 22, minus 5.9 percent, with the December 9 FOMC on day 45, the CR expiry on day 47, and the Cook hearing on day 48.";

export const LEVELS_HEADING = "Levels to be prepared for";
export const ES_INTRO = "ES, December contract. MES trades the same prices at one tenth the size.";
export const SPY_INTRO = "SPY.";

/** ES ladder, verbatim from the copy; key = lower bound of a range for ordering. */
export const ES_LADDER = [
  { key: 7800, price: "7800", what: "90-day value-area high, 15-touch ceiling", action: "Analog is dead above here" },
  { key: 7762, price: "7762", what: "90-day point of control", action: "" },
  { key: 7725, price: "7725", what: "50-day", action: "" },
  { key: 7650, price: "7650", what: "90-day value-area low", action: "Reclaim = Thursday was the flush" },
  { key: 7575, price: "7575 to 7605", what: "Bottom of three months of value, R1, Nov 3 low", action: "First rally target. Sell into it until a daily close above" },
  { key: 7490, price: "7490", what: "Friday pivot", action: "" },
  { key: 7353, price: "7353", what: "200-day", action: "The referendum. Close below plus a failed retest = 2018 confirmed" },
  { key: 7322, price: "7322", what: "Friday overnight low", action: "" },
  { key: 7268, price: "7268", what: "S1", action: "" },
  { key: 7232, price: "7232 to 7268", what: "June 9 to 11 lows, last place value was built", action: "Buy zone with a stop under 7155, only on a reversal day with VIX above 25" },
  { key: 7155, price: "7155", what: "S2", action: "Below here there is no volume until 7056" },
  { key: 6933, price: "6933", what: "S3, roughly -12% from the high", action: "The 2018 \"October low\" equivalent" },
];

/** SPY ladder, verbatim from the copy; key = lowest price named in the row. */
export const SPY_LADDER = [
  { key: 779.1, price: "779.1", what: "October 6 high" },
  { key: 766.4, price: "766.4", what: "50-day" },
  { key: 758.6, price: "758.6", what: "38.2% retracement of the June to October rally" },
  { key: 752, price: "752 to 756", what: "September 16 and October 30 closes, 50% retracement" },
  { key: 745.9, price: "745.9", what: "61.8% retracement, broke Thursday, first resistance" },
  { key: 730.2, price: "731.8 / 730.2", what: "38.2% of the April to October rally, the 200-day" },
  { key: 725.4, price: "729.5 / 725.4", what: "July 29 and June 10 lows" },
  { key: 718.0, price: "718.0", what: "May low, 50% of April to October" },
  { key: 702.6, price: "702.6", what: "61.8% of April to October, and 10% from the high" },
  { key: 681.9, price: "681.9", what: "Flat on the year" },
  { key: 632.0, price: "655.2 / 632.0", what: "April and March lows, the 2018-style minus 20% zone" },
];

export const NAVIGATE_HEADING = "How to navigate it";

export const NAVIGATE: string[] = [
  "Treat the 200-day as a referendum. The base case after a first close below it is a flush and then a retest, and the 2018 bounces show how long the retest can take. Sell the first rally into 7575 to 7605 until price closes back above that zone, because in 2018 the first bounce was 6 percent in six sessions and died at the 200-day. Buy only at the June value, 7232 to 7268, with a hard stop, and only on a reversal day. ATR is 118 points, about 590 dollars a day per MES contract, so run half size.",
  "The catalyst calendar is the 2018 map. NVDA reports November 17 (the Apple warning in 2018 came January 3). The FOMC is December 9. The CR expires December 11 and the Cook hearing is December 14. Watch December hike odds against the tape: in 2018 they held near 70 percent all the way into the hike, and that rigidity was the error. If they fall below 50 percent while equities fall, the Fed has blinked and the analog breaks in the bulls' favor. If they hold above 80 percent while SPY trades below 730, December 9 is the December 19 moment.",
  "My odds, as of Friday morning: a test of SPY 702 to 718 by mid-December at 35 to 40 percent, a full 2018-style 20 percent drawdown into the low 620s at 10 percent, and a 50 percent chance that Thursday was the flush and SPY reclaims 746 and then 752 within a week, which would retire the template.",
];

export const BREAKS_HEADING = "The analog breaks in the bulls' favor if";
export const CONFIRMED_HEADING = "The analog is confirmed if";

export const BREAKS_CONFIRMED: [string, string][] = [
  ["HY spreads stay below 3.75%", "A close below the 200-day plus a failed retest from underneath"],
  ["Equal-weight keeps outperforming through NVDA", "HY spreads through 4%"],
  ["SPY reclaims 745.9 then 752 within a week", "December hike odds hold above 80% with SPY under 730"],
  ["December hike odds fall below 50%", "Oil's drop reverses on Hormuz"],
];

export const CAVEATS =
  "Caveats we owe you. Eleven 200-day breaks and twelve 4 percent days are tendencies, not laws. The 2018 path is one path, and the two cycles differ most on inflation and credit, which is exactly where the bulls are strongest. The levels above are from our ES volume profile and pivot history and will shift with each session. Data: SPY and TLT closes, FRED yields, TreasuryDirect, FactSet Earnings Insight (October 30 and November 3), BLS, BEA, the October 28 FOMC transcript, and our 72-event FOMC table, public at github.com/Elendil-Labs/fomc-research.";

export const DISCLOSURE =
  "[Disclosure: state the book's exposure to SPY, ES, MES and rate products here, or \"no position\" if none.]";

export const NOT_ADVICE = "Not investment advice.";
export const BYLINE = "Jing Xie, Co-Founder, Elendil Labs";

/** ES December settle on November 5, 2026 (the copy's "ES settled 7373"). Not in the data file. */
export const ES_SETTLE = 7373;
