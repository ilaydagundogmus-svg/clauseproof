import json

import pytest

from clauseproof.analyzer import AnalysisError
from clauseproof.config import MIN_TEXT_CHARS
from clauseproof.grounding import quote_in_text
from clauseproof.pipeline import run_analysis
from clauseproof.rules.loader import load_rules
from clauseproof.schemas import RuleFinding
from eval.baseline import BaselineAnalyzer
from eval.build_dataset import DATASET_DIR, RULE_IDS, SPECS, build_all, build_contract
from eval.clauses import VARIANTS
from eval.data import DatasetError, load_dataset
from eval.metrics import (
    accuracy,
    consistency,
    evaluate,
    grounding_rate,
    missing_precision,
    missing_recall,
    render_table,
)

from .conftest import FakeClient

# ------------------------------------------------------------------ dataset


def test_dataset_files_match_generator():
    texts, labels = build_all()
    for cid, text in texts.items():
        assert (DATASET_DIR / f"{cid}.txt").read_text(encoding="utf-8") == text
    on_disk = json.loads((DATASET_DIR / "labels.json").read_text(encoding="utf-8"))
    assert on_disk == labels


def test_dataset_size_and_coverage():
    cases = load_dataset()
    assert 12 <= len(cases) <= 15
    assert all(set(c.gold) == set(RULE_IDS) for c in cases)
    statuses = {s for c in cases for s in c.gold.values()}
    assert statuses == {"satisfied", "partial", "missing", "not_applicable"}


def test_contracts_pass_input_validation():
    for case in load_dataset():
        assert len(case.text) >= MIN_TEXT_CHARS


def test_labels_agree_with_clause_text():
    """A satisfied/partial label means its clause text is really in the contract; a
    missing label never has the satisfied wording present."""
    for spec in SPECS:
        text, labels = build_contract(spec)
        for rule_id, status in labels.items():
            variants = VARIANTS[rule_id]
            if status in ("satisfied", "partial"):
                assert any(quote_in_text(c[1], text) for c in variants[status] if c is not None), (
                    spec.id,
                    rule_id,
                )
            if status == "missing":
                for c in variants["satisfied"]:
                    assert not quote_in_text(c[1], text), (spec.id, rule_id)


def test_poisoned_contract_exists():
    texts, _ = build_all()
    assert any("Ignore all previous instructions" in t for t in texts.values())


def test_load_dataset_missing_dir(tmp_path):
    with pytest.raises(DatasetError, match="labels.json"):
        load_dataset(tmp_path)


def test_load_dataset_bad_labels(tmp_path):
    (tmp_path / "labels.json").write_text(json.dumps({"x": {"DPA-01": "satisfied"}}))
    (tmp_path / "x.txt").write_text("text")
    with pytest.raises(DatasetError, match="must cover"):
        load_dataset(tmp_path)


# ------------------------------------------------------------------ metrics


def k(case, rule):
    return (case, rule)


def test_accuracy():
    gold = {k("a", "1"): "satisfied", k("a", "2"): "missing"}
    assert accuracy(gold, {k("a", "1"): "satisfied", k("a", "2"): "satisfied"}) == 0.5
    assert accuracy(gold, {}) is None


def test_missing_precision_and_recall():
    gold = {k("a", "1"): "missing", k("a", "2"): "missing", k("a", "3"): "satisfied"}
    pred = {k("a", "1"): "missing", k("a", "2"): "satisfied", k("a", "3"): "missing"}
    assert missing_recall(gold, pred) == 0.5
    assert missing_precision(gold, pred) == 0.5


def test_missing_metrics_undefined_cases():
    gold = {k("a", "1"): "satisfied"}
    assert missing_recall(gold, {k("a", "1"): "satisfied"}) is None
    assert missing_precision(gold, {k("a", "1"): "satisfied"}) is None


def test_grounding_rate_only_counts_claims():
    claims = [("satisfied", True), ("partial", False), ("missing", False)]
    assert grounding_rate(claims) == 0.5
    assert grounding_rate([("missing", False)]) is None


def test_consistency():
    r1 = {k("a", "1"): "satisfied", k("a", "2"): "missing"}
    r2 = {k("a", "1"): "satisfied", k("a", "2"): "partial"}
    assert consistency([r1, r2]) == 0.5
    assert consistency([r1]) is None


# ----------------------------------------------------------- evaluate runner


def _finding(rule_id, status, grounded=True):
    quote = "a verbatim quote here" if status in ("satisfied", "partial") else None
    return RuleFinding(
        rule_id=rule_id,
        status=status,
        evidence_quote=quote,
        rationale="r",
        confidence=0.9,
        grounded=grounded and quote is not None,
    )


def _oracle(cases):
    gold = {c.text: c.gold for c in cases}
    return lambda text: [_finding(r, s) for r, s in gold[text].items()]


def test_evaluate_perfect_runner():
    cases = load_dataset()
    result = evaluate(cases, _oracle(cases), runs=2)
    m = result["metrics"]
    assert m["rule_accuracy"] == 1.0
    assert m["missing_recall"] == 1.0
    assert m["missing_precision"] == 1.0
    assert m["grounding_rate"] == 1.0
    assert m["consistency"] == 1.0
    assert result["n_failed_calls"] == 0
    assert result["n_pairs"] == len(cases) * 11


def test_evaluate_always_satisfied_runner_is_not_perfect():
    cases = load_dataset()
    result = evaluate(cases, lambda t: [_finding(r, "satisfied") for r in RULE_IDS])
    assert result["metrics"]["rule_accuracy"] < 0.8
    assert result["metrics"]["missing_recall"] == 0.0


def test_evaluate_records_failures_without_crashing():
    cases = load_dataset()
    calls = {"n": 0}

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AnalysisError("boom")
        return _oracle(cases)(text)

    result = evaluate(cases, flaky)
    assert result["n_failed_calls"] == 1
    assert result["failures"][0]["error"] == "boom"
    assert result["metrics"]["rule_accuracy"] == 1.0  # computed on what succeeded only


def test_ungrounded_claims_lower_grounding_and_effective_accuracy():
    cases = load_dataset()
    gold = {c.text: c.gold for c in cases}
    result = evaluate(cases, lambda t: [_finding(r, s, grounded=False) for r, s in gold[t].items()])
    assert result["metrics"]["rule_accuracy"] == 1.0  # raw labels are right
    assert result["metrics"]["grounding_rate"] == 0.0
    assert result["metrics"]["accuracy_after_grounding"] < 1.0


def test_render_table_marks_unavailable_metrics():
    cases = load_dataset()
    result = evaluate(cases, _oracle(cases), runs=1)
    table = render_table({"pipeline": result})
    assert "n/a" in table  # consistency is undefined for a single run
    assert "| Metric | pipeline |" in table


# ------------------------------------------------------------------ baseline


def test_baseline_makes_one_plain_call_and_grounds():
    case = load_dataset()[0]
    client = FakeClient()
    report = run_analysis(case.text, load_rules(), BaselineAnalyzer(client=client))
    assert len(client.calls) == 1
    assert len(report.findings) == 11
    system_text = client.calls[0]["system"][0]["text"]
    assert "cache_control" not in client.calls[0]["system"][0]
    assert "Checklist" not in system_text  # no per-rule criteria in the baseline prompt
