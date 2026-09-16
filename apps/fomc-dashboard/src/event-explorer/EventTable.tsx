import { useMemo, useState } from "react";
import type { FomcEvent } from "../types";
import { classifyColor, COLOR_META } from "../lib/colorDay";
import { pct, shortDate, signClass } from "../lib/format";
import { sortBy, type SortDir } from "../lib/sort";

type Col = {
  key: keyof FomcEvent;
  label: string;
  left?: boolean;
  numeric?: boolean;
};

const COLS: Col[] = [
  { key: "date", label: "Date", left: true },
  { key: "chair", label: "Chair", left: true },
  { key: "regime", label: "Regime", left: true },
  { key: "action", label: "Action", left: true },
  { key: "spy_d0", label: "SPY d0", numeric: true },
  { key: "spy_p1", label: "SPY +1", numeric: true },
  { key: "spy_p3", label: "SPY +3", numeric: true },
  { key: "spy_p5", label: "SPY +5", numeric: true },
  { key: "spy_p10", label: "SPY +10", numeric: true },
  { key: "tlt_d0", label: "TLT d0", numeric: true },
  { key: "tlt_p1", label: "TLT +1", numeric: true },
  { key: "tlt_p3", label: "TLT +3", numeric: true },
  { key: "tlt_p5", label: "TLT +5", numeric: true },
  { key: "tlt_p10", label: "TLT +10", numeric: true },
];

export function EventTable({
  events,
  onSelect,
}: {
  events: FomcEvent[];
  onSelect: (e: FomcEvent) => void;
}) {
  const [sortKey, setSortKey] = useState<keyof FomcEvent>("date");
  const [dir, setDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => sortBy(events, sortKey, dir), [events, sortKey, dir]);

  const clickHeader = (key: keyof FomcEvent) => {
    if (key === sortKey) setDir(dir === "asc" ? "desc" : "asc");
    else {
      setSortKey(key);
      setDir(key === "date" ? "desc" : "asc");
    }
  };

  return (
    <div className="table-wrap">
      <table className="events">
        <thead>
          <tr>
            <th className="left">Color</th>
            {COLS.map((c) => (
              <th
                key={String(c.key)}
                className={[c.left ? "left" : "", c.key === "tlt_d0" ? "group-start" : ""]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => clickHeader(c.key)}
                aria-sort={sortKey === c.key ? (dir === "asc" ? "ascending" : "descending") : "none"}
              >
                {c.label}
                {sortKey === c.key && <span className="sort-ind">{dir === "asc" ? "▲" : "▼"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((e) => {
            const color = classifyColor(e.spy_d0, e.tlt_d0);
            return (
              <tr key={e.date} onClick={() => onSelect(e)}>
                <td className="left">
                  {color ? (
                    <span title={COLOR_META[color].label}>
                      <span className="dot" style={{ background: COLOR_META[color].hex }} />
                      {COLOR_META[color].name}
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                {COLS.map((c) => {
                  const v = e[c.key];
                  if (c.numeric) {
                    const cls = [signClass(v as number), c.key === "tlt_d0" ? "group-start" : ""]
                      .filter(Boolean)
                      .join(" ");
                    return (
                      <td key={String(c.key)} className={cls}>
                        {pct(v as number)}
                      </td>
                    );
                  }
                  return (
                    <td key={String(c.key)} className="left">
                      {c.key === "date" ? shortDate(e.date) : (v as string)}
                      {c.key === "date" && e.emergency ? <span title="emergency"> *</span> : null}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
