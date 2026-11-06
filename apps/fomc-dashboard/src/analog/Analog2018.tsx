import { useEffect, useState } from "react";
import type { AnalogDoc, AnalogPoint } from "../types";
import { loadAnalog2018 } from "../data/load";
import { OverlayChart, pctLabel } from "./OverlayChart";
import { buildLadder, sideOf, type LadderRow } from "./ladder";
import * as C from "./copy";
import "./analog.css";

// "What if 4Q'26 looks like 4Q'18?" The copy is the author's and is rendered verbatim from
// ./copy; the chart, the 2026 row in the 2018 template, and the "you are here" rows in
// the ladders are computed from data/analog_2018.json.

const PENDING = "Analog overlay populates on the next scheduled data run.";

function last<T>(xs: T[]): T | undefined {
  return xs[xs.length - 1];
}

function LeadCards({ items, numbered }: { items: C.LeadParagraph[]; numbered: boolean }) {
  return (
    <div className="lead-cards">
      {items.map((it, i) => (
        <article className="panel lead-card" key={i}>
          {numbered && <div className="lead-num" aria-hidden="true">{i + 1}</div>}
          <p className="lead-body">
            <strong className="lead-lead">{it.lead}</strong> {it.body}
          </p>
        </article>
      ))}
    </div>
  );
}

function TemplateTable({ now }: { now: AnalogPoint }) {
  const rows = [...C.TEMPLATE_2018].sort((a, b) => a.day - b.day);
  // Where the 2026 path sits on the 2018 template, computed from the last 2026 point.
  const hereIdx = rows.findIndex((r) => r.day > now.t);
  const insertAt = hereIdx === -1 ? rows.length : hereIdx;
  const sma = now.sma200_pct;
  const smaText = `${Math.abs(sma).toFixed(1)}% ${sma >= 0 ? "above" : "below"}`;
  return (
    <div className="table-wrap">
      <table className="win-table analog-table">
        <thead>
          <tr>
            <th>Day from peak</th>
            <th className="left">2018</th>
            <th>SPY from peak</th>
            <th className="left">What the 200-day did</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, insertAt).map((r) => (
            <tr key={r.day}>
              <td>{r.day}</td>
              <td className="left">{r.what}</td>
              <td>{r.spy}</td>
              <td className="left">{r.sma}</td>
            </tr>
          ))}
          <tr className="here" data-testid="template-here">
            <td>{now.t}</td>
            <td className="left">2026 is here: {now.date}{now.event ? `, ${now.event}` : ""}</td>
            <td>{pctLabel(now.spy)}</td>
            <td className="left">{smaText}</td>
          </tr>
          {rows.slice(insertAt).map((r) => (
            <tr key={r.day}>
              <td>{r.day}</td>
              <td className="left">{r.what}</td>
              <td>{r.spy}</td>
              <td className="left">{r.sma}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Ladder({
  rows,
  current,
  currentLabel,
  withAction,
  testId,
  digits,
}: {
  rows: LadderRow[];
  current: number;
  currentLabel: string;
  withAction: boolean;
  testId: string;
  digits: number;
}) {
  const ladder = buildLadder(rows, current, currentLabel, digits);
  return (
    <div className="table-wrap">
      <table className="win-table analog-table ladder" data-testid={testId}>
        <thead>
          <tr>
            <th className="left">Level</th>
            <th className="left">What it is</th>
            {withAction && <th className="left">What to do</th>}
          </tr>
        </thead>
        <tbody>
          {ladder.map((r) => {
            const side = sideOf(r, current);
            return (
              <tr key={`${r.key}-${r.price}`} className={r.current ? "here" : undefined} data-side={side}>
                <td className="left lvl">
                  <span className={`lvl-dot ${side}`} aria-hidden="true" />
                  <span className="lvl-price">{r.price}</span>
                </td>
                <td className="left">{r.what}</td>
                {withAction && <td className="left">{r.action ?? ""}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Analog2018View({ doc }: { doc: AnalogDoc | null }) {
  if (!doc) {
    return (
      <div className="analog">
        <h1 className="page-headline">{C.TITLE}</h1>
        <div className="panel">
          <div className="qs-row">
            <span className="label">4Q'18 analog</span>
            <span className="v" style={{ color: "var(--muted)" }}>—</span>
          </div>
          <div className="tiny muted" style={{ marginTop: 8 }}>{PENDING}</div>
        </div>
      </div>
    );
  }
  const now = last(doc.series_2026);
  if (!now) {
    return <Analog2018View doc={null} />;
  }

  return (
    <div className="analog">
      <div className="page-intro analog-intro">
        <h1 className="page-headline">{C.TITLE}</h1>
        {C.INTRO.map((p, i) => (
          <p className="page-lead" key={i}>{p}</p>
        ))}
      </div>

      <OverlayChart s2018={doc.series_2018} s2026={doc.series_2026} />
      <div className="tiny muted analog-chart-note">
        SPY close, % from the peak ({doc.peak_2018.date} and {doc.peak_2026.date}). Hover for the day-by-day
        read. Dotted verticals are the 2026 calendar at the same day count.
      </div>

      <h2 className="section-title">{C.REASONS_HEADING}</h2>
      <LeadCards items={C.REASONS} numbered />

      <h2 className="section-title">{C.DIFFERENT_HEADING}</h2>
      <LeadCards items={C.DIFFERENT} numbered={false} />
      <p className="page-lead analog-prose">{C.HONEST_WEIGHT}</p>

      <h2 className="section-title">{C.TEMPLATE_HEADING}</h2>
      <div className="panel analog-panel">
        <TemplateTable now={now} />
      </div>
      <p className="page-lead analog-prose">{C.TEMPLATE_NOTE}</p>

      <h2 className="section-title">{C.LEVELS_HEADING}</h2>
      <div className="ladders">
        <div className="panel analog-panel">
          <p className="ladder-intro">{C.ES_INTRO}</p>
          <Ladder
            rows={C.ES_LADDER}
            current={C.ES_SETTLE}
            currentLabel="ES settle, you are here"
            withAction
            testId="es-ladder"
            digits={0}
          />
        </div>
        <div className="panel analog-panel">
          <p className="ladder-intro">{C.SPY_INTRO}</p>
          <Ladder
            rows={C.SPY_LADDER}
            current={now.spy_close}
            currentLabel={`SPY close ${now.date}, you are here`}
            withAction={false}
            testId="spy-ladder"
            digits={2}
          />
        </div>
      </div>

      <h2 className="section-title">{C.NAVIGATE_HEADING}</h2>
      {C.NAVIGATE.map((p, i) => (
        <p className="page-lead analog-prose" key={i}>{p}</p>
      ))}
      <div className="panel analog-panel">
        <div className="table-wrap">
          <table className="win-table analog-table two-col">
            <thead>
              <tr>
                <th className="left">{C.BREAKS_HEADING}</th>
                <th className="left">{C.CONFIRMED_HEADING}</th>
              </tr>
            </thead>
            <tbody>
              {C.BREAKS_CONFIRMED.map(([bull, bear], i) => (
                <tr key={i}>
                  <td className="left">{bull}</td>
                  <td className="left">{bear}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="page-lead analog-prose">{C.CAVEATS}</p>
      <p className="tiny muted analog-prose">{C.DISCLOSURE}</p>
      <p className="analog-prose"><strong>{C.NOT_ADVICE}</strong></p>
      <p className="muted analog-byline">{C.BYLINE}</p>
    </div>
  );
}

/** Route target: loads data/analog_2018.json and renders the page. */
export function Analog2018() {
  const [doc, setDoc] = useState<AnalogDoc | null | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    loadAnalog2018().then((d) => {
      if (alive) setDoc(d);
    });
    return () => {
      alive = false;
    };
  }, []);
  if (doc === undefined) return <div className="loading">Loading the 4Q'18 analog…</div>;
  return <Analog2018View doc={doc} />;
}
