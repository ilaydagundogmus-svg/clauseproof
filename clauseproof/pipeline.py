"""Glue: analyze, verify quotes, compute the score. Each step stays separately testable."""

from __future__ import annotations

from .analyzer import Analyzer
from .grounding import ground_report
from .rules.loader import RuleSet
from .schemas import AnalysisReport
from .scoring import compute_score


def finalize_report(report: AnalysisReport, ruleset: RuleSet, contract_text: str) -> AnalysisReport:
    """Set `grounded` flags, extend the review list and compute the score, all in code."""
    grounded = ground_report(report, contract_text)
    score = compute_score(grounded.findings, ruleset)
    return grounded.model_copy(update={"score": score})


def run_analysis(text: str, ruleset: RuleSet, analyzer: Analyzer) -> AnalysisReport:
    return finalize_report(analyzer.analyze(text, ruleset), ruleset, text)
