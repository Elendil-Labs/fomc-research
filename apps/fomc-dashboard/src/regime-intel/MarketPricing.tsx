import type { MarketPricingDoc } from "../types";
import { netLeanColor } from "../lib/regime";
import { shortDate } from "../lib/format";

// Market-priced Fed path. Third hard-data read, deterministic from FRED: what rates
// markets actually PRICE for Fed policy (2y momentum, curve slope, 2y-vs-funds gap,
// net liquidity). The market can disagree with both the news lean and the balance
// sheet — this tile makes that disagreement visible. Rendered as its own panel, NOT
// as a third axis on the two-axis quadrant.

function signalMark(s: number): string {
  return s > 0 ? "↑ tightening" : s < 0 ? "↓ loosening" : "– neutral";
}

/** The NET_LIQUIDITY indicator carries change_90d in $M; display it in $B. */
function netLiquidityB(changeM: number | undefined): string {
  if (changeM === undefined || Number.isNaN(changeM)) return "—";
  const b = changeM / 1000;
  return `${b >= 0 ? "+" : ""}${b.toLocaleString("en-US", { maximumFractionDigits: 0 })} $B`;
}

export function MarketPricing({ doc }: { doc: MarketPricingDoc | null }) {
  if (!doc) {
    return (
      <div className="panel">
        <div className="qs-row">
          <span className="label">Market-priced Fed path</span>
          <span className="v" style={{ color: "var(--muted)" }}>—</span>
        </div>
        <div className="tiny muted" style={{ marginTop: 8 }}>
          Market-pricing axis populates on the next scheduled data run (FRED, deterministic).
        </div>
      </div>
    );
  }

  const net = doc.net_lean;
  const netLiq = doc.indicators.find((i) => i.id === "NET_LIQUIDITY");

  return (
    <div className="panel">
      <div className="qs-row">
        <span className="label">Market-priced Fed path</span>
        <span className="v" style={{ color: netLeanColor(net) }}>
          {net >= 0 ? "+" : ""}{net.toFixed(2)} ({doc.label})
        </span>
      </div>
      <table className="bs-indicators">
        <tbody>
          {doc.indicators.map((ind) => (
            <tr key={ind.id}>
              <td className="left">{ind.name}</td>
              <td className="left muted">{ind.detail}</td>
              <td
                className="left"
                style={
                  ind.latest === null || ind.latest === undefined
                    ? { color: "var(--muted)", whiteSpace: "nowrap" }
                    : { color: netLeanColor(ind.signal), whiteSpace: "nowrap" }
                }
              >
                {ind.latest === null || ind.latest === undefined ? "—" : signalMark(ind.signal)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {netLiq && netLiq.latest !== null && (
        <div className="qs-row" style={{ marginTop: 6 }}>
          <span className="label">Net liquidity Δ90d</span>
          <span className="v" style={{ color: netLeanColor(netLiq.signal) }}>
            {netLiquidityB(netLiq.change_90d)}
          </span>
        </div>
      )}
      {doc.coverage !== undefined && doc.coverage < 1 && (
        <div className="tiny muted" style={{ marginTop: 6 }}>
          Degraded read: only {Math.round(doc.coverage * 100)}% of indicator weight produced
          data — lean is computed over the live indicators only.
        </div>
      )}
      <div className="tiny muted" style={{ marginTop: 6 }}>
        Market-pricing axis: {doc.source} · deterministic, no LLM · {shortDate(doc.generated_at)}
      </div>
    </div>
  );
}
