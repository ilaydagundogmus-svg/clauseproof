"""Clause segmentation by clause numbering (never blind token chunking)."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches line starts such as "1.", "1.1", "7.2.3", "Article 3", "Section 4".
_HEADING = re.compile(
    r"^(?P<num>(?:Article|Section|Clause)\s+\d+(?:\.\d+)*|\d+(?:\.\d+)*\.?)(?=\s|$)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class Clause:
    id: str
    ref: str
    text: str
    start: int
    end: int


def segment(text: str) -> list[Clause]:
    """Split text into clauses with ids and character spans.

    Falls back to paragraph splitting when no numbering is found, so the
    pipeline never silently drops content.
    """
    matches = list(_HEADING.finditer(text))
    if not matches:
        return _by_paragraph(text)

    clauses: list[Clause] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        clauses.append(_make("C0", "preamble", text, 0, matches[0].start()))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        ref = m.group("num").rstrip(".")
        clauses.append(_make(f"C{len(clauses) + 1}", ref, text, m.start(), end))
    return clauses


def _by_paragraph(text: str) -> list[Clause]:
    clauses: list[Clause] = []
    pos = 0
    for part in re.split(r"\n\s*\n", text):
        idx = text.find(part, pos)
        if idx < 0 or not part.strip():
            continue
        pos = idx + len(part)
        clauses.append(_make(f"C{len(clauses) + 1}", f"para {len(clauses) + 1}", text, idx, pos))
    return clauses


def _make(cid: str, ref: str, text: str, start: int, end: int) -> Clause:
    return Clause(id=cid, ref=ref, text=text[start:end].strip(), start=start, end=end)


def format_clauses(clauses: list[Clause]) -> str:
    """Render clauses for the prompt, each tagged with its reference."""
    return "\n\n".join(f"[{c.ref}] {c.text}" for c in clauses)
