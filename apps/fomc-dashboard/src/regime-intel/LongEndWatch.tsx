import type {
  AuctionDoc,
  AuctionRow,
  AuctionStatus,
  CftcContract,
  CftcDoc,
  LongEndDoc,
  LongEndGroup,
  LongEndIndicator,
} from "../types";
import { shortDate } from "../lib/format";

// Long-end watch: has TLT bottomed? Three deterministic inputs, no LLM:
//   1. long_end_axis.json    — valuation (real yield, term premium, breakevens, MOVE) and
//                              timing boxes with explicit thresholds, plus context yields.
//   2. auction_monitor.json  — 10/20/30-Year coupon auctions vs trailing averages.
//   3. cftc_positioning.json — TFF asset-manager / leveraged-fund net positioning.
// The "N of M boxes" count is computed client-side so the three derived boxes
// (auction stress, real money stopped selling, spec capitulation) stay in sync with
// whichever docs actually loaded. Any doc may be null; the rest still renders.

const ANALOG_IDS = new Set(["DFII10", "ACMTP10", "MOVE"]);
const CONTEXT_ORDER = ["DGS10", "DGS30", "T10Y2Y", "FIVE_THIRTY", "MORTGAGE30US"];
const LONG_END_TERM = /^(10|20|30)-Year/i;
const AUCTION_STRESS_WINDOW_DAYS = 30;
const DAY_MS = 86_400_000;

const STATUS_COLOR: Record<AuctionStatus, string> = {
  stress: "#ef4444",
  watch: "#f59e0b",
  ok: "#22c55e",
};

const GROUP_COLOR: Record<LongEndGroup, string> = {
  valuation: "#5b9dff",
  timing: "#f59e0b",
  context: "#94a3b8",
};

/** A checklist row: either a producer indicator or a box derived from the other docs. */
export interface LongEndBox {
  id: string;
  name: string;
  group: "valuation" | "timing";
  checked: boolean | null;
  valueText: string;
  rule: string;
  detail: string;
  analogText?: string;
}

/** Format a level with its unit: "1.95%", "118 index", "7 wks"; em-dash for missing. */
export function fmtValue(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const n = Number.isInteger(v)
    ? v.toLocaleString("en-US")
    : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (!unit) return n;
  return unit === "%" ? `${n}%` : `${n} ${unit}`;
}

/** Signed thousands: 2,531,400 -> "+2,531k"; -83,900 -> "-84k"; em-dash for missing. */
export function fmtK(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const k = Math.round(v / 1000);
  const abs = Math.abs(k).toLocaleString("en-US");
  return `${k > 0 ? "+" : k < 0 ? "-" : ""}${abs}k`;
}

function fmtRatio(v: number | null | undefined): string {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(2);
}

function fmtPct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined || Number.isNaN(v) ? "—" : `${v.toFixed(digits)}%`;
}

/** "2026-09-11" -> "Sep 11" (year dropped; the strip is a recent window). */
function monthDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** True when the last stress date is within `windowDays` calendar days before generated_at. */
export function stressWithinWindow(
  lastStress: string | null | undefined,
  generatedAt: string,
  windowDays = AUCTION_STRESS_WINDOW_DAYS,
): boolean {
  if (!lastStress) return false;
  const a = new Date(lastStress).getTime();
  const b = new Date(generatedAt).getTime();
  if (Number.isNaN(a) || Number.isNaN(b)) return false;
  // Calendar-day arithmetic: last_long_end_stress is a yyyy-mm-dd, generated_at a timestamp.
  const days = Math.floor((b - a) / DAY_MS);
  return days >= 0 && days <= windowDays;
}

function analogLine(doc: LongEndDoc, id: string, unit: string): string | undefined {
  if (!ANALOG_IDS.has(id)) return undefined;
  const parts = Object.entries(doc.analogs ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, vals]) => {
      const v = vals[id as keyof typeof vals];
      return `${date.slice(0, 4)}: ${fmtValue(v, unit)}`;
    });
  return parts.length ? `at the ${parts.join(" · ")} lows` : undefined;
}

function ruleText(ind: LongEndIndicator): string {
  if (ind.rule) return ind.rule;
  return ind.threshold === null ? "—" : `threshold ${fmtValue(ind.threshold, ind.unit)}`;
}

/** Build the ordered box list: producer valuation/timing rows, then the three derived rows. */
export function buildBoxes(
  longEnd: LongEndDoc | null,
  auctions: AuctionDoc | null,
  cftc: CftcDoc | null,
): LongEndBox[] {
  const boxes: LongEndBox[] = [];
  if (longEnd) {
    for (const ind of longEnd.indicators) {
      if (ind.group === "context") continue;
      boxes.push({
        id: ind.id,
        name: ind.name,
        group: ind.group,
        checked: ind.checked,
        valueText: fmtValue(ind.latest, ind.unit),
        rule: ruleText(ind),
        detail: ind.detail,
        analogText: analogLine(longEnd, ind.id, ind.unit),
      });
    }
  }

  const stress = auctions?.summary;
  boxes.push({
    id: "AUCTION_STRESS",
    name: "Recent long-end auction stress",
    group: "timing",
    checked: auctions
      ? stressWithinWindow(stress?.last_long_end_stress, auctions.generated_at)
      : null,
    valueText: stress?.last_long_end_stress ? shortDate(stress.last_long_end_stress) : "—",
    rule: `stress auction within ${AUCTION_STRESS_WINDOW_DAYS}d`,
    detail: auctions
      ? `${stress?.stress_count_90d ?? 0} stress · ${stress?.watch_count_90d ?? 0} watch in 90d`
      : "pending next data run",
  });

  const c = cftc?.summary;
  boxes.push({
    id: "REAL_MONEY_SELLING",
    name: "Real money stopped selling",
    group: "timing",
    checked: cftc ? !c?.real_money_distribution : null,
    valueText: cftc ? (c?.real_money_distribution ? "distributing" : "stopped") : "—",
    rule: "asset managers not net sellers",
    detail: cftc ? `${c?.am_stopped_selling_count ?? 0} of ${cftc.contracts.length} contracts` : "pending next data run",
  });
  boxes.push({
    id: "SPEC_CAPITULATION",
    name: "Spec capitulation",
    group: "timing",
    checked: cftc ? Boolean(c?.spec_capitulation) : null,
    valueText: cftc ? (c?.spec_capitulation ? "yes" : "no") : "—",
    rule: "leveraged-fund net at 26w low",
    detail: cftc
      ? `${cftc.contracts.filter((k) => k.lf_net_26w_low).length} of ${cftc.contracts.length} contracts at 26w low`
      : "pending next data run",
  });
  return boxes;
}

export interface BoxCounts {
  checked: number;
  total: number;
  valuation: { checked: number; total: number };
  timing: { checked: number; total: number };
}

/** Count checked boxes among those with a verdict (checked !== null). */
export function countBoxes(boxes: LongEndBox[]): BoxCounts {
  const tally = (g?: LongEndBox["group"]) => {
    const live = boxes.filter((b) => b.checked !== null && (!g || b.group === g));
    return { checked: live.filter((b) => b.checked).length, total: live.length };
  };
  return { ...tally(), valuation: tally("valuation"), timing: tally("timing") };
}

function markFor(checked: boolean | null): { text: string; color: string; title: string } {
  if (checked === null) return { text: "—", color: "var(--muted)", title: "no data" };
  return checked
    ? { text: "✓", color: "#22c55e", title: "checked" }
    : { text: "○", color: "var(--muted)", title: "not yet" };
}

function GroupChip({ group }: { group: LongEndGroup }) {
  return (
    <span
      className="badge claim"
      style={{ color: GROUP_COLOR[group], borderColor: GROUP_COLOR[group] }}
    >
      {group}
    </span>
  );
}

function ContextLine({ doc }: { doc: LongEndDoc }) {
  const ctx = doc.indicators.filter((i) => i.group === "context");
  if (!ctx.length) return null;
  const ordered = [...ctx].sort(
    (a, b) => CONTEXT_ORDER.indexOf(a.id) - CONTEXT_ORDER.indexOf(b.id),
  );
  return (
    <div className="le-strip muted" data-testid="le-context">
      {ordered.map((i) => (
        <span key={i.id} className="le-item">
          {i.name}: <strong style={{ color: "var(--text)" }}>{fmtValue(i.latest, i.unit)}</strong>
          {i.as_of ? ` (${monthDay(i.as_of)})` : ""}
        </span>
      ))}
    </div>
  );
}

function AuctionItem({ a }: { a: AuctionRow }) {
  return (
    <span className="le-item" data-status={a.status}>
      <strong>{a.term}</strong> {monthDay(a.auction_date)}: b/c {fmtRatio(a.bid_to_cover)} vs avg{" "}
      {fmtRatio(a.bc_avg_12m)} · indirects {fmtPct(a.indirect_pct)} ·{" "}
      <span style={{ color: STATUS_COLOR[a.status], fontWeight: 700 }}>{a.status}</span>
    </span>
  );
}

function AuctionStrip({ doc }: { doc: AuctionDoc | null }) {
  if (!doc) {
    return (
      <div className="tiny muted" style={{ marginTop: 4 }}>
        Auction monitor pending next data run.
      </div>
    );
  }
  const recent = doc.auctions.filter((a) => LONG_END_TERM.test(a.term)).slice(0, 4);
  const next = doc.summary.next_long_end_auction;
  return (
    <div data-testid="le-auctions">
      <div className="le-strip">
        {recent.length === 0 && <span className="muted">No long-end auctions in window.</span>}
        {recent.map((a) => (
          <AuctionItem key={`${a.cusip}-${a.auction_date}`} a={a} />
        ))}
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>
        Next long-end auction:{" "}
        {next ? `${next.term} on ${shortDate(next.auction_date)}` : "none scheduled"}
        {doc.summary.read ? ` · ${doc.summary.read}` : ""}
      </div>
      {doc.note_on_tail && (
        <div className="tiny muted" style={{ marginTop: 4 }}>
          {doc.note_on_tail}
        </div>
      )}
    </div>
  );
}

function PositioningItem({ c }: { c: CftcContract }) {
  return (
    <span className="le-item">
      <strong>{c.name}</strong> AM {fmtK(c.am_net)} ({fmtK(c.am_net_change_4w)} 4w) · LF{" "}
      {fmtK(c.lf_net)} ({fmtK(c.lf_net_change_4w)} 4w)
      {c.am_selling_streak_weeks > 0 && (
        <>
          {" "}
          <span className="badge imp-medium">AM selling {c.am_selling_streak_weeks} wks</span>
        </>
      )}
      {c.am_stopped_selling && (
        <>
          {" "}
          <span className="badge official">AM stopped</span>
        </>
      )}
      {c.lf_net_26w_low && (
        <>
          {" "}
          <span className="badge imp-high">LF 26w low</span>
        </>
      )}
    </span>
  );
}

function PositioningStrip({ doc }: { doc: CftcDoc | null }) {
  if (!doc) {
    return (
      <div className="tiny muted" style={{ marginTop: 4 }}>
        CFTC positioning pending next data run.
      </div>
    );
  }
  return (
    <div data-testid="le-positioning">
      <div className="le-strip">
        {doc.contracts.map((c) => (
          <PositioningItem key={c.id} c={c} />
        ))}
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }}>
        {doc.summary.read}
        {doc.summary.as_of ? ` · as of ${shortDate(doc.summary.as_of)}` : ""}
      </div>
    </div>
  );
}

export function LongEndWatch({
  longEnd,
  auctions,
  cftc,
}: {
  longEnd: LongEndDoc | null;
  auctions: AuctionDoc | null;
  cftc: CftcDoc | null;
}) {
  const title = "Long-end watch: has TLT bottomed?";

  if (!longEnd && !auctions && !cftc) {
    return (
      <div className="panel">
        <div className="qs-row">
          <span className="label">{title}</span>
          <span className="v" style={{ color: "var(--muted)" }}>—</span>
        </div>
        <div className="tiny muted" style={{ marginTop: 8 }}>
          Long-end watch populates on the next scheduled data run (FRED, TreasuryDirect, CFTC;
          deterministic).
        </div>
      </div>
    );
  }

  const boxes = buildBoxes(longEnd, auctions, cftc);
  const counts = countBoxes(boxes);
  const headColor =
    counts.total === 0
      ? "var(--muted)"
      : counts.checked / counts.total >= 0.67
        ? "#22c55e"
        : counts.checked / counts.total >= 0.34
          ? "#f59e0b"
          : "#94a3b8";

  const sources = [longEnd?.source, auctions?.source, cftc?.source].filter(Boolean).join(" · ");
  const stamp = longEnd?.generated_at ?? auctions?.generated_at ?? cftc?.generated_at;

  return (
    <div className="panel">
      <div className="qs-row">
        <span className="label">{title}</span>
        <span className="v" style={{ color: headColor }} data-testid="le-count">
          {`${counts.checked} of ${counts.total} boxes checked`}
        </span>
      </div>
      <div className="tiny muted" style={{ marginTop: 6 }} data-testid="le-split">
        {`valuation ${counts.valuation.checked}/${counts.valuation.total} · timing ${counts.timing.checked}/${counts.timing.total}`}
        {longEnd?.summary?.read ? ` · ${longEnd.summary.read}` : ""}
      </div>

      <table className="bs-indicators" data-testid="le-boxes">
        <tbody>
          {boxes.map((b) => {
            const m = markFor(b.checked);
            return (
              <tr
                key={b.id}
                data-box={b.id}
                data-checked={b.checked === null ? "pending" : String(b.checked)}
              >
                <td className="left">
                  {b.name}
                  {b.analogText && (
                    <div className="tiny muted" style={{ marginTop: 2 }}>
                      {b.analogText}
                    </div>
                  )}
                </td>
                <td className="left">
                  <GroupChip group={b.group} />
                </td>
                <td className="left" style={{ whiteSpace: "nowrap" }}>
                  {b.valueText}
                </td>
                <td className="left muted">{b.rule}</td>
                <td className="left le-mark" style={{ color: m.color }} title={m.title}>
                  {m.text}
                </td>
                <td className="left muted">{b.detail}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {longEnd ? (
        <ContextLine doc={longEnd} />
      ) : (
        <div className="tiny muted" style={{ marginTop: 8 }}>
          Long-end valuation/timing axis pending next data run.
        </div>
      )}

      <div className="le-sub">Long-end auctions</div>
      <AuctionStrip doc={auctions} />

      <div className="le-sub">Positioning (CFTC TFF)</div>
      <PositioningStrip doc={cftc} />

      <div className="tiny muted" style={{ marginTop: 10 }}>
        Long-end watch: {sources} · deterministic, no LLM · {shortDate(stamp)}
      </div>
    </div>
  );
}
