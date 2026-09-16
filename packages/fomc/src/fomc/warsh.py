"""Fetch Kevin Warsh's freely-available primary-text record into the corpus.

Warsh left the Fed Board in 2011, so his 2020-2026 monetary-policy record is NOT on
federalreserve.gov. This module holds a *curated* catalog (assembled from a web-search
pass; see data/fomc/warsh/warsh_dossier.md) of items whose full primary text is freely
accessible, downloads each, extracts plain text, and writes a manifest. Paywalled
items (most WSJ op-eds) are listed in the dossier but not downloaded here; drop any
manually-obtained text into data/fomc/warsh/text/.

Usage:
    python -m fomc.warsh                 # fetch the curated free primary sources
    python -m fomc.warsh --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[4]


def _rel(p: Path) -> str:
    """Manifest paths are stored relative to the repo root so the committed manifests are
    portable across machines and CI runners (never absolute local paths)."""
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(p)

# Some hosts (e.g. RealClearPolitics) 403 a bare UA; send browser-like headers.
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/pdf,*/*", "Accept-Language": "en-US,en;q=0.9"}


@dataclass
class Source:
    slug: str  # stable filename stem
    date: str  # ISO
    title: str
    venue: str
    doc_type: str  # testimony | qfr | lecture | interview | essay | op-ed
    url: str
    ext: str  # pdf | html


# Curated catalog of FREELY accessible Warsh primary text (his own words), confirmed
# retrievable. Paywalled / dead-URL / JS-rendered items are in BLOCKED below + the dossier.
CATALOG: list[Source] = [
    Source("2026-04-21_senate_testimony", "2026-04-21",
           "Confirmation Opening Statement / Written Testimony", "Senate Banking (BHUA)",
           "testimony",
           "https://www.banking.senate.gov/imo/media/doc/warsh_testimony_4-21-26.pdf", "pdf"),
    Source("2026-04-23_qfr_responses", "2026-04-23",
           "Combined QFR Responses (Democratic members)", "Senate Banking (BHUA)",
           "qfr",
           "https://www.banking.senate.gov/imo/media/doc/bhua_dems_combined_qfr_responses_from_warsh.pdf", "pdf"),
    Source("2025-07-08_inflation_is_a_choice", "2025-07-08",
           "Inflation Is a Choice: Warsh on Fixing the Federal Reserve (Uncommon Knowledge)", "Hoover",
           "interview",
           "https://www.hoover.org/research/inflation-choice-kevin-warsh-fixing-federal-reserve", "html"),
]

# Known-valuable items that are NOT freely retrievable by an automated fetcher (verified
# 2026-06-18). Recorded so the gap is explicit and reproducible, not silently dropped.
# To capture: open in a browser (Hoover pages are JS-rendered; WSJ is paywalled) and
# drop the text into data/fomc/warsh/text/.
BLOCKED: list[dict] = [
    {"date": "2025-04-25", "title": "Commanding Heights: Central Banks at a Crossroads (G30 Spring Lecture)",
     "venue": "Hoover/G30/IMF",
     "url": "https://www.hoover.org/research/g30-spring-lecture-2025-kevin-warsh-commanding-heights-central-banks-crossroads",
     "reason": "Hoover PDF URL 404s; landing page is JS-rendered (no static text). Capture via browser."},
    {"date": "2022-03-01", "title": "Reinvigorating Economic Governance (Cogan & Warsh)", "venue": "Hoover",
     "url": "https://www.hoover.org/research/reinvigorating-economic-governance-advancing-new-framework-american-prosperity",
     "reason": "Hoover PDF URL 404s; landing JS-rendered. Capture via browser. (Partly non-monetary.)"},
    {"date": "2025-11-16", "title": "The Federal Reserve's Broken Leadership", "venue": "Wall Street Journal",
     "url": "https://www.wsj.com/opinion/the-federal-reserves-broken-leadership-43629c87",
     "reason": "Paywalled at WSJ; RealClearPolitics repost is a teaser stub only (no full text)."},
]


@dataclass
class Result:
    slug: str
    date: str
    title: str
    venue: str
    doc_type: str
    url: str
    ext: str
    raw_path: str = ""
    text_path: str = ""
    http_status: int | None = None
    byte_size: int | None = None
    sha256: str = ""
    text_chars: int = 0
    fetched_at: str = ""
    error: str = ""


def _extract_text(content: bytes, ext: str) -> str:
    if ext == "pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except Exception as exc:  # pragma: no cover
            return f"[pdf extraction failed: {exc}]"
    soup = BeautifulSoup(content, "lxml")
    node = soup.find(id="article") or soup.find("article") or soup.body or soup
    for tag in node.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", node.get_text("\n", strip=True)).strip()


def fetch_one(sess: requests.Session, s: Source, out_dir: Path, delay: float) -> Result:
    raw_dir = out_dir / "raw"
    text_dir = out_dir / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    r = Result(**{k: getattr(s, k) for k in ("slug", "date", "title", "venue", "doc_type", "url", "ext")})
    try:
        resp = sess.get(s.url, timeout=60)
        r.http_status = resp.status_code
        if resp.status_code != 200:
            r.error = f"HTTP {resp.status_code}"
            return r
        content = resp.content
        r.byte_size = len(content)
        r.sha256 = hashlib.sha256(content).hexdigest()
        (raw_dir / f"{s.slug}.{s.ext}").write_bytes(content)
        text = _extract_text(content, s.ext)
        (text_dir / f"{s.slug}.txt").write_text(text, encoding="utf-8")
        r.raw_path = _rel(raw_dir / f"{s.slug}.{s.ext}")
        r.text_path = _rel(text_dir / f"{s.slug}.txt")
        r.text_chars = len(text)
        r.fetched_at = datetime.now(timezone.utc).isoformat()
    except requests.RequestException as exc:  # pragma: no cover
        r.error = str(exc)
    finally:
        time.sleep(delay)
    return r


def run(out_dir: Path, dry_run: bool = False, delay: float = 0.5) -> list[Result]:
    sess = requests.Session()
    sess.headers.update(HEADERS)
    if dry_run:
        for s in CATALOG:
            print(f"  {s.date} {s.doc_type:10s} {s.ext:4s} {s.url}")
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    for i, s in enumerate(CATALOG, 1):
        r = fetch_one(sess, s, out_dir, delay)
        status = f"ok ({r.text_chars} chars)" if r.text_path and not r.error else f"FAIL({r.error})"
        print(f"  [{i}/{len(CATALOG)}] {r.date} {r.doc_type:10s} -> {status}")
        results.append(r)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Curated free primary-text Warsh sources. Paywalled items are in warsh_dossier.md.",
        "doc_count": len(results),
        "ok_count": sum(1 for r in results if r.text_path and not r.error),
        "documents": [asdict(r) for r in results],
        "blocked": BLOCKED,
    }
    (out_dir / "warsh_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    ok = manifest["ok_count"]
    print(f"\nDone. {ok}/{len(results)} fetched. Manifest: {out_dir / 'warsh_manifest.json'}")
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch curated free Warsh primary-text sources")
    default_out = REPO_ROOT / "data" / "fomc" / "warsh"
    p.add_argument("--out", default=str(default_out))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--delay", type=float, default=0.5)
    args = p.parse_args(argv)
    run(Path(args.out), dry_run=args.dry_run, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
