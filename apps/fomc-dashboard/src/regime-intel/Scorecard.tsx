import type { RegimeIntelDocument } from "../types";
import { descriptorColor, DIRECTION_META, pctShare } from "../lib/regime";
import { shortDate } from "../lib/format";

/** Stacked 3-way bar: easing | neutral | tightening, widths = weighted evidence shares. */
function EvidenceBalance({ shares }: { shares: RegimeIntelDocument["evidence_shares"] }) {
  const segs: Array<[keyof typeof shares, string]> = [
    ["easing", DIRECTION_META.easing.color],
    ["neutral", DIRECTION_META.neutral.color],
    ["tightening", DIRECTION_META.tightening.color],
  ];
  return (
    <div>
      <div className="balance-bar" role="img" aria-label="evidence balance">
        {segs.map(([k, color]) => (
          <div
            key={k}
            className="balance-seg"
            style={{ width: `${shares[k] * 100}%`, background: color }}
            title={`${DIRECTION_META[k].label} ${pctShare(shares[k])}`}
          />
        ))}
      </div>
      {/* order matches the bar left→right: easing (green) · mixed · tightening (red) */}
      <div className="balance-legend tiny">
        <span style={{ color: DIRECTION_META.easing.color }}>
          {pctShare(shares.easing)} easing
        </span>
        <span className="muted">{pctShare(shares.neutral)} mixed</span>
        <span style={{ color: DIRECTION_META.tightening.color }}>
          {pctShare(shares.tightening)} tightening
        </span>
      </div>
    </div>
  );
}

export function Scorecard({ doc }: { doc: RegimeIntelDocument }) {
  const color = descriptorColor(doc.inferred_regime);
  return (
    <div className="scorecard">
      <div className="big panel">
        <div className="muted tiny">Regime read</div>
        <div className="regime-label" style={{ color }}>
          {doc.inferred_regime}
        </div>
        <div className="regime-sub">
          Fed's current regime (from statements): <strong>{doc.current_repo_regime}</strong>. The
          read above is where the weighted evidence is pointing.
        </div>
        <div style={{ marginTop: 16 }}>
          <EvidenceBalance shares={doc.evidence_shares} />
        </div>
      </div>

      <div className="meta-grid panel">
        <div>
          <div className="label">Conviction</div>
          <div className="v">{doc.conviction}</div>
        </div>
        <div>
          <div className="label">Direction</div>
          <div className="v" style={{ textTransform: "capitalize" }}>
            {doc.evidence_dir}
          </div>
        </div>
        <div>
          <div className="label">Next FOMC</div>
          <div className="v">{doc.next_fomc_meeting ? shortDate(doc.next_fomc_meeting) : "—"}</div>
        </div>
        <div>
          <div className="label">Sources</div>
          <div className="v">{doc.sources.length}</div>
        </div>
        <div>
          <div className="label">Window</div>
          <div className="v" style={{ fontSize: 13 }}>
            {shortDate(doc.window_start)} → {shortDate(doc.window_end)}
          </div>
        </div>
        <div>
          <div className="label">Last updated</div>
          <div className="v" style={{ fontSize: 13 }}>
            {shortDate(doc.generated_at)}
          </div>
        </div>
      </div>
    </div>
  );
}
