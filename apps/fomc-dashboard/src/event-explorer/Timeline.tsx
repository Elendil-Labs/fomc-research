import type { FomcEvent } from "../types";
import { classifyColor, COLOR_META } from "../lib/colorDay";
import { shortDate } from "../lib/format";

/** A compact dot strip: one square per event, colored by its color-day. */
export function Timeline({
  events,
  onSelect,
}: {
  events: FomcEvent[];
  onSelect: (e: FomcEvent) => void;
}) {
  return (
    <div className="timeline panel">
      {events.map((e) => {
        const c = classifyColor(e.spy_d0, e.tlt_d0);
        return (
          <button
            key={e.date}
            className={c ? "tl-dot" : "tl-dot none"}
            style={c ? { background: COLOR_META[c].hex } : {}}
            title={`${shortDate(e.date)} · ${e.chair} · ${e.action}${c ? ` · ${COLOR_META[c].label}` : ""}`}
            aria-label={`${e.date} ${c ?? "no data"}`}
            onClick={() => onSelect(e)}
          />
        );
      })}
    </div>
  );
}
