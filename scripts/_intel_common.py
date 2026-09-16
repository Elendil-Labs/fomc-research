"""Shared helpers for the regime-intelligence pipeline (collect + score).

Kept dependency-light (stdlib only) so the GitHub Action needs nothing beyond the
repo's own packages. Both scripts run as `python scripts/<name>.py`, so this module
sits on sys.path[0] and imports as `import _intel_common`.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths

REPO = Path(__file__).resolve().parents[1]  # repo root (scripts/ -> ..)
DASHBOARD_DATA = REPO / "apps" / "fomc-dashboard" / "public" / "data"
INTEL_DIR = DASHBOARD_DATA / "regime_intel"
HISTORY_DIR = INTEL_DIR / "history"

EVENT_TRUTH_JSON = DASHBOARD_DATA / "fomc_event_truth.json"
SOURCES_JSONL = INTEL_DIR / "sources.jsonl"
LATEST_RAW = INTEL_DIR / "latest_raw.json"
LATEST = INTEL_DIR / "latest.json"
HISTORY_SERIES = INTEL_DIR / "history.json"

# ---------------------------------------------------------------- env

def _read_env_file(env_path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_api_key(*names: str) -> str | None:
    """Resolve a Perplexity key by name, preferring this project's fomc-specific key.

    Tries each candidate name in order, checking the process env (CI secrets) then a
    local .env then the parent directory's .env. Defaults to PPLX_API_KEY_fomc with a fallback
    to the generic PPLX_API_KEY, so a shared repo can hold separate keys per workflow.
    """
    if not names:
        names = ("PPLX_API_KEY_fomc", "PPLX_API_KEY")
    env_files = [_read_env_file(REPO / ".env"), _read_env_file(REPO.parent / ".env")]
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
        for env_map in env_files:
            if env_map.get(name):
                return env_map[name]
    return None


# ---------------------------------------------------------------- schema / buckets

BUCKETS = ("employment", "inflation", "fed_communications", "market_pricing", "other")
DIRECTIONS = ("easing", "neutral", "tightening")
IMPORTANCES = ("low", "medium", "high")
CONFIDENCES = ("low", "medium", "high")
# Evidentiary tier — what KIND of claim this is, most → least authoritative. Separates
# documented fact from narrative so the score isn't swayed by punditry (the "factual vs
# interpretive" discipline). Distinct from source tier (WHO published it).
CLAIM_TYPES = ("documented_fact", "official_data", "sell_side_scenario", "interpretation")

# Recency-weight scoring inputs (plan rubric).
BUCKET_WEIGHTS = {
    "fed_communications": 0.35,
    "inflation": 0.30,
    "market_pricing": 0.20,
    "employment": 0.15,
}

# Publishers we treat as official primary sources (badge + never decayed below 0.25).
OFFICIAL_HINTS = (
    "federal reserve", "fomc", "bureau of labor", "bls", "bureau of economic", "bea",
    "treasury", "fred", "st. louis fed", "stlouisfed", "cme", "fedwatch",
    "department of labor", "dol",
)

# Source tiers — how much an item's vote counts. The Fed's own words outrank official
# data, which outranks news/commentary. This is the "elevate Fed statements over a
# random blog" lever; combined multiplicatively with importance/confidence/recency.
TIER_FED_HINTS = ("federalreserve.gov", "fomc", "federal reserve", "kevin warsh", "jerome powell")
TIER_OFFICIAL_HINTS = (
    "bureau of labor", "bls", "bureau of economic", "bea", "treasury", "fred",
    "st. louis fed", "stlouisfed", "cme", "fedwatch", "department of labor", "dol",
)
TIER_WEIGHTS = {"fed": 2.0, "official": 1.5, "news": 1.0}


def source_tier(publisher: str, url: str) -> str:
    hay = f"{publisher} {url}".lower()
    if any(h in hay for h in TIER_FED_HINTS):
        return "fed"
    if any(h in hay for h in TIER_OFFICIAL_HINTS):
        return "official"
    return "news"

# Query groups handed to the search model, one prompt per probe.
QUERY_GROUPS: dict[str, list[str]] = {
    "employment": [
        "latest US employment data payrolls unemployment wages Federal Reserve policy implications",
        "weekly jobless claims labor market cooling wages Fed cuts hikes",
        "US labor market news Fed policy",
    ],
    "inflation": [
        "latest CPI PCE inflation price stability Fed policy implications",
        "core services inflation shelter wages inflation expectations Federal Reserve",
        "inflation surprise Fed cuts priced out",
    ],
    "fed_communications": [
        "Federal Reserve speech inflation employment monetary policy this week",
        "FOMC statement press conference cuts hikes inflation labor market",
        "Federal Reserve minutes inflation employment price stability",
    ],
    "market_pricing": [
        "Fed funds futures cuts priced out hikes priced in 2 year Treasury CME FedWatch",
        "OIS Fed policy path next FOMC meeting cuts hikes",
        "2 year Treasury yields Fed policy expectations",
    ],
}


@dataclass
class IntelSource:
    title: str
    publisher: str
    url: str
    published_at: str
    bucket: str
    direction: str
    score: int
    importance: str
    confidence: str
    evidence_text: str
    why_it_matters: str
    official: bool = False
    claim_type: str = "interpretation"
    event_key: str = ""
    id: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "title": self.title,
            "publisher": self.publisher,
            "url": self.url,
            "published_at": self.published_at,
            "bucket": self.bucket,
            "direction": self.direction,
            "score": self.score,
            "importance": self.importance,
            "confidence": self.confidence,
            "claim_type": self.claim_type,
            "event_key": self.event_key,
            "evidence_text": self.evidence_text,
            "why_it_matters": self.why_it_matters,
            "official": self.official,
        }
        return d


def is_official(publisher: str, url: str) -> bool:
    hay = f"{publisher} {url}".lower()
    return any(h in hay for h in OFFICIAL_HINTS)


_EVENT_KEY_SEP = re.compile(r"[\s\-]+")
_EVENT_KEY_BAD = re.compile(r"[^a-z0-9_]")
_EVENT_KEY_COLLAPSE = re.compile(r"_+")
EVENT_KEY_MAX_LEN = 60


def sanitize_event_key(raw) -> str:
    """Normalize a model-provided event key to lowercase snake_case (<= 60 chars).

    Spaces/dashes become underscores, anything outside [a-z0-9_] is dropped, runs of
    underscores collapse. Empty/missing stays "" (the source then forms its own
    singleton cluster — see event_cluster_key)."""
    k = str(raw or "").strip().lower()
    k = _EVENT_KEY_SEP.sub("_", k)
    k = _EVENT_KEY_BAD.sub("", k)
    k = _EVENT_KEY_COLLAPSE.sub("_", k).strip("_")
    return k[:EVENT_KEY_MAX_LEN].rstrip("_")


def event_cluster_key(d: dict) -> str:
    """Identity of the UNDERLYING event a source reports on, for one-vote-per-event
    clustering. Uses the sanitized event_key when present; keyless/legacy sources fall
    back to their own URL so each forms a singleton cluster. Prefixes ("ev::"/"src::")
    keep the two namespaces from colliding."""
    ek = sanitize_event_key(d.get("event_key", ""))
    if ek:
        return f"ev::{ek}"
    return f"src::{url_key(d.get('url', ''))}"


def claim_type_of(source: dict) -> str:
    """Resolve a source's evidentiary tier: its own valid claim_type, else a sensible
    fallback — official sources are treated as official data, everything else as
    interpretation (conservative: unclassified narrative isn't over-weighted)."""
    ct = (source.get("claim_type") or "").strip().lower()
    if ct in CLAIM_TYPES:
        return ct
    return "official_data" if source.get("official") else "interpretation"


def _clamp_score(v) -> int:
    try:
        n = int(round(float(v)))
    except (TypeError, ValueError):
        return 0
    return max(-2, min(2, n))


def normalize_source(raw: dict, fallback_bucket: str) -> IntelSource | None:
    """Coerce a model-produced dict into a valid IntelSource, or None if unusable."""
    url = (raw.get("url") or "").strip()
    title = (raw.get("title") or "").strip()
    if not url or not title:
        return None
    bucket = (raw.get("bucket") or fallback_bucket).strip().lower()
    if bucket not in BUCKETS:
        bucket = fallback_bucket
    direction = (raw.get("direction") or "neutral").strip().lower()
    if direction not in DIRECTIONS:
        direction = "neutral"
    importance = (raw.get("importance") or "medium").strip().lower()
    if importance not in IMPORTANCES:
        importance = "medium"
    confidence = (raw.get("confidence") or "medium").strip().lower()
    if confidence not in CONFIDENCES:
        confidence = "medium"
    publisher = (raw.get("publisher") or raw.get("source") or "").strip() or "Unknown"
    official = bool(raw.get("official")) or is_official(publisher, url)
    return IntelSource(
        title=title,
        publisher=publisher,
        url=url,
        published_at=(raw.get("published_at") or "").strip(),
        bucket=bucket,
        direction=direction,
        score=_clamp_score(raw.get("score")),
        importance=importance,
        confidence=confidence,
        evidence_text=(raw.get("evidence_text") or "").strip(),
        why_it_matters=(raw.get("why_it_matters") or "").strip(),
        official=official,
        claim_type=claim_type_of({"claim_type": raw.get("claim_type"), "official": official}),
        event_key=sanitize_event_key(raw.get("event_key")),
    )


_WORD = re.compile(r"[a-z0-9]+")


def url_key(url: str) -> str:
    """Normalize a URL for identity: drop scheme noise, query, fragment, trailing slash."""
    return re.sub(r"[#?].*$", "", (url or "").rstrip("/").lower())


def title_key(title: str) -> str:
    return " ".join(_WORD.findall((title or "").lower())[:8])


def source_key(d: dict) -> tuple[str, str]:
    """Identity of a source dict: (normalized url, first-8-word title)."""
    return (url_key(d.get("url", "")), title_key(d.get("title", "")))


def dedupe(sources: list[IntelSource]) -> list[IntelSource]:
    """Drop duplicates by normalized URL, then by first-8-word title similarity."""
    seen_url: set[str] = set()
    seen_title: set[str] = set()
    out: list[IntelSource] = []
    for s in sources:
        uk = url_key(s.url)
        tk = title_key(s.title)
        if uk in seen_url or (tk and tk in seen_title):
            continue
        seen_url.add(uk)
        if tk:
            seen_title.add(tk)
        out.append(s)
    return out


def in_window(published_at: str, since: str) -> bool:
    """True if a source is within the current inter-meeting window (>= since date).

    Undated sources are kept (we can't prove they're stale). Comparison is on the
    ISO date prefix, so timestamps and bare dates both work.
    """
    if not published_at:
        return True
    return published_at[:10] >= (since or "")[:10]


def mark_and_merge(
    prior: list[dict], current: list[dict], since: str, now: str
) -> tuple[list[dict], int]:
    """Merge previously-seen sources with this run's sources into the window feed.

    * Scoped to the current inter-meeting window (`since`) so the feed auto-resets at
      each FOMC meeting and never regrows unbounded.
    * Deduped by `source_key` so the same article never appears twice.
    * Each merged source carries `first_seen_at` (when it first entered the feed) and
      `is_new` (first appeared in THIS run). Carried-over sources from earlier runs are
      retained but marked `is_new=False`, so new evidence builds on what we already have.

    Returns (merged_sources, new_count).
    """
    # A source is "the same" if EITHER its URL or its title key matches (mirrors dedupe).
    prior_urls = {url_key(d.get("url", "")) for d in prior if url_key(d.get("url", ""))}
    prior_titles = {title_key(d.get("title", "")) for d in prior if title_key(d.get("title", ""))}

    def seen_before(d: dict) -> bool:
        uk, tk = source_key(d)
        return uk in prior_urls or (bool(tk) and tk in prior_titles)

    merged: list[dict] = []
    by_url: dict[str, int] = {}
    by_title: dict[str, int] = {}

    def find(d: dict) -> int | None:
        uk, tk = source_key(d)
        if uk in by_url:
            return by_url[uk]
        if tk and tk in by_title:
            return by_title[tk]
        return None

    def index(i: int, d: dict) -> None:
        uk, tk = source_key(d)
        if uk:
            by_url[uk] = i
        if tk:
            by_title[tk] = i

    new_count = 0
    # Earlier-run sources still inside the window come first; then this run's sources.
    # Each tagged is_first so we know whether to count it as new-this-run.
    for d in [(p, False) for p in prior] + [(c, True) for c in current]:
        src, is_this_run = d
        if not in_window(src.get("published_at", ""), since):
            continue
        if not url_key(src.get("url", "")):
            continue
        first_seen = src.get("first_seen_at") or src.get("collected_at") or now
        idx = find(src)
        if idx is not None:
            # Known already — keep the earliest first_seen, refresh fields, never "new".
            prev_fs = merged[idx]["first_seen_at"]
            merged[idx] = {**src, "first_seen_at": min(prev_fs, first_seen), "is_new": False}
        else:
            is_new = is_this_run and not seen_before(src)
            if is_new:
                new_count += 1
            merged.append({**src, "first_seen_at": (now if is_this_run else first_seen),
                           "is_new": is_new})
            index(len(merged) - 1, merged[-1])

    return merged, new_count


def latest_event_date() -> str | None:
    if not EVENT_TRUTH_JSON.exists():
        return None
    doc = json.loads(EVENT_TRUTH_JSON.read_text(encoding="utf-8"))
    return doc.get("latest_event_date")


def today_iso() -> str:
    return date.today().isoformat()


def ensure_dirs() -> None:
    INTEL_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
