import type { RegimeIntelDocument } from "../types";

export function NarrativeSummary({ doc }: { doc: RegimeIntelDocument }) {
  return (
    <div className="narrative panel">
      <div className="bottom-line">{doc.summary}</div>
      {doc.what_would_change_the_call.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop: 14 }}>
            What would change the call
          </div>
          <ul>
            {doc.what_would_change_the_call.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </>
      )}
      <p className="tiny muted" style={{ marginTop: 12 }}>
        Every claim above is backed by a source card below. This is an evidence-weighted regime-risk
        read, not a prediction or investment advice.
      </p>
    </div>
  );
}
