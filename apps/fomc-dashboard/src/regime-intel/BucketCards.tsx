import type { Bucket, IntelSource, RegimeIntelDocument } from "../types";
import { BUCKET_META, DIRECTION_META, leanColor } from "../lib/regime";

const ORDER: Array<keyof RegimeIntelDocument["bucket_scores"]> = [
  "fed_communications",
  "inflation",
  "market_pricing",
  "employment",
];

/** Top 2-4 evidence snippets for a bucket, most important/recent first. */
function topEvidence(sources: IntelSource[], bucket: Bucket): IntelSource[] {
  const rank = { high: 3, medium: 2, low: 1 } as const;
  return sources
    .filter((s) => s.bucket === bucket)
    .sort((a, b) => {
      const r = rank[b.importance] - rank[a.importance];
      return r !== 0 ? r : b.published_at.localeCompare(a.published_at);
    })
    .slice(0, 4);
}

function counts(sources: IntelSource[], bucket: Bucket) {
  const c = { easing: 0, neutral: 0, tightening: 0 };
  for (const s of sources) if (s.bucket === bucket) c[s.direction] += 1;
  return c;
}

export function BucketCards({ doc }: { doc: RegimeIntelDocument }) {
  return (
    <div className="bucket-row">
      {ORDER.map((key) => {
        const bl = doc.bucket_scores[key];
        const color = leanColor(bl.dominant);
        const c = counts(doc.sources, key);
        const evidence = topEvidence(doc.sources, key);
        return (
          <div className="bucket panel" key={key}>
            <div className="head">
              <strong>{BUCKET_META[key].label}</strong>
              <span className="lean-pill" style={{ color, background: `${color}22` }}>
                {DIRECTION_META[bl.dominant].label}
              </span>
            </div>
            <div className="tiny muted">{bl.label}</div>

            {/* weighted share split (easing | neutral | tightening) */}
            <div className="balance-bar small">
              <div
                className="balance-seg"
                style={{ width: `${bl.shares.easing * 100}%`, background: DIRECTION_META.easing.color }}
              />
              <div
                className="balance-seg"
                style={{ width: `${bl.shares.neutral * 100}%`, background: DIRECTION_META.neutral.color }}
              />
              <div
                className="balance-seg"
                style={{ width: `${bl.shares.tightening * 100}%`, background: DIRECTION_META.tightening.color }}
              />
            </div>
            <div className="tiny muted">
              {bl.n} source{bl.n === 1 ? "" : "s"} · {c.tightening} tightening / {c.neutral} mixed /{" "}
              {c.easing} easing
            </div>

            <ul>
              {evidence.length === 0 && <li className="muted">No evidence yet.</li>}
              {evidence.map((s) => (
                <li key={s.id}>
                  {s.evidence_text}{" "}
                  <a href={s.url} target="_blank" rel="noopener noreferrer" title={s.publisher}>
                    ↗
                  </a>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
