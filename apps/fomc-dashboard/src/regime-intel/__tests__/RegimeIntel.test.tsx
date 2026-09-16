import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { IntelSource, RegimeIntelDocument } from "../../types";
import { filterSources } from "../NewsFeed";
import { NewsFeed } from "../NewsFeed";
import { NarrativeSummary } from "../NarrativeSummary";
import { Scorecard } from "../Scorecard";

function src(p: Partial<IntelSource>): IntelSource {
  return {
    id: "s",
    title: "t",
    publisher: "pub",
    url: "https://example.com/a",
    published_at: "2026-06-20T12:00:00Z",
    bucket: "inflation",
    direction: "tightening",
    score: 1,
    importance: "high",
    confidence: "medium",
    evidence_text: "evidence",
    why_it_matters: "matters",
    ...p,
  };
}

const sources: IntelSource[] = [
  src({ id: "a", bucket: "inflation", direction: "tightening", published_at: "2026-06-20T00:00:00Z" }),
  src({ id: "b", bucket: "employment", direction: "easing", published_at: "2026-06-22T00:00:00Z" }),
  src({ id: "c", bucket: "market_pricing", direction: "tightening", published_at: "2026-06-21T00:00:00Z" }),
];

const bl = (dominant: "easing" | "neutral" | "tightening", e: number, n: number, t: number,
            label: string, nn: number) => ({
  shares: { easing: e, neutral: n, tightening: t },
  net: Number((t - e).toFixed(2)),
  dominant,
  label,
  n: nn,
  weight_sum: 1,
});

const doc: RegimeIntelDocument = {
  generated_at: "2026-06-23T11:00:00Z",
  window_start: "2026-06-17",
  window_end: "2026-06-23",
  current_repo_regime: "Easing",
  inferred_regime: "Potential pivot → tightening",
  conviction: "High",
  evidence_shares: { easing: 0.1, neutral: 0.15, tightening: 0.75 },
  net_lean: 0.65,
  evidence_dir: "tightening",
  bucket_scores: {
    employment: bl("neutral", 0.2, 0.6, 0.2, "mixed", 2),
    inflation: bl("tightening", 0.05, 0.1, 0.85, "strongly tightening", 3),
    fed_communications: bl("tightening", 0.1, 0.2, 0.7, "leaning tightening", 4),
    market_pricing: bl("tightening", 0.1, 0.2, 0.7, "leaning tightening", 2),
  },
  summary: "Regime read: Potential pivot → tightening. Tightening risk is rising.",
  what_would_change_the_call: ["A second upside inflation surprise."],
  sources,
};

describe("filterSources", () => {
  it("returns all and sorts newest-first by default", () => {
    expect(filterSources(sources, "all", "all").map((s) => s.id)).toEqual(["b", "c", "a"]);
  });
  it("filters by bucket", () => {
    expect(filterSources(sources, "inflation", "all").map((s) => s.id)).toEqual(["a"]);
  });
  it("filters by direction", () => {
    expect(filterSources(sources, "all", "easing").map((s) => s.id)).toEqual(["b"]);
  });
  it("combines bucket and direction", () => {
    expect(filterSources(sources, "market_pricing", "tightening").map((s) => s.id)).toEqual(["c"]);
  });

  it("filters to new-only when requested", () => {
    const withNew = [src({ id: "n", is_new: true }), src({ id: "old", is_new: false })];
    expect(filterSources(withNew, "all", "all", true).map((s) => s.id)).toEqual(["n"]);
    expect(filterSources(withNew, "all", "all", false)).toHaveLength(2);
  });
});

describe("NarrativeSummary", () => {
  it("renders the summary and what-would-change list", () => {
    render(<NarrativeSummary doc={doc} />);
    expect(screen.getByText(/Tightening risk is rising/)).toBeInTheDocument();
    expect(screen.getByText(/second upside inflation surprise/)).toBeInTheDocument();
  });
});

describe("Scorecard", () => {
  it("shows the 4-state descriptor, conviction, and evidence balance", () => {
    render(<Scorecard doc={doc} />);
    expect(screen.getByText("Potential pivot → tightening")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument(); // conviction
    expect(screen.getByText("75% tightening")).toBeInTheDocument(); // evidence balance
  });
});

describe("NewsFeed", () => {
  it("renders every source with a visible source link", () => {
    render(<NewsFeed sources={sources} />);
    const links = screen.getAllByRole("link");
    expect(links.length).toBeGreaterThanOrEqual(sources.length);
    links.forEach((a) => expect(a.getAttribute("href")).toMatch(/^https:\/\//));
  });

  it("filters the feed by bucket selection", () => {
    render(<NewsFeed sources={sources} />);
    const [bucketSelect] = screen.getAllByRole("combobox");
    fireEvent.change(bucketSelect, { target: { value: "inflation" } });
    expect(screen.getByText(/^1 sources/)).toBeInTheDocument();
  });

  it("shows NEW badges and a new-since-last-run count", () => {
    const withNew = [src({ id: "n", is_new: true }), ...sources];
    render(<NewsFeed sources={withNew} />);
    expect(screen.getByText("NEW")).toBeInTheDocument();
    expect(screen.getByText(/1 new since last run/)).toBeInTheDocument();
  });

  it("shows the evidentiary-tier (claim_type) badge", () => {
    render(<NewsFeed sources={[src({ id: "ct", claim_type: "official_data" })]} />);
    expect(screen.getByText("official data")).toBeInTheDocument();
  });
});
