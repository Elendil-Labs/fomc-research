import type { ChecklistItem, SpyTltSignal } from "../types";

const STATUS_LABEL: Record<ChecklistItem["status"], string> = {
  confirmed: "Confirmed",
  partial: "Partial",
  not_confirmed: "Not confirmed",
  unknown: "Unknown",
};

const pct = (r: number) => `${r >= 0 ? "+" : ""}${(r * 100).toFixed(1)}%`;

export function RegimeChecklist({
  items,
  spytlt,
}: {
  items: ChecklistItem[];
  spytlt?: SpyTltSignal | null;
}) {
  if (!items.length) {
    return <div className="empty-state">No checklist available.</div>;
  }
  return (
    <ul className="checklist panel">
      {items.map((it) => (
        <li key={it.id}>
          <span className={`status st-${it.status}`}>{STATUS_LABEL[it.status]}</span>
          <span>
            {it.text}
            {it.id === "spytlt_confirms" && spytlt && (
              <span className="muted">
                {" "}
                (SPY {pct(spytlt.spy_ret)} / TLT {pct(spytlt.tlt_ret)} over {spytlt.window_days}d)
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
