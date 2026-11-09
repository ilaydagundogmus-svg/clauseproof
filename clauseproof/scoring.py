"""Deterministic compliance score, colors and breakdown. No model involved.

score = sum(w_i * s_i) / sum(w_i), with s_i = 1 (satisfied), 0.5 (partial), 0 (missing).
Rules marked not_applicable are removed from the denominator. A satisfied or
partial finding whose quote could not be verified counts as missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .config import LOW_CONFIDENCE
from .rules.loader import Rule, RuleSet
from .schemas import RuleFinding, Status

STATUS_POINTS = {Status.SATISFIED: 1.0, Status.PARTIAL: 0.5, Status.MISSING: 0.0}


class ScoringError(ValueError):
    """Raised when findings and rule set do not line up. Never silently ignored."""


class Color(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    GREY = "grey"


@dataclass(frozen=True)
class Breakdown:
    satisfied: int
    partial: int
    missing: int
    not_applicable: int

    @property
    def applicable(self) -> int:
        return self.satisfied + self.partial + self.missing

    def summary(self) -> str:
        text = (
            f"{self.satisfied} of {self.applicable} rules satisfied, "
            f"{self.partial} partial, {self.missing} missing"
        )
        if self.not_applicable:
            text += f", {self.not_applicable} not applicable"
        return text


def effective_status(finding: RuleFinding) -> Status:
    """Status used for scoring: unverified satisfied/partial claims count as missing."""
    if finding.status in (Status.SATISFIED, Status.PARTIAL) and not finding.grounded:
        return Status.MISSING
    return finding.status


def rule_color(finding: RuleFinding, rule: Rule) -> Color:
    """Fixed mapping: mandatory missing is red; partial or uncertain is yellow."""
    status = effective_status(finding)
    if status is Status.NOT_APPLICABLE:
        return Color.GREY
    if status is Status.MISSING:
        return Color.RED if rule.mandatory else Color.YELLOW
    if status is Status.PARTIAL or finding.confidence < LOW_CONFIDENCE:
        return Color.YELLOW
    return Color.GREEN


def _index(findings: list[RuleFinding], ruleset: RuleSet) -> dict[str, RuleFinding]:
    by_id: dict[str, RuleFinding] = {}
    for f in findings:
        if f.rule_id in by_id:
            raise ScoringError(f"Duplicate finding for rule {f.rule_id}.")
        by_id[f.rule_id] = f
    expected = {r.id for r in ruleset.rules}
    if set(by_id) != expected:
        missing = sorted(expected - set(by_id))
        extra = sorted(set(by_id) - expected)
        raise ScoringError(
            f"Findings do not match the rule set (missing={missing}, extra={extra})."
        )
    return by_id


def compute_score(findings: list[RuleFinding], ruleset: RuleSet) -> float | None:
    """Weighted score in [0, 1], or None if no rule is applicable."""
    by_id = _index(findings, ruleset)
    numerator = denominator = 0.0
    for rule in ruleset.rules:
        status = effective_status(by_id[rule.id])
        if status is Status.NOT_APPLICABLE:
            continue
        numerator += rule.weight * STATUS_POINTS[status]
        denominator += rule.weight
    return numerator / denominator if denominator else None


def summarize(findings: list[RuleFinding], ruleset: RuleSet) -> Breakdown:
    by_id = _index(findings, ruleset)
    counts = dict.fromkeys(Status, 0)
    for rule in ruleset.rules:
        counts[effective_status(by_id[rule.id])] += 1
    return Breakdown(
        satisfied=counts[Status.SATISFIED],
        partial=counts[Status.PARTIAL],
        missing=counts[Status.MISSING],
        not_applicable=counts[Status.NOT_APPLICABLE],
    )
