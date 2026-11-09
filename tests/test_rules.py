import pytest

from clauseproof.rules.loader import RuleSet, RuleSetError, load_rules


def test_loads_eleven_rules():
    rs = load_rules()
    assert rs.framework == "gdpr_art28_dpa"
    assert [r.id for r in rs.rules] == [f"DPA-{i:02d}" for i in range(1, 12)]


def test_every_rule_has_legal_basis_and_criteria():
    for r in load_rules().rules:
        assert r.legal_basis.startswith("GDPR")
        assert r.satisfied_when and r.suggested_clause_hint and r.weight > 0


def test_unknown_framework():
    with pytest.raises(RuleSetError, match="not found"):
        load_rules("nope")


def test_duplicate_ids_rejected():
    rule = {
        "id": "X-1",
        "title": "t",
        "legal_basis": "b",
        "weight": 1,
        "mandatory": True,
        "question": "q",
        "satisfied_when": ["s"],
        "suggested_clause_hint": "h",
    }
    with pytest.raises(ValueError, match="Duplicate"):
        RuleSet(framework="f", version="1", source="s", rules=[rule, rule])


def test_invalid_yaml_reported(tmp_path):
    (tmp_path / "bad.yaml").write_text("framework: x\nrules: []\n")
    with pytest.raises(RuleSetError, match="Invalid rule set"):
        load_rules("bad", directory=tmp_path)
