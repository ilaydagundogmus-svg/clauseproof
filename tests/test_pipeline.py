import pytest

from clauseproof.analyzer import Analyzer
from clauseproof.pipeline import run_analysis
from clauseproof.rules.loader import load_rules

from .conftest import FakeClient, good_finding, requested_ids, tool_response


def _script(overrides):
    def respond(kwargs):
        return tool_response(
            [good_finding(i, **overrides.get(i, {})) for i in requested_ids(kwargs)]
        )

    return [respond] * 3


def test_end_to_end_with_real_and_fabricated_quotes(sample_dpa):
    overrides = {
        "DPA-02": {"status": "satisfied"},  # default quote exists in the sample contract
        "DPA-09": {
            "status": "satisfied",
            "evidence_quote": "The Controller may audit the Processor at any time",
        },
    }
    client = FakeClient(_script(overrides))
    report = run_analysis(sample_dpa, load_rules(), Analyzer(client=client))

    by_id = {f.rule_id: f for f in report.findings}
    assert by_id["DPA-02"].grounded is True
    assert by_id["DPA-09"].grounded is False  # fabricated quote caught
    assert "DPA-09" in report.needs_human_review
    # Only DPA-02 (weight 3 of total 25) is satisfied and verified.
    assert report.score == pytest.approx(3 / 25)


def test_score_ignores_fabricated_claim(sample_dpa):
    # Everything claimed satisfied with a quote that is not in the contract:
    # nothing can be verified, so the score must be 0.
    claim = {"status": "satisfied", "evidence_quote": "this sentence is not in the contract"}
    ids = [f"DPA-{i:02d}" for i in range(1, 12)]
    client = FakeClient(_script(dict.fromkeys(ids, claim)))
    report = run_analysis(sample_dpa, load_rules(), Analyzer(client=client))
    assert report.score == 0.0
    assert set(report.needs_human_review) == set(ids)


def test_all_verified_scores_one(sample_dpa):
    claim = {"status": "satisfied", "evidence_quote": "documented instructions from the Controller"}
    ids = [f"DPA-{i:02d}" for i in range(1, 12)]
    client = FakeClient(_script(dict.fromkeys(ids, claim)))
    report = run_analysis(sample_dpa, load_rules(), Analyzer(client=client))
    assert report.score == 1.0
    assert report.needs_human_review == []
