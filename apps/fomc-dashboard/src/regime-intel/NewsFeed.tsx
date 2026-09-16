import { useMemo, useState } from "react";
import type { Bucket, Direction, IntelSource } from "../types";
import { BUCKET_META, CLAIM_TYPE_META, DIRECTION_META } from "../lib/regime";
import { ageLabel, shortDate } from "../lib/format";

const BUCKETS: Bucket[] = ["employment", "inflation", "fed_communications", "market_pricing", "other"];
const DIRECTIONS: Direction[] = ["easing", "neutral", "tightening"];

/** Pure filter — exported for tests. */
export function filterSources(
  sources: IntelSource[],
  bucket: Bucket | "all",
  direction: Direction | "all",
  newOnly = false,
): IntelSource[] {
  return sources
    .filter((s) => bucket === "all" || s.bucket === bucket)
    .filter((s) => direction === "all" || s.direction === direction)
    .filter((s) => !newOnly || s.is_new)
    .slice()
    .sort((a, b) => b.published_at.localeCompare(a.published_at));
}

export function NewsFeed({ sources }: { sources: IntelSource[] }) {
  const [bucket, setBucket] = useState<Bucket | "all">("all");
  const [direction, setDirection] = useState<Direction | "all">("all");
  const [newOnly, setNewOnly] = useState(false);

  const newCount = useMemo(() => sources.filter((s) => s.is_new).length, [sources]);
  const shown = useMemo(
    () => filterSources(sources, bucket, direction, newOnly),
    [sources, bucket, direction, newOnly],
  );

  return (
    <div>
      <div className="toolbar">
        <select value={bucket} onChange={(e) => setBucket(e.target.value as Bucket | "all")}>
          <option value="all">All buckets</option>
          {BUCKETS.map((b) => (
            <option key={b} value={b}>
              {BUCKET_META[b].label}
            </option>
          ))}
        </select>
        <select
          value={direction}
          onChange={(e) => setDirection(e.target.value as Direction | "all")}
        >
          <option value="all">All directions</option>
          {DIRECTIONS.map((d) => (
            <option key={d} value={d}>
              {DIRECTION_META[d].label}
            </option>
          ))}
        </select>
        <label className="new-toggle tiny" title="Show only sources first seen in the latest run">
          <input
            type="checkbox"
            checked={newOnly}
            onChange={(e) => setNewOnly(e.target.checked)}
            disabled={newCount === 0}
          />
          New only
        </label>
        <span className="muted tiny">
          {shown.length} sources{newCount > 0 && <> · {newCount} new since last run</>}
        </span>
      </div>

      <div className="feed">
        {shown.length === 0 && <div className="empty-state">No sources match this filter.</div>}
        {shown.map((s) => (
          <article
            className="source-card panel"
            key={s.id}
            style={{ borderLeftColor: DIRECTION_META[s.direction].color }}
          >
            <div className="row1">
              {s.is_new && <span className="badge new" title="First seen in the latest run">NEW</span>}
              <span className="title">{s.title}</span>
              <span className={s.official ? "badge official" : "badge news"}>
                {s.official ? "Official" : "News"}
              </span>
              <span className={`badge imp-${s.importance}`}>{s.importance}</span>
              {s.claim_type && (
                <span
                  className="badge claim"
                  style={{
                    color: CLAIM_TYPE_META[s.claim_type].color,
                    borderColor: CLAIM_TYPE_META[s.claim_type].color,
                  }}
                  title="Evidentiary tier — facts/official data weigh more than scenarios/opinion"
                >
                  {CLAIM_TYPE_META[s.claim_type].label}
                </span>
              )}
              <span className="badge" style={{ color: DIRECTION_META[s.direction].color }}>
                {DIRECTION_META[s.direction].label}
              </span>
              <span className="muted tiny">{BUCKET_META[s.bucket].label}</span>
            </div>
            <div className="tiny muted">
              {s.publisher} · {shortDate(s.published_at)} · {ageLabel(s.published_at)}
            </div>
            <div>{s.evidence_text}</div>
            <div className="why tiny">
              <strong>Why it matters:</strong> {s.why_it_matters}
            </div>
            <a href={s.url} target="_blank" rel="noopener noreferrer" className="tiny">
              {s.url}
            </a>
          </article>
        ))}
      </div>
    </div>
  );
}
