import type { BalanceSheetDoc, RegimeIntelDocument } from "../types";
import { netLeanColor } from "../lib/regime";
import { shortDate } from "../lib/format";

// Two-axis regime map. The policy/communications lean (news vote-share) is one axis;
// the balance-sheet / liquidity stance (FRED, deterministic) is the orthogonal axis.
// The point of the chart: catch the Warsh-type divergence — the Fed easing on the rate
// while liquidity / collateral tightens via the balance sheet.

const W = 360;
const H = 340;
const PAD = 46;

function x(bs: number): number {
  const c = Math.max(-1, Math.min(1, bs));
  return PAD + ((c + 1) / 2) * (W - 2 * PAD);
}
function y(rate: number): number {
  const c = Math.max(-1, Math.min(1, rate)); // tightening up
  return H - PAD - ((c + 1) / 2) * (H - 2 * PAD);
}

function signalMark(s: number): string {
  return s > 0 ? "↑ tightening" : s < 0 ? "↓ loosening" : "– neutral";
}

export function RegimeQuadrant({
  doc,
  bs,
}: {
  doc: RegimeIntelDocument;
  bs: BalanceSheetDoc | null;
}) {
  const rateNet = doc.net_lean;
  const bsNet = bs?.net_lean ?? 0;
  const fedEasing = (doc.current_repo_regime || "").toLowerCase() === "easing";
  const fedTightening = (doc.current_repo_regime || "").toLowerCase() === "tightening";
  // "Bifurcated" = the Fed's stated stance and the balance sheet disagree.
  const divergence =
    bs &&
    ((fedEasing && bsNet >= 0.25) || (fedTightening && bsNet <= -0.25));

  return (
    <div>
      {divergence && (
        <div className="divergence-banner">
          ⚠ <strong>Divergence (bifurcated setup):</strong> the Fed's stated regime is{" "}
          <strong>{doc.current_repo_regime}</strong>, but the balance-sheet / liquidity data is{" "}
          <strong>{bs!.label}</strong>. Rate path and financial-conditions stance are pulling in
          opposite directions — easing for Main Street, tightening for levered/Wall-Street
          collateral.
        </div>
      )}

      <div className="quadrant-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Two-axis regime map">
          {/* quadrant fills */}
          <rect x={PAD} y={PAD} width={(W - 2 * PAD) / 2} height={(H - 2 * PAD) / 2} fill="#f59e0b11" />
          <rect x={W / 2} y={PAD} width={(W - 2 * PAD) / 2} height={(H - 2 * PAD) / 2} fill="#ef444411" />
          <rect x={PAD} y={H / 2} width={(W - 2 * PAD) / 2} height={(H - 2 * PAD) / 2} fill="#22c55e11" />
          <rect x={W / 2} y={H / 2} width={(W - 2 * PAD) / 2} height={(H - 2 * PAD) / 2} fill="#f59e0b18" />
          {/* axes */}
          <line x1={PAD} y1={H / 2} x2={W - PAD} y2={H / 2} stroke="#33415588" />
          <line x1={W / 2} y1={PAD} x2={W / 2} y2={H - PAD} stroke="#33415588" />
          {/* quadrant labels */}
          <text x={W / 2 - 8} y={PAD + 16} fill="#6b7a90" fontSize="10" textAnchor="end">Rate-led tightening</text>
          <text x={W / 2 + 8} y={PAD + 16} fill="#ff9d9d" fontSize="10">Full tightening</text>
          <text x={W / 2 - 8} y={H - PAD - 8} fill="#7ee2a8" fontSize="10" textAnchor="end">Full easing</text>
          <text x={W / 2 + 8} y={H - PAD - 8} fill="#ffd591" fontSize="10">Bifurcated</text>
          {/* axis captions */}
          <text x={W / 2} y={H - 12} fill="#93a1b5" fontSize="11" textAnchor="middle">Balance sheet / liquidity →</text>
          <text x={16} y={H / 2} fill="#93a1b5" fontSize="11" textAnchor="middle" transform={`rotate(-90 16 ${H / 2})`}>Policy &amp; news lean →</text>
          <text x={PAD} y={H - PAD + 14} fill="#6b7a90" fontSize="9">loosening</text>
          <text x={W - PAD} y={H - PAD + 14} fill="#6b7a90" fontSize="9" textAnchor="end">tightening</text>
          {/* the point */}
          <circle cx={x(bsNet)} cy={y(rateNet)} r={7} fill="#5b9dff" stroke="#0b0f17" strokeWidth={2}>
            <title>{`policy/news ${rateNet >= 0 ? "+" : ""}${rateNet.toFixed(2)} · balance sheet ${bsNet >= 0 ? "+" : ""}${bsNet.toFixed(2)}`}</title>
          </circle>
        </svg>

        <div className="quadrant-side">
          <div className="qs-row">
            <span className="label">Policy &amp; news lean</span>
            <span className="v" style={{ color: netLeanColor(rateNet) }}>
              {rateNet >= 0 ? "+" : ""}{rateNet.toFixed(2)} ({doc.inferred_regime})
            </span>
          </div>
          <div className="qs-row">
            <span className="label">Balance sheet / liquidity</span>
            <span className="v" style={{ color: bs ? netLeanColor(bsNet) : "var(--muted)" }}>
              {bs ? `${bsNet >= 0 ? "+" : ""}${bsNet.toFixed(2)} (${bs.label})` : "—"}
            </span>
          </div>
          <div className="qs-row">
            <span className="label">Fed's stated regime</span>
            <span className="v">{doc.current_repo_regime}</span>
          </div>
          {bs && (
            <table className="bs-indicators">
              <tbody>
                {bs.indicators.map((ind) => (
                  <tr key={ind.id}>
                    <td className="left">{ind.name}</td>
                    <td className="left muted">{ind.detail}</td>
                    <td
                      className="left"
                      style={{ color: netLeanColor(ind.signal), whiteSpace: "nowrap" }}
                    >
                      {signalMark(ind.signal)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {bs ? (
            <div className="tiny muted" style={{ marginTop: 6 }}>
              Balance-sheet axis: {bs.source} · deterministic, no LLM · {shortDate(bs.generated_at)}
            </div>
          ) : (
            <div className="tiny muted" style={{ marginTop: 8 }}>
              Balance-sheet axis populates on the next scheduled data run (FRED, deterministic).
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
