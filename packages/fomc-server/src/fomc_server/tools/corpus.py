"""Corpus tools: search the Fed primary-source text corpus + statement redlines.

The corpus lives at <lab_root>/data/fomc/<doc_type>/text/*.txt (lab_root == repo root
in the flat fomc-research layout) with
filenames starting with the ISO document date (e.g. 2026-06-17a.txt). Both tools
resolve paths through _paths at call time so FOMC_INTEL_REPO_ROOT keeps working.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from fomc_server import _paths
from fomc_server._provenance import stamp
from fomc_server.tools import error_dict

DOC_TYPES = ("statement", "minutes", "speech", "testimony", "warsh")

SNIPPET_CONTEXT = 200  # chars either side of a match
MAX_HITS_PER_FILE = 3
MAX_LIMIT = 200
UNIFIED_DIFF_CAP = 8000

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Statements/minutes/warsh filenames START with the ISO date; speeches/testimony carry a
# speaker prefix first (powell_2020-04-09a.txt) — so extract, don't slice.
_FILE_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _corpus_root() -> Path:
    return _paths.lab_root() / "data" / "fomc"


def _doc_dir(doc_type: str) -> Path:
    return _corpus_root() / doc_type / "text"


def _compile_query(query: str) -> tuple[re.Pattern[str], str]:
    """Regex when the query compiles as one, otherwise escaped substring."""
    try:
        return re.compile(query, re.IGNORECASE), "regex"
    except re.error:
        return re.compile(re.escape(query), re.IGNORECASE), "substring"


def _corpus_files(
    doc_types: list[str], since: str | None, until: str | None
) -> list[tuple[str, str, Path]]:
    """(date, doc_type, path) for every corpus file in range, newest first."""
    out: list[tuple[str, str, Path]] = []
    for doc_type in doc_types:
        d = _doc_dir(doc_type)
        if not d.is_dir():
            continue
        for path in d.glob("*.txt"):
            m = _FILE_DATE.search(path.name)
            iso = m.group(0) if m else ""
            if since and (not iso or iso < since):
                continue
            if until and (not iso or iso > until):
                continue
            out.append((iso, doc_type, path))
    out.sort(key=lambda t: (t[0], t[2].name), reverse=True)
    return out


def _snippet(text: str, start: int, end: int) -> str:
    pre = text[max(0, start - SNIPPET_CONTEXT) : start]
    post = text[end : end + SNIPPET_CONTEXT]
    return " ".join(f"{pre}«{text[start:end]}»{post}".split())


def search_fed_corpus(
    query: str,
    doc_types: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search the Fed primary-source corpus (FOMC statements, minutes, speeches,
    testimony, plus the Warsh file set) for a case-insensitive regex or plain
    substring (auto-detected). Filters: doc_types subset of
    statement/minutes/speech/testimony/warsh, since/until ISO dates. Returns up to
    `limit` hits, newest documents first, max 3 hits per file, each with a
    whitespace-normalized snippet where the match is wrapped in «».
    Historical/observational evidence only — not investment advice."""
    try:
        if doc_types is None:
            selected = list(DOC_TYPES)
        else:
            bad = [d for d in doc_types if d not in DOC_TYPES]
            if bad:
                raise ValueError(f"unknown doc_types {bad}; expected subset of {list(DOC_TYPES)}")
            selected = list(doc_types)
        limit = max(1, min(int(limit), MAX_LIMIT))
        root = _corpus_root()
        if not root.is_dir():
            raise FileNotFoundError(f"corpus directory not found: {root}")
        pattern, pattern_type = _compile_query(query)
        files = _corpus_files(selected, since, until)
        hits: list[dict[str, Any]] = []
        files_matched = 0
        for iso, doc_type, path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            file_hits = 0
            for m in pattern.finditer(text):
                if m.end() == m.start():
                    continue  # zero-width regex match — skip, useless snippet
                file_hits += 1
                if file_hits > MAX_HITS_PER_FILE:
                    break
                if len(hits) < limit:
                    hits.append(
                        {
                            "date": iso,
                            "doc_type": doc_type,
                            "file": path.name,
                            "snippet": _snippet(text, m.start(), m.end()),
                        }
                    )
            if file_hits:
                files_matched += 1
        return {
            "query": query,
            "pattern_type": pattern_type,
            "doc_types": selected,
            "since": since,
            "until": until,
            "hits": hits,
            "n_hits": len(hits),
            "files_searched": len(files),
            "files_matched": files_matched,
            "provenance": stamp(root),
        }
    except Exception as exc:
        return error_dict(exc)


# ---------------------------------------------------------------- redline


def _statement_files_by_date() -> dict[str, Path]:
    """Newest→ oldest map of ISO date -> statement file (prefer the 'a' release)."""
    d = _doc_dir("statement")
    if not d.is_dir():
        raise FileNotFoundError(f"statement corpus directory not found: {d}")
    by_date: dict[str, Path] = {}
    for path in sorted(d.glob("*.txt")):
        iso = path.name[:10]
        if iso not in by_date:  # sorted → '2026-01-28a.txt' wins over '...b.txt'
            by_date[iso] = path
    if not by_date:
        raise FileNotFoundError(f"no statement files in {d}")
    return by_date


def _sentences(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [s.strip() for s in _SENTENCE_SPLIT.split(flat) if s.strip()]


def diff_statements(date_a: str | None = None, date_b: str | None = None) -> dict[str, Any]:
    """Fed-watcher redline of two FOMC statements (ISO dates; defaults: the two
    most recent statements on disk, date_a = older). Sentence-level diff: added and
    removed sentences, changed_pairs (before → after rewrites), a unified diff, and
    summary counts — the classic what-changed-since-last-meeting read.
    Historical/observational evidence only — not investment advice."""
    try:
        by_date = _statement_files_by_date()
        dates = sorted(by_date)
        if date_b is None:
            date_b = dates[-1]
        if date_a is None:
            earlier = [d for d in dates if d < date_b]
            if not earlier:
                raise ValueError(f"no statement earlier than {date_b} to diff against")
            date_a = earlier[-1]
        for d in (date_a, date_b):
            if d not in by_date:
                raise FileNotFoundError(
                    f"no statement on disk for {d}; nearest available: "
                    f"{', '.join(dates[-6:])}"
                )
        file_a, file_b = by_date[date_a], by_date[date_b]
        sents_a = _sentences(file_a.read_text(encoding="utf-8", errors="replace"))
        sents_b = _sentences(file_b.read_text(encoding="utf-8", errors="replace"))

        added: list[str] = []
        removed: list[str] = []
        changed_pairs: list[dict[str, str]] = []
        for op, a0, a1, b0, b1 in difflib.SequenceMatcher(
            None, sents_a, sents_b, autojunk=False
        ).get_opcodes():
            if op == "insert":
                added.extend(sents_b[b0:b1])
            elif op == "delete":
                removed.extend(sents_a[a0:a1])
            elif op == "replace":
                olds, news = sents_a[a0:a1], sents_b[b0:b1]
                paired = min(len(olds), len(news))
                changed_pairs.extend(
                    {"from": olds[i], "to": news[i]} for i in range(paired)
                )
                removed.extend(olds[paired:])
                added.extend(news[paired:])

        unified = "\n".join(
            difflib.unified_diff(sents_a, sents_b, fromfile=date_a, tofile=date_b, lineterm="")
        )
        if len(unified) > UNIFIED_DIFF_CAP:
            unified = unified[:UNIFIED_DIFF_CAP] + "\n… [diff truncated]"
        return {
            "date_a": date_a,
            "date_b": date_b,
            "file_a": file_a.name,
            "file_b": file_b.name,
            "added": added,
            "removed": removed,
            "changed_pairs": changed_pairs,
            "unified_diff": unified,
            "summary": {
                "n_added": len(added),
                "n_removed": len(removed),
                "n_changed": len(changed_pairs),
            },
            "provenance": stamp(file_b),
        }
    except Exception as exc:
        return error_dict(exc)


def register(mcp: Any) -> None:
    mcp.tool()(search_fed_corpus)
    mcp.tool()(diff_statements)
