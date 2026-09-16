import { useEffect } from "react";
import type { FomcEvent } from "../types";
import { FORWARD_HORIZONS } from "../types";
import { colorInfo, COLOR_META } from "../lib/colorDay";
import { num, pct, shortDate, signClass } from "../lib/format";

export function EventDrawer({
  event,
  onClose,
}: {
  event: FomcEvent | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!event) return null;
  const ci = colorInfo(event);

  const spyFwd = FORWARD_HORIZONS.map((h) => event[`spy_p${h}` as keyof FomcEvent] as number | null);
  const tltFwd = FORWARD_HORIZONS.map((h) => event[`tlt_p${h}` as keyof FomcEvent] as number | null);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={`FOMC event ${event.date}`}>
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <div className="muted tiny">FOMC decision</div>
        <h2>{shortDate(event.date)}</h2>
        <div>
          {ci ? (
            <span>
              <span className="dot" style={{ background: ci.hex }} />
              <strong>{COLOR_META[ci.color].name}</strong> · {ci.label}
            </span>
          ) : (
            <span className="muted">No decision-day data</span>
          )}
        </div>

        <dl className="kv">
          <dt>Chair</dt>
          <dd>{event.chair}</dd>
          <dt>Regime</dt>
          <dd>{event.regime || "—"}</dd>
          <dt>Action</dt>
          <dd>{event.action || "—"}</dd>
          <dt>FF target</dt>
          <dd>{event.ff_target || "—"}</dd>
          <dt>Emergency</dt>
          <dd>{event.emergency ? "Yes" : "No"}</dd>
          <dt>SPY close</dt>
          <dd>{num(event.spy_close)}</dd>
          <dt>TLT close</dt>
          <dd>{num(event.tlt_close)}</dd>
          <dt>SPY pre-5d</dt>
          <dd className={signClass(event.spy_pre5)}>{pct(event.spy_pre5)}</dd>
          <dt>TLT pre-5d</dt>
          <dd className={signClass(event.tlt_pre5)}>{pct(event.tlt_pre5)}</dd>
        </dl>

        <div className="section-title" style={{ marginTop: 8 }}>
          Forward windows (% from decision-day close)
        </div>
        <table className="win-table">
          <thead>
            <tr>
              <th className="left">Asset</th>
              <th>d0</th>
              {FORWARD_HORIZONS.map((h) => (
                <th key={h}>+{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="left">SPY</td>
              <td className={signClass(event.spy_d0)}>{pct(event.spy_d0)}</td>
              {spyFwd.map((v, i) => (
                <td key={i} className={signClass(v)}>
                  {pct(v)}
                </td>
              ))}
            </tr>
            <tr>
              <td className="left">TLT</td>
              <td className={signClass(event.tlt_d0)}>{pct(event.tlt_d0)}</td>
              {tltFwd.map((v, i) => (
                <td key={i} className={signClass(v)}>
                  {pct(v)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
        <p className="tiny muted" style={{ marginTop: 14 }}>
          "—" marks a forward window that has not completed yet (e.g. the most recent meeting has
          no +10 session data).
        </p>
      </aside>
    </>
  );
}
