"""Fetch FOMC primary sources directly from federalreserve.gov.

Link-driven: scrapes the official FOMC calendar + historical index pages for real
document URLs (statements, minutes, SEP projection tables, press-conference
transcripts), then downloads each, saves the raw file plus extracted plain text,
and writes a JSON manifest.

Usage:
    python -m fomc.fetch                       # fetch everything since 2020-01-01
    python -m fomc.fetch --since 2020-01-01 --out /path/to/data/fomc
    python -m fomc.fetch --types statement,minutes
    python -m fomc.fetch --dry-run             # list what would be fetched
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
from typing import Iterable

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

# Index pages that link to the actual documents. The calendars page covers the
# most recent ~6 years; historical pages cover older years (2020 holds the COVID
# emergency meetings, which are analytically important).
INDEX_PAGES = [
    f"{BASE}/monetarypolicy/fomccalendars.htm",  # covers ~2021-current
    f"{BASE}/monetarypolicy/fomchistorical2020.htm",  # 2020 incl. COVID emergency meetings
]

# Pre-2020 historical pages are 5-year-lag *materials archives* (agendas/tealbooks),
# not direct doc links — but the FOMC{YYYYMMDD} file prefixes enumerate each scheduled
# meeting's decision date, from which statement/minutes/SEP/press-conf URLs are built.
MATERIALS_INDEX = f"{BASE}/monetarypolicy/fomchistorical{{year}}.htm"
MATERIALS_DATE_RE = re.compile(r"FOMC(\d{8})")

# doc_type -> (regex over href, file extension). Each regex's group(1) is the
# YYYYMMDD meeting date; statements also have a trailing a/b/c suffix in group(2).
# The calendar links the press-conference *landing page* (fomcpresconf{date}.htm);
# the actual transcript PDF lives at /mediacenter/files/FOMCpresconf{date}.pdf and
# is reconstructed from the matched date in discover().
LINK_PATTERNS: dict[str, tuple[re.Pattern, str]] = {
    "statement": (re.compile(r"/newsevents/pressreleases/monetary(\d{8})([a-z])\.htm"), "html"),
    "minutes": (re.compile(r"/monetarypolicy/fomcminutes(\d{8})\.htm"), "html"),
    "sep": (re.compile(r"/monetarypolicy/(?:files/)?fomcprojtabl(\d{8})\.(?:htm|pdf)"), "html"),
    "press_conference_transcript": (re.compile(r"/monetarypolicy/fomcpresconf(\d{8})\.htm"), "pdf"),
}

DEFAULT_TYPES = list(LINK_PATTERNS.keys())


@dataclass
class FomcDoc:
    doc_type: str
    meeting_date: str  # ISO YYYY-MM-DD
    suffix: str  # statement a/b/c; "" otherwise
    url: str
    ext: str  # html | pdf
    raw_path: str = ""
    text_path: str = ""
    http_status: int | None = None
    byte_size: int | None = None
    sha256: str = ""
    fetched_at: str = ""
    error: str = ""

    @property
    def key(self) -> tuple:
        return (self.doc_type, self.meeting_date, self.suffix)


def _ymd_to_iso(ymd: str) -> str:
    return f"{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    return s


def discover(sess: requests.Session, since: date) -> list[FomcDoc]:
    """Scrape index pages and return a deduped, date-filtered list of documents."""
    found: dict[tuple, FomcDoc] = {}
    for index_url in INDEX_PAGES:
        try:
            resp = sess.get(index_url, timeout=30)
        except requests.RequestException as exc:  # pragma: no cover - network
            print(f"  ! index fetch failed {index_url}: {exc}", file=sys.stderr)
            continue
        if resp.status_code != 200:
            print(f"  ! index {index_url} -> HTTP {resp.status_code}", file=sys.stderr)
            continue
        html = resp.text
        for doc_type, (pat, _ext) in LINK_PATTERNS.items():
            for m in pat.finditer(html):
                ymd = m.group(1)
                suffix = m.group(2) if pat.groups >= 2 and m.lastindex and m.lastindex >= 2 else ""
                href = m.group(0)
                ext = "pdf" if href.lower().endswith(".pdf") else "html"
                iso = _ymd_to_iso(ymd)
                try:
                    d = date.fromisoformat(iso)
                except ValueError:
                    continue
                if d < since:
                    continue
                if doc_type == "press_conference_transcript":
                    # Rewrite landing page -> transcript PDF.
                    url = f"{BASE}/mediacenter/files/FOMCpresconf{ymd}.pdf"
                    ext = "pdf"
                else:
                    url = href if href.startswith("http") else BASE + href
                doc = FomcDoc(
                    doc_type=doc_type,
                    meeting_date=iso,
                    suffix=suffix,
                    url=url,
                    ext=ext,
                )
                # Dedup. For SEP prefer pdf over htm if both seen.
                existing = found.get(doc.key)
                if existing is None or (doc.doc_type == "sep" and ext == "pdf" and existing.ext != "pdf"):
                    found[doc.key] = doc
    return sorted(found.values(), key=lambda x: (x.meeting_date, x.doc_type, x.suffix))


def discover_from_materials(sess: requests.Session, since: date) -> list[FomcDoc]:
    """Enumerate pre-2020 scheduled meetings from materials-archive pages and build
    constructed doc URLs (statement/minutes/SEP/press-conf). 404s are filtered at
    download time, so non-quarterly meetings (no SEP/presser before 2019) drop out."""
    found: dict[tuple, FomcDoc] = {}
    for year in range(since.year, 2020):
        url = MATERIALS_INDEX.format(year=year)
        try:
            resp = sess.get(url, timeout=30)
        except requests.RequestException as exc:  # pragma: no cover - network
            print(f"  ! materials fetch failed {url}: {exc}", file=sys.stderr)
            continue
        if resp.status_code != 200:
            continue
        for ymd in sorted(set(MATERIALS_DATE_RE.findall(resp.text))):
            iso = _ymd_to_iso(ymd)
            try:
                d = date.fromisoformat(iso)
            except ValueError:
                continue
            if d < since:
                continue
            built = [
                ("statement", "a", f"{BASE}/newsevents/pressreleases/monetary{ymd}a.htm", "html"),
                ("minutes", "", f"{BASE}/monetarypolicy/fomcminutes{ymd}.htm", "html"),
                ("sep", "", f"{BASE}/monetarypolicy/files/fomcprojtabl{ymd}.pdf", "pdf"),
                ("press_conference_transcript", "", f"{BASE}/mediacenter/files/FOMCpresconf{ymd}.pdf", "pdf"),
            ]
            for doc_type, suffix, doc_url, ext in built:
                doc = FomcDoc(doc_type=doc_type, meeting_date=iso, suffix=suffix, url=doc_url, ext=ext)
                found.setdefault(doc.key, doc)
    return sorted(found.values(), key=lambda x: (x.meeting_date, x.doc_type, x.suffix))


def _extract_text(content: bytes, ext: str) -> str:
    if ext == "pdf":
        import io

        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception as exc:  # pragma: no cover - malformed pdf
            return f"[pdf extraction failed: {exc}]"
    # HTML
    soup = BeautifulSoup(content, "lxml")
    # Fed article pages put body text in <div id="article">; fall back to body.
    node = soup.find(id="article") or soup.body or soup
    for tag in node.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = node.get_text("\n", strip=True)
    # collapse runs of blank lines
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def download(sess: requests.Session, doc: FomcDoc, out_dir: Path, delay: float = 0.5) -> FomcDoc:
    raw_dir = out_dir / doc.doc_type / "raw"
    text_dir = out_dir / doc.doc_type / "text"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{doc.meeting_date}{doc.suffix}"
    raw_path = raw_dir / f"{stem}.{doc.ext}"
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
        text = _extract_text(content, doc.ext)
        text_path.write_text(text, encoding="utf-8")
        doc.raw_path = _rel(raw_path)
        doc.text_path = _rel(text_path)
        doc.fetched_at = datetime.now(timezone.utc).isoformat()
    except requests.RequestException as exc:  # pragma: no cover - network
        doc.error = str(exc)
    finally:
        time.sleep(delay)
    return doc


def write_manifest(docs: list[FomcDoc], out_dir: Path) -> Path:
    path = out_dir / "manifest.json"
    # Merge with the existing manifest: a filtered run (--types/--since/--limit)
    # must not erase entries for documents it did not touch.
    merged: dict[tuple, dict] = {}
    if path.exists():
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
            for d in prior.get("documents", []):
                merged[(d.get("doc_type"), d.get("meeting_date"), d.get("suffix", ""))] = d
        except (json.JSONDecodeError, OSError):
            pass
    for doc in docs:
        merged[(doc.doc_type, doc.meeting_date, doc.suffix)] = asdict(doc)
    all_docs = sorted(
        merged.values(), key=lambda x: (x["meeting_date"], x["doc_type"], x.get("suffix", ""))
    )

    # Per-meeting rollup for convenience.
    meetings: dict[str, dict] = {}
    for d in all_docs:
        m = meetings.setdefault(d["meeting_date"], {"meeting_date": d["meeting_date"], "documents": {}})
        suffix = d.get("suffix", "")
        label = d["doc_type"] + (f"_{suffix}" if suffix and suffix != "a" else "")
        m["documents"][label] = {
            "url": d.get("url", ""),
            "text_path": d.get("text_path", ""),
            "raw_path": d.get("raw_path", ""),
            "ok": bool(d.get("text_path")) and not d.get("error"),
            "error": d.get("error") or None,
        }
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "federalreserve.gov",
        "doc_count": len(all_docs),
        "ok_count": sum(1 for d in all_docs if d.get("text_path") and not d.get("error")),
        "documents": all_docs,
        "meetings": sorted(meetings.values(), key=lambda x: x["meeting_date"]),
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def run(
    since: date,
    out_dir: Path,
    types: Iterable[str],
    dry_run: bool = False,
    limit: int | None = None,
    delay: float = 0.5,
) -> list[FomcDoc]:
    sess = _session()
    types = set(types)
    print(f"Discovering FOMC documents since {since} ...")
    found = {d.key: d for d in discover(sess, since)}
    if since.year < 2020:  # add pre-2020 meetings from materials-archive pages
        for d in discover_from_materials(sess, since):
            found.setdefault(d.key, d)
    docs = [d for d in sorted(found.values(), key=lambda x: (x.meeting_date, x.doc_type, x.suffix))
            if d.doc_type in types]
    if limit:
        docs = docs[:limit]
    by_type: dict[str, int] = {}
    for d in docs:
        by_type[d.doc_type] = by_type.get(d.doc_type, 0) + 1
    print(f"Discovered {len(docs)} documents: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    if dry_run:
        for d in docs:
            print(f"  {d.meeting_date} {d.doc_type:30s} {d.suffix:1s} {d.url}")
        return docs

    out_dir.mkdir(parents=True, exist_ok=True)
    done: list[FomcDoc] = []
    for i, d in enumerate(docs, 1):
        d = download(sess, d, out_dir, delay=delay)
        status = "ok" if d.text_path and not d.error else f"FAIL({d.error})"
        print(f"  [{i}/{len(docs)}] {d.meeting_date} {d.doc_type:30s}{d.suffix} -> {status}")
        done.append(d)
    manifest_path = write_manifest(done, out_dir)
    ok = sum(1 for d in done if d.text_path and not d.error)
    print(f"\nDone. {ok}/{len(done)} fetched. Manifest: {manifest_path}")
    return done


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch FOMC primary sources from federalreserve.gov")
    p.add_argument("--since", default="2020-01-01", help="ISO date; collect documents on/after this (default 2020-01-01)")
    default_out = REPO_ROOT / "data" / "fomc"
    p.add_argument("--out", default=str(default_out), help="output directory (default: <repo>/data/fomc)")
    p.add_argument("--types", default=",".join(DEFAULT_TYPES), help="comma list: " + ",".join(DEFAULT_TYPES))
    p.add_argument("--dry-run", action="store_true", help="list documents without downloading")
    p.add_argument("--limit", type=int, default=None, help="cap number of documents (debug)")
    p.add_argument("--delay", type=float, default=0.5, help="seconds between requests (be polite)")
    args = p.parse_args(argv)
    try:
        since = date.fromisoformat(args.since)
    except ValueError:
        print(f"bad --since {args.since!r}", file=sys.stderr)
        return 2
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    run(since, Path(args.out), types, dry_run=args.dry_run, limit=args.limit, delay=args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
