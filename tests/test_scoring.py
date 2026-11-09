import pytest

from clauseproof.rules.loader import load_rules
from clauseproof.schemas import RuleFinding, Status
from clauseproof.scoring import (
    Color,
    ScoringError,
    compute_score,
    effective_status,
    rule_color,
    summarize,
)

RULESET = load_rules()
WEIGHTS = {r.id: r.weight for r in RULESET.rules}
QUOTE = "a verbatim quote of sufficient length"


def f(rule_id, status, grounded=True, confidence=0.9):
    quote = QUOTE if status in ("satisfied", "partial") else None
    return RuleFinding(
        rule_id=rule_id,
        status=status,
        evidence_quote=quote,
        rationale="r",
        confidence=confidence,
        grounded=grounded and quote is not None,
    )


def all_with(status, **over):
    return [f(r.id, over.get(r.id, status)) for r in RULESET.rules]


def test_all_satisfied_is_one():
    assert compute_score(all_with("satisfied"), RULESET) == 1.0


def test_all_missing_is_zero():
    assert compute_score(all_with("missing"), RULESET) == 0.0


def test_partial_counts_half():
    assert compute_score(all_with("partial"), RULESET) == 0.5


def test_weighting():
    # DPA-02 has weight 3; marking only it missing removes 3 of the total weight.
    total = sum(WEIGHTS.values())
    score = compute_score(all_with("satisfied", **{"DPA-02": "missing"}), RULESET)
    assert score == pytest.approx((total - WEIGHTS["DPA-02"]) / total)


def test_not_applicable_leaves_denominator():
    score = compute_score(all_with("satisfied", **{"DPA-11": "not_applicable"}), RULESET)
    assert score == 1.0
    score = compute_score(
        all_with("missing", **{"DPA-11": "not_applicable", "DPA-01": "satisfied"}), RULESET
    )
    assert score == pytest.approx(WEIGHTS["DPA-01"] / (sum(WEIGHTS.values()) - WEIGHTS["DPA-11"]))


def test_all_not_applicable_gives_none():
    assert compute_score(all_with("not_applicable"), RULESET) is None


def test_ungrounded_satisfied_counts_as_missing():
    findings = [f(r.id, "satisfied", grounded=(r.id != "DPA-01")) for r in RULESET.rules]
    assert effective_status(findings[0]) is Status.MISSING
    expected = 1 - WEIGHTS["DPA-01"] / sum(WEIGHTS.values())
    assert compute_score(findings, RULESET) == pytest.approx(expected)


def test_score_is_deterministic():
    findings = all_with("partial", **{"DPA-03": "satisfied"})
    assert compute_score(findings, RULESET) == compute_score(list(findings), RULESET)


def test_missing_finding_raises():
    with pytest.raises(ScoringError, match="missing"):
        compute_score(all_with("satisfied")[:-1], RULESET)


def test_unknown_and_duplicate_ids_raise():
    base = all_with("satisfied")
    with pytest.raises(ScoringError):
        compute_score(base + [f("DPA-99", "missing")], RULESET)
    with pytest.raises(ScoringError, match="Duplicate"):
        compute_score(base + [f("DPA-01", "missing")], RULESET)


def test_colors():
    mandatory = next(r for r in RULESET.rules if r.mandatory)
    optional = next(r for r in RULESET.rules if not r.mandatory)
    assert rule_color(f(mandatory.id, "missing"), mandatory) is Color.RED
    assert rule_color(f(optional.id, "missing"), optional) is Color.YELLOW
    assert rule_color(f(mandatory.id, "partial"), mandatory) is Color.YELLOW
    assert rule_color(f(mandatory.id, "satisfied"), mandatory) is Color.GREEN
    assert rule_color(f(mandatory.id, "satisfied", confidence=0.2), mandatory) is Color.YELLOW
    assert rule_color(f(mandatory.id, "not_applicable"), mandatory) is Color.GREY
    assert rule_color(f(mandatory.id, "satisfied", grounded=False), mandatory) is Color.RED


def test_breakdown_summary():
    findings = all_with(
        "satisfied", **{"DPA-01": "partial", "DPA-02": "partial", "DPA-03": "missing"}
    )
    summary = summarize(findings, RULESET)
    assert summary.summary() == "8 of 11 rules satisfied, 2 partial, 1 missing"


def test_breakdown_mentions_not_applicable():
    findings = all_with("satisfied", **{"DPA-11": "not_applicable"})
    assert summarize(findings, RULESET).summary() == (
        "10 of 10 rules satisfied, 0 partial, 0 missing, 1 not applicable"
    )
