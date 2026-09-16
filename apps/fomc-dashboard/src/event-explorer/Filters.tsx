import { ALL_COLORS, COLOR_META, type ColorDay } from "../lib/colorDay";

export interface FilterState {
  regimes: Set<string>;
  actions: Set<string>;
  chairs: Set<string>;
  colors: Set<ColorDay>;
}

export const emptyFilters = (): FilterState => ({
  regimes: new Set(),
  actions: new Set(),
  chairs: new Set(),
  colors: new Set(),
});

export function filtersActive(f: FilterState): boolean {
  return f.regimes.size + f.actions.size + f.chairs.size + f.colors.size > 0;
}

function toggle<T>(set: Set<T>, v: T): Set<T> {
  const next = new Set(set);
  if (next.has(v)) next.delete(v);
  else next.add(v);
  return next;
}

interface Props {
  filters: FilterState;
  regimes: string[];
  actions: string[];
  chairs: string[];
  onChange: (f: FilterState) => void;
}

export function Filters({ filters, regimes, actions, chairs, onChange }: Props) {
  const group = (
    legend: string,
    values: string[],
    key: "regimes" | "actions" | "chairs",
  ) => (
    <div className="filter-group">
      <span className="legend">{legend}</span>
      <div className="chips">
        {values.map((v) => (
          <button
            key={v}
            className={filters[key].has(v) ? "chip on" : "chip"}
            onClick={() => onChange({ ...filters, [key]: toggle(filters[key], v) })}
          >
            {v}
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="filters panel">
      {group("Regime", regimes, "regimes")}
      {group("Action", actions, "actions")}
      {group("Chair", chairs, "chairs")}
      <div className="filter-group">
        <span className="legend">Color day</span>
        <div className="chips">
          {ALL_COLORS.map((c: ColorDay) => {
            const on = filters.colors.has(c);
            return (
              <button
                key={c}
                className={on ? "chip color-chip on" : "chip color-chip"}
                style={on ? { background: COLOR_META[c].hex, borderColor: COLOR_META[c].hex } : {}}
                onClick={() => onChange({ ...filters, colors: toggle(filters.colors, c) })}
                title={COLOR_META[c].label}
              >
                {COLOR_META[c].name}
              </button>
            );
          })}
        </div>
      </div>
      {filtersActive(filters) && (
        <button className="reset-btn" onClick={() => onChange(emptyFilters())}>
          Reset filters
        </button>
      )}
    </div>
  );
}
