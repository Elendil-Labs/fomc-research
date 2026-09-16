import { useState } from "react";
import type { FomcEvent, RegimeIntelDocument } from "../types";
import { blackoutEnd, blackoutStart, daysUntil, inBlackout, nextFomc } from "../lib/fomcSchedule";
import {
  conditionEvents,
  playbookTable,
  PLAYBOOK_WINDOWS,
  type PlaybookWindow,
  type WindowStats,
} from "../lib/playbook";
import { pct, shortDate, signClass } from "../lib/format";

const ACTIONS = ["All", "Hike", "Hold", "Cut"] as const;
type ActionFilter = (typeof ACTIONS)[number];

const WINDOW_LABELS: Record<PlaybookWindow, string> = {
  d0: "d0",
  p1: "+1",
  p3: "+3",
  p5: "+5",
  p10: "+10",
};

/** One grid cell: mean · win-rate, colored by mean sign, median/n in the tooltip. */
function StatCell({ s }: { s: WindowStats }) {
  if (s.n === 0 || s.mean === null || s.winRate === null) {
    return <td className="flat">—</td>;
  }
  return (
    <td className={signClass(s.mean)} title={`median ${pct(s.median)} · n=${s.n}`}>
      {pct(s.mean)} · {Math.round(s.winRate * 100)}%
    </td>
  );
}

/**
 * Bridges Regime Intelligence and the Event Explorer: given the CURRENT stated
 * regime and the NEXT scheduled FOMC meeting, show what historically happened at
 * meetings under that regime. Historical conditional evidence — not investment advice.
 */
export function PlaybookPanel({
  doc,
  events,
  today = new Date(),
}: {
  doc: RegimeIntelDocument;
  events: FomcEvent[];
  /** Injectable clock so tests are deterministic. */
  today?: Date;
}) {
  const [action, setAction] = useState<ActionFilter>("All");

  const regime = doc.current_repo_regime || "Unknown";
  const next = nextFomc(today);

  const regimeEvents = conditionEvents(events, { regime });
  const conditioned =
    action === "All" ? regimeEvents : conditionEvents(events, { regime, action });
  const grid = playbookTable(conditioned);
  const scheduledTotal = events.filter((e) => !e.emergency).length;
  const pivot = doc.inferred_regime?.startsWith("Potential pivot") ?? false;

  return (
    <div className="panel playbook">
      <div className="playbook-head">
        {next ? (
          <>
            <span className="next-meeting">
              Next FOMC: <strong>{shortDate(next)}</strong>{" "}
              <span className="muted">· {daysUntil(next, today)} days away</span>
            </span>
            {inBlackout(today, next) ? (
              <span className="badge blackout">
                Fed blackout in effect (ends {shortDate(blackoutEnd(next))})
              </span>
            ) : (
              <span className="muted tiny">Blackout begins {shortDate(blackoutStart(next))}</span>
            )}
          </>
        ) : (
          <span className="muted tiny">
            No future meeting in the local FOMC calendar — schedule needs updating.
          </span>
        )}
      </div>

      <p className="playbook-conditioning">
        Historical playbook: <strong>{regime}</strong>-regime meetings since 2018 (n=
        {regimeEvents.length}, emergencies excluded)
      </p>

      <div className="chips playbook-chips">
        {ACTIONS.map((a) => {
          const count =
            a === "All" ? regimeEvents.length : regimeEvents.filter((e) => e.action === a).length;
          const empty = a !== "All" && count === 0;
          return (
            <button
              key={a}
              type="button"
              className={`chip${action === a ? " on" : ""}`}
              disabled={empty}
              title={
                empty
                  ? a === "Hold"
                    ? `No ${regime}-regime hold meetings in the sample.`
                    : `No ${a.toLowerCase()}s occurred within ${regime} regimes since 2018 — a ${a.toLowerCase()} starts a ${a === "Hike" ? "Tightening" : "Easing"} regime, so this combination is empty by construction.`
                  : undefined
              }
              onClick={() => setAction(a)}
            >
              {a === "All" ? a : `${a} (${count})`}
            </button>
          );
        })}
      </div>

      <div className="table-wrap" style={{ marginTop: 4 }}>
        <table className="playbook-table">
          <thead>
            <tr>
              <th className="left">Asset</th>
              {PLAYBOOK_WINDOWS.map((w) => (
                <th key={w}>{WINDOW_LABELS[w]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["spy", "tlt"] as const).map((asset) => (
              <tr key={asset}>
                <td className="left rowhead">{asset.toUpperCase()}</td>
                {PLAYBOOK_WINDOWS.map((w) => (
                  <StatCell key={w} s={grid[asset][w]} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted tiny" style={{ margin: "6px 0 0" }}>
        Cells: mean return · share of meetings positive. Hover for median and n.
      </p>

      {pivot && (
        <p className="playbook-pivot-note">
          Note: current evidence is leaning against the stated regime — historical base rates
          under {regime} may understate transition risk.
        </p>
      )}

      <p className="muted tiny playbook-footer">
        Historical conditional evidence from {scheduledTotal} scheduled FOMC decisions (2018→).
        Not investment advice.
      </p>
    </div>
  );
}
