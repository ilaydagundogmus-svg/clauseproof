"""Evaluation metrics. Pure functions; nothing here calls a model."""

from __future__ import annotations

from collections.abc import Callable
from statistics import fmean
from typing import Any

from clauseproof.analyzer import AnalysisError
from clauseproof.schemas import RuleFinding
from clauseproof.scoring import ScoringError, effective_status

from .data import Case

Key = tuple[str, str]  # (case id, rule id)


def accuracy(gold: dict[Key, str], pred: dict[Key, str]) -> float | None:
    keys = [k for k in gold if k in pred]
    if not keys:
        return None
    return sum(gold[k] == pred[k] for k in keys) / len(keys)


def missing_recall(gold: dict[Key, str], pred: dict[Key, str]) -> float | None:
    """Share of truly missing rules that the method also called missing."""
    relevant = [k for k, v in gold.items() if v == "missing" and k in pred]
    if not relevant:
        return None
    return sum(pred[k] == "missing" for k in relevant) / len(relevant)


def missing_precision(gold: dict[Key, str], pred: dict[Key, str]) -> float | None:
    """Share of 'missing' calls that were truly missing."""
    called = [k for k, v in pred.items() if v == "missing" and k in gold]
    if not called:
        return None
    return sum(gold[k] == "missing" for k in called) / len(called)


def grounding_rate(claims: list[tuple[str, bool]]) -> float | None:
    """Among satisfied/partial findings, the share whose quote was found verbatim."""
    relevant = [grounded for status, grounded in claims if status in ("satisfied", "partial")]
    if not relevant:
        return None
    return sum(relevant) / len(relevant)


def consistency(runs: list[dict[Key, str]]) -> float | None:
    """Share of (case, rule) pairs that received the identical status in every run."""
    if len(runs) < 2:
        return None
    keys = set(runs[0]).intersection(*runs[1:])
    if not keys:
        return None
    return sum(len({run[k] for run in runs}) == 1 for k in keys) / len(keys)


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return fmean(present) if present else None


Runner = Callable[[str], list[RuleFinding]]


def evaluate(cases: list[Case], runner: Runner, runs: int = 1) -> dict[str, Any]:
    """Run `runner` over every case `runs` times and compute metrics from what was returned.

    Failed calls are recorded and excluded from the metrics, never counted as correct.
    """
    gold: dict[Key, str] = {
        (c.id, rule_id): status for c in cases for rule_id, status in c.gold.items()
    }
    raw_runs: list[dict[Key, str]] = []
    per_run: list[dict[str, float | None]] = []
    failures: list[dict[str, Any]] = []
    predictions: list[dict[str, dict[str, str]]] = []

    for run_index in range(runs):
        raw: dict[Key, str] = {}
        effective: dict[Key, str] = {}
        claims: list[tuple[str, bool]] = []
        for case in cases:
            try:
                findings = runner(case.text)
            except (AnalysisError, ScoringError) as exc:
                failures.append({"case": case.id, "run": run_index, "error": str(exc)})
                continue
            for f in findings:
                key = (case.id, f.rule_id)
                raw[key] = f.status.value
                effective[key] = effective_status(f).value
                claims.append((f.status.value, f.grounded))
        raw_runs.append(raw)
        predictions.append(_nest(raw))
        per_run.append(
            {
                "rule_accuracy": accuracy(gold, raw),
                "missing_recall": missing_recall(gold, raw),
                "missing_precision": missing_precision(gold, raw),
                "grounding_rate": grounding_rate(claims),
                "accuracy_after_grounding": accuracy(gold, effective),
            }
        )

    metrics = {name: _mean([r[name] for r in per_run]) for name in per_run[0]}
    metrics["consistency"] = consistency(raw_runs)
    return {
        "n_cases": len(cases),
        "n_pairs": len(gold),
        "runs": runs,
        "n_failed_calls": len(failures),
        "metrics": metrics,
        "failures": failures,
        "predictions": predictions,
    }


def _nest(flat: dict[Key, str]) -> dict[str, dict[str, str]]:
    nested: dict[str, dict[str, str]] = {}
    for (case_id, rule_id), status in flat.items():
        nested.setdefault(case_id, {})[rule_id] = status
    return nested


METRIC_LABELS = [
    ("rule_accuracy", "Rule accuracy (status label)"),
    ("missing_recall", "Missing-rule recall"),
    ("missing_precision", "Missing-rule precision"),
    ("grounding_rate", "Grounding rate (verbatim quotes)"),
    ("accuracy_after_grounding", "Accuracy after grounding downgrade"),
    ("consistency", "Consistency across runs"),
]


def render_table(results: dict[str, dict[str, Any]]) -> str:
    """Markdown table: one column per method. Unavailable metrics show 'n/a'."""
    names = list(results)
    header = "| Metric | " + " | ".join(names) + " |"
    sep = "|---|" + "---|" * len(names)
    rows = []
    for key, label in METRIC_LABELS:
        cells = []
        for name in names:
            value = results[name]["metrics"].get(key)
            cells.append("n/a" if value is None else f"{value:.2f}")
        rows.append(f"| {label} | " + " | ".join(cells) + " |")
    footer = (
        "| Failed calls | " + " | ".join(str(results[n]["n_failed_calls"]) for n in names) + " |"
    )
    return "\n".join([header, sep, *rows, footer])


__all__ = [
    "accuracy",
    "consistency",
    "evaluate",
    "grounding_rate",
    "missing_precision",
    "missing_recall",
    "render_table",
]
