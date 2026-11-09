import pytest
from pydantic import ValidationError

from clauseproof.schemas import RuleFinding, Status, tool_input_schema


def _kw(**over):
    base = {"rule_id": "DPA-01", "status": "missing", "rationale": "r", "confidence": 0.5}
    base.update(over)
    return base


def test_missing_needs_no_quote():
    assert RuleFinding(**_kw()).status is Status.MISSING


@pytest.mark.parametrize("status", ["satisfied", "partial"])
def test_satisfied_or_partial_requires_quote(status):
    with pytest.raises(ValidationError):
        RuleFinding(**_kw(status=status))
    with pytest.raises(ValidationError):
        RuleFinding(**_kw(status=status, evidence_quote="   "))


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_confidence_bounds(bad):
    with pytest.raises(ValidationError):
        RuleFinding(**_kw(confidence=bad))


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        RuleFinding(**_kw(status="compliant"))


def test_tool_schema_excludes_grounded():
    schema = tool_input_schema()
    assert "grounded" not in schema["$defs"]["RuleFinding"]["properties"]
    assert "evidence_quote" in schema["$defs"]["RuleFinding"]["properties"]
