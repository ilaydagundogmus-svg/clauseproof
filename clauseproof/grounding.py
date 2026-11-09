"""Evidence quote verification.

A finding is "grounded" only if its quote appears verbatim in the contract text,
after harmless normalization (whitespace, quote and dash styles, Unicode forms).
Case and wording are never normalized: a paraphrase must fail.
"""

from __future__ import annotations

import re
import unicodedata

from .config import MIN_QUOTE_CHARS
from .schemas import AnalysisReport, RuleFinding, Status

_QUOTE_MAP = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "«": '"',
    "»": '"',
}
_DASHES = "‐‑‒–—―−"
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"))
_CLAUSE_TAG = re.compile(r"^\[[^\]]{1,30}\]\s*")


def normalize_for_match(text: str) -> str:
    """Normalize typography and whitespace only; wording and case stay untouched."""
    text = unicodedata.normalize("NFKC", text).translate(_INVISIBLE)
    for src, dst in _QUOTE_MAP.items():
        text = text.replace(src, dst)
    for dash in _DASHES:
        text = text.replace(dash, "-")
    return re.sub(r"\s+", " ", text).strip()


def _segments(quote: str) -> list[str]:
    """Split a quote on ellipses; each segment must then appear, in order."""
    q = normalize_for_match(quote)
    q = _CLAUSE_TAG.sub("", q)  # the prompt tags clauses as "[2.1] ..."; that tag is ours
    q = q.strip("\"' ")
    parts = [p.strip(" \"'") for p in q.split("...")]
    return [p for p in parts if p]


def quote_in_text(quote: str | None, contract_text: str) -> bool:
    """True if every segment of the quote occurs verbatim, in order, in the contract."""
    if not quote or not quote.strip():
        return False
    segments = _segments(quote)
    if not segments or any(len(s) < MIN_QUOTE_CHARS for s in segments):
        return False
    haystack = normalize_for_match(contract_text)
    pos = 0
    for seg in segments:
        idx = haystack.find(seg, pos)
        if idx < 0:
            return False
        pos = idx + len(seg)
    return True


def ground_finding(finding: RuleFinding, contract_text: str) -> RuleFinding:
    """Return a copy with `grounded` set by code. Findings without a quote stay ungrounded."""
    return finding.model_copy(
        update={"grounded": quote_in_text(finding.evidence_quote, contract_text)}
    )


def needs_grounding(finding: RuleFinding) -> bool:
    """Only satisfied or partial findings rely on a quote."""
    return finding.status in (Status.SATISFIED, Status.PARTIAL)


def ground_report(report: AnalysisReport, contract_text: str) -> AnalysisReport:
    """Ground every finding and flag unverified claims for human review."""
    findings = [ground_finding(f, contract_text) for f in report.findings]
    flagged = set(report.needs_human_review)
    flagged.update(f.rule_id for f in findings if needs_grounding(f) and not f.grounded)
    review = [f.rule_id for f in findings if f.rule_id in flagged]
    return report.model_copy(update={"findings": findings, "needs_human_review": review})
