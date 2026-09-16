"""Collect regime-intelligence evidence via the Perplexity API.

Runs the four bucket query-groups (employment, inflation, fed communications, market
pricing) against a Perplexity search model, forces strict JSON conforming to the
source schema, normalizes + dedupes, and writes:

  * regime_intel/sources.jsonl    — append-only normalized feed (history/dedupe)
  * regime_intel/latest_raw.json  — this run's collection (input to the scorer)

Design choices:
  * stdlib only (urllib) — no new dependencies for CI.
  * Never hard-fails the pipeline: on missing key or total API failure it writes a
    latest_raw.json with an "error" field and exits 0, so the scorer can preserve the
    previous good snapshot and flag it stale.

Usage:
    python scripts/collect_regime_intel.py [--model sonar] [--max-per-prompt 6]

Requires PPLX_API_KEY_fomc (process env or the repo-root .env);
falls back to PPLX_API_KEY if the fomc-specific key is absent.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

import _intel_common as ic

API_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM_PROMPT = (
    "You are a macro research assistant tracking whether US monetary policy is staying in "
    "an easing regime or drifting toward tightening. You search recent, credible sources and "
    "return STRICT JSON only — no prose, no markdown fences. Prefer official primary sources "
    "(Federal Reserve, BLS, BEA, Treasury, FRED, CME FedWatch) over commentary. Score each item "
    "from the Fed's reaction-function perspective."
)

# Per-prompt instruction appended to each query, defining the exact JSON contract.
JSON_CONTRACT = """
Return a JSON object: {{"sources": [ ... ]}} where each source has exactly:
  "title": string,
  "publisher": string,
  "url": string (direct link),
  "published_at": ISO-8601 timestamp (best estimate),
  "bucket": one of "employment","inflation","fed_communications","market_pricing","other",
  "direction": one of "easing","neutral","tightening"
      (easing = supports more cuts; tightening = supports fewer cuts or hikes),
  "score": integer -2..2 (-2 strongly easing, 0 mixed, +2 strongly tightening),
  "importance": one of "low","medium","high",
  "confidence": one of "low","medium","high",
  "claim_type": one of "documented_fact" (verifiable on-the-record fact, e.g. an actual
      quote or an enacted action), "official_data" (an official statistic/data release:
      BLS, BEA, Treasury, FRED, CME, an FOMC vote), "sell_side_scenario" (a bank/research
      forecast or modeled scenario), "interpretation" (analyst/pundit opinion or framing),
  "event_key": stable lowercase snake_case identifier of the UNDERLYING event/release/statement
      this source reports on (e.g. "2026_06_cpi_release", "2026_07_powell_senate_testimony",
      "2026_07_fomc_minutes"). Different outlets covering the same event MUST share the same
      event_key; genuinely distinct events must get distinct keys,
  "evidence_text": one concise factual sentence IN YOUR OWN WORDS. NEVER include a direct
      quotation attributed to a named person — reconstructed quotes misattribute speech;
      paraphrase the substance instead (e.g. "Powell said the Fed faces no risk-free
      path", not "Powell said, 'there is no risk-free path'"),
  "why_it_matters": one sentence linking it to the Fed reaction function.
Only include items published on or after {since}. Up to {max_per_prompt} items. JSON only.
"""


def _extract_json(content: str) -> dict:
    """Pull the first {...} object out of a model response, tolerating stray prose."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lstrip().lower().startswith("json"):
            content = content.lstrip()[4:]
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in response")
    return json.loads(content[start : end + 1])


def call_perplexity(api_key: str, model: str, prompt: str, timeout: int = 60) -> dict:
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    return _extract_json(content)


def collect(
    api_key: str, model: str, since: str, max_per_prompt: int
) -> tuple[list[ic.IntelSource], list[str]]:
    collected: list[ic.IntelSource] = []
    errors: list[str] = []
    for bucket, prompts in ic.QUERY_GROUPS.items():
        for probe in prompts:
            prompt = f"{probe}\n\n" + JSON_CONTRACT.format(
                since=since, max_per_prompt=max_per_prompt
            )
            try:
                data = call_perplexity(api_key, model, prompt)
            except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as e:
                errors.append(f"{bucket}: {type(e).__name__}: {e}")
                continue
            for raw in data.get("sources", []):
                s = ic.normalize_source(raw, fallback_bucket=bucket)
                if s:
                    collected.append(s)
    return ic.dedupe(collected), errors


def load_prior_sources() -> list[dict]:
    """Every source seen in earlier runs (the append-only audit feed)."""
    if not ic.SOURCES_JSONL.exists():
        return []
    out: list[dict] = []
    for line in ic.SOURCES_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def assign_ids(sources: list[dict]) -> None:
    ordered = sorted(sources, key=lambda d: d.get("published_at", ""), reverse=True)
    for i, s in enumerate(ordered, 1):
        s["id"] = f"src_{i:03d}"


def write_outputs(doc: dict, this_run: list[dict]) -> None:
    ic.ensure_dirs()
    ic.LATEST_RAW.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    # Append only THIS run's freshly-collected sources to the audit feed.
    with ic.SOURCES_JSONL.open("a", encoding="utf-8") as f:
        for s in this_run:
            f.write(json.dumps({**s, "collected_at": doc["generated_at"]}) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Collect regime intelligence via Perplexity")
    p.add_argument("--model", default="sonar", help="Perplexity model (default: sonar)")
    p.add_argument("--max-per-prompt", type=int, default=6)
    args = p.parse_args(argv)

    since = ic.latest_event_date() or "2020-01-01"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    api_key = ic.load_api_key()

    if not api_key:
        doc = {
            "generated_at": now,
            "window_start": since,
            "window_end": ic.today_iso(),
            "model": args.model,
            "error": "PPLX_API_KEY_fomc not set",
            "sources": [],
        }
        write_outputs(doc, [])
        print("WARN: PPLX_API_KEY_fomc not set — wrote empty latest_raw.json (scorer marks stale).")
        return 0

    sources, errors = collect(api_key, args.model, since, args.max_per_prompt)
    this_run = [s.to_dict() for s in sources]  # deduped within this run

    # Merge with everything seen in earlier runs, scoped to the current window. The same
    # article never reappears; genuinely new evidence is flagged is_new and builds on
    # the carried-over set.
    prior = load_prior_sources()
    merged, new_count = ic.mark_and_merge(prior, this_run, since, now)
    assign_ids(merged)

    doc = {
        "generated_at": now,
        "window_start": since,
        "window_end": ic.today_iso(),
        "model": args.model,
        "errors": errors,
        "error": ("all probes failed" if (not merged and errors) else None),
        "new_this_run": new_count,
        "sources": merged,
    }
    write_outputs(doc, this_run)
    print(
        f"This run: {len(this_run)} fresh; window feed now {len(merged)} sources "
        f"({new_count} new since last run) back to {since}; {len(errors)} probe errors."
    )
    print(f"  raw : {ic.LATEST_RAW}")
    print(f"  feed: {ic.SOURCES_JSONL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
