import type { IntelSource } from "../types";
import { BUCKET_META, CLAIM_TYPE_META, DIRECTION_META } from "../lib/regime";
import { shortDate } from "../lib/format";
import { toCsv } from "../lib/csv";

function download(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function EvidenceMatrix({ sources }: { sources: IntelSource[] }) {
  const rows = sources
    .slice()
    .sort((a, b) => b.published_at.localeCompare(a.published_at));

  const exportJson = () =>
    download("regime_evidence.json", JSON.stringify(sources, null, 2), "application/json");

  const exportCsv = () => {
    const header = [
      "date",
      "publisher",
      "bucket",
      "direction",
      "claim_type",
      "importance",
      "confidence",
      "evidence",
      "url",
    ];
    const data = rows.map((s) => [
      s.published_at,
      s.publisher,
      s.bucket,
      s.direction,
      s.claim_type ?? "",
      s.importance,
      s.confidence,
      s.evidence_text,
      s.url,
    ]);
    download("regime_evidence.csv", toCsv(header, data), "text/csv");
  };

  return (
    <div>
      <div className="toolbar">
        <button className="btn" onClick={exportJson}>
          Export JSON
        </button>
        <button className="btn" onClick={exportCsv}>
          Export CSV
        </button>
      </div>
      <div className="table-wrap panel" style={{ padding: 6 }}>
        <table className="events">
          <thead>
            <tr>
              <th className="left">Date</th>
              <th className="left">Source</th>
              <th className="left">Bucket</th>
              <th className="left">Direction</th>
              <th className="left">Tier</th>
              <th className="left">Importance</th>
              <th className="left">Evidence</th>
              <th className="left">Link</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id}>
                <td className="left">{shortDate(s.published_at)}</td>
                <td className="left">{s.publisher}</td>
                <td className="left">{BUCKET_META[s.bucket].label}</td>
                <td className="left" style={{ color: DIRECTION_META[s.direction].color }}>
                  {DIRECTION_META[s.direction].label}
                </td>
                <td className="left" style={{ color: s.claim_type ? CLAIM_TYPE_META[s.claim_type].color : undefined }}>
                  {s.claim_type ? CLAIM_TYPE_META[s.claim_type].label : "—"}
                </td>
                <td className="left">{s.importance}</td>
                <td className="left" style={{ whiteSpace: "normal", maxWidth: 360 }}>
                  {s.evidence_text}
                </td>
                <td className="left">
                  <a href={s.url} target="_blank" rel="noopener noreferrer">
                    ↗
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
