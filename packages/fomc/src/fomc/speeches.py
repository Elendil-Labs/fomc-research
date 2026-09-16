"""Fetch Fed speeches and Congressional testimony by speaker (default: Powell).

Distinct from fetch.py (which reads the FOMC meeting calendar): this scrapes the
yearly speeches and testimony index pages on federalreserve.gov, where each item's
URL slug encodes the speaker (e.g. /newsevents/speech/powell20240131a.htm). Filters
by speaker slug, downloads each, extracts plain text, and writes a manifest.

Note: Kevin Warsh left the Fed Board in 2011, so he has NO speeches/testimony on
federalreserve.gov for 2020-2026 — his material is gathered separately (see the
Warsh dossier under data/fomc/warsh/).

Usage:
    python -m fomc.speeches                                  # Powell, 2020-current
    python -m fomc.speeches --speakers powell,williams
    python -m fomc.speeches --since 2024-01-01 --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
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

BASE = "https://www.federalreserve.gov"
UA = "Mozilla/5.0 (compatible; fomc-research/0.1; research use)"

# doc_type -> (index URL template, link regex). group(1)=speaker, (2)=YYYYMMDD, (3)=suffix
SOURCES: dict[str, tuple[str, re.Pattern]] = {
    "speech": (
        f"{BASE}/newsevents/speech/{{year}}-speeches.htm",
        re.compile(r"/newsevents/speech/([a-z]+)(\d{8})([a-z])\.htm"),
    ),
    "testimony": (
        f"{BASE}/newsevents/testimony/{{year}}-testimony.htm",
        re.compile(r"/newsevents/testimony/([a-z]+)(\d{8})([a-z])\.htm"),
    ),
}


@dataclass
class SpeechDoc:
    doc_type: str  # speech | testimony
    speaker: str
    speech_date: str  # ISO
    suffix: str
    url: str
    raw_path: str = ""
    text_path: str = ""
    http_status: int | None = None
    byte_size: int | None = None
    sha256: str = ""
    fetched_at: str = ""
    error: str = ""

    @property
    def key(self) -> tuple:
        return (self.doc_type, self.speaker, self.speech_date, self.suffix)


def _ymd_to_iso(ymd: str) -> str:
    return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def discover(sess: requests.Session, since: date, speakers: set[str]) -> list[SpeechDoc]:
    found: dict[tuple, SpeechDoc] = {}
    start_year = since.year
    end_year = datetime.now(timezone.utc).year
    for doc_type, (tmpl, pat) in SOURCES.items():
        for year in range(start_year, end_year + 1):
            url = tmpl.format(year=year)
            try:
                resp = sess.get(url, timeout=30)
            except requests.RequestException as exc:  # pragma: no cover - network
                print(f"  ! index fetch failed {url}: {exc}", file=sys.stderr)
                continue
            if resp.status_code != 200:
                continue
            for m in pat.finditer(resp.text):
                speaker, ymd, suffix = m.group(1), m.group(2), m.group(3)
                if speakers and speaker not in speakers:
                    continue
                iso = _ymd_to_iso(ymd)
                try:
                    d = date.fromisoformat(iso)
                except ValueError:
                    continue
                if d < since:
                    continue
                doc = SpeechDoc(
                    doc_type=doc_type,
                    speaker=speaker,
                    speech_date=iso,
                    suffix=suffix,
                    url=BASE + m.group(0),
                )
                found.setdefault(doc.key, doc)
    return sorted(found.values(), key=lambda x: (x.speech_date, x.doc_type, x.speaker))


def _extract_text(content: bytes) -> str:
    soup = BeautifulSoup(content, "lxml")
    node = soup.find(id="article") or soup.body or soup
    for tag in node.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = node.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def download(sess: requests.Session, doc: SpeechDoc, out_dir: Path, delay: float = 0.4) -> SpeechDoc:
    raw_dir = out_dir / doc.doc_type / "raw"
    text_dir = out_dir / doc.doc_type / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{doc.speaker}_{doc.speech_date}{doc.suffix}"
    raw_path = raw_dir / f"{stem}.html"
    text_path = text_dir / f"{stem}.txt"
    try:
        resp = sess.get(doc.url, timeout=60)
        doc.http_status = resp.status_code
        if resp.status_code != 200:
            doc.error = f"HTTP {resp.status_code}"
            return doc
        content = resp.content
        doc.byte_size = len(content)
        doc.sha256 = hashlib.sha256(content).hexdigest()
        raw_path.write_bytes(content)
        text_path.write_text(_extract_text(content), encoding="utf-8")
        doc.raw_path = _rel(raw_path)
        doc.text_path = _rel(text_path)
        doc.fetched_at = datetime.now(timezone.utc).isoformat()
    except requests.RequestException as exc:  # pragma: no cover - network
        doc.error = str(exc)
    finally:
        time.sleep(delay)
    return doc


def write_manifest(docs: list[SpeechDoc], out_dir: Path) -> Path:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "federalreserve.gov",
        "doc_count": len(docs),
        "ok_count": sum(1 for d in docs if d.text_path and not d.error),
        "by_speaker": {},
        "documents": [asdict(d) for d in docs],
    }
    for d in docs:
        manifest["by_speaker"].setdefault(d.speaker, {"speech": 0, "testimony": 0})
        if not d.error and d.text_path:
            manifest["by_speaker"][d.speaker][d.doc_type] += 1
    path = out_dir / "speeches_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def run(since: date, out_dir: Path, speakers: set[str], dry_run: bool = False, delay: float = 0.4) -> list[SpeechDoc]:
    sess = _session()
    print(f"Discovering speeches/testimony for {sorted(speakers) or 'ALL'} since {since} ...")
    docs = discover(sess, since, speakers)
    by = {}
    for d in docs:
        by[d.doc_type] = by.get(d.doc_type, 0) + 1
    print(f"Discovered {len(docs)}: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())))
    if dry_run:
        for d in docs:
            print(f"  {d.speech_date} {d.doc_type:10s} {d.speaker:10s} {d.url}")
        return docs
    out_dir.mkdir(parents=True, exist_ok=True)
    done: list[SpeechDoc] = []
    for i, d in enumerate(docs, 1):
        d = download(sess, d, out_dir, delay=delay)
        status = "ok" if d.text_path and not d.error else f"FAIL({d.error})"
        print(f"  [{i}/{len(docs)}] {d.speech_date} {d.doc_type:10s} {d.speaker:10s} -> {status}")
        done.append(d)
    manifest_path = write_manifest(done, out_dir)
    ok = sum(1 for d in done if d.text_path and not d.error)
    print(f"\nDone. {ok}/{len(done)} fetched. Manifest: {manifest_path}")
    return done


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch Fed speeches/testimony by speaker")
    p.add_argument("--since", default="2020-01-01")
    default_out = REPO_ROOT / "data" / "fomc"
    p.add_argument("--out", default=str(default_out))
    p.add_argument("--speakers", default="powell", help="comma list of URL slugs (e.g. powell,williams); empty = all")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--delay", type=float, default=0.4)
    args = p.parse_args(argv)
    try:
        since = date.fromisoformat(args.since)
    except ValueError:
        print(f"bad --since {args.since!r}", file=sys.stderr)
        return 2
    speakers = {s.strip().lower() for s in args.speakers.split(",") if s.strip()}
    run(since, Path(args.out), speakers, dry_run=args.dry_run, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
