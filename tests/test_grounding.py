import pytest

from clauseproof.grounding import ground_report, normalize_for_match, quote_in_text
from clauseproof.schemas import AnalysisReport, RuleFinding, Status

CONTRACT = (
    "2.1 The Processor shall process personal data only on documented instructions "
    "from the Controller.\n"
    "4.1 At the Controller’s choice, the Processor shall delete or return all personal "
    "data – including copies – after the end of the Services."
)


def test_exact_quote_is_grounded():
    assert quote_in_text("process personal data only on documented instructions", CONTRACT)


def test_whitespace_and_line_breaks_ignored():
    assert quote_in_text("documented   instructions\nfrom the Controller", CONTRACT)


def test_quote_and_dash_style_ignored():
    assert quote_in_text("At the Controller's choice, the Processor shall delete", CONTRACT)
    assert quote_in_text("all personal data - including copies - after", CONTRACT)


def test_paraphrase_is_not_grounded():
    assert not quote_in_text("The Processor must only act on written orders", CONTRACT)


def test_case_change_is_not_grounded():
    assert not quote_in_text("DOCUMENTED INSTRUCTIONS FROM THE CONTROLLER", CONTRACT)


def test_fabricated_quote_is_not_grounded():
    assert not quote_in_text("The Processor shall permit audits on thirty days notice", CONTRACT)


@pytest.mark.parametrize("quote", [None, "", "   ", "short"])
def test_empty_or_too_short_quote_rejected(quote):
    assert not quote_in_text(quote, CONTRACT)


def test_clause_tag_prefix_is_stripped():
    assert quote_in_text("[2.1] The Processor shall process personal data only", CONTRACT)


def test_surrounding_quotation_marks_ignored():
    assert quote_in_text('"documented instructions from the Controller"', CONTRACT)


def test_ellipsis_segments_must_appear_in_order():
    assert quote_in_text("The Processor shall process ... from the Controller.", CONTRACT)
    assert not quote_in_text("from the Controller ... The Processor shall process", CONTRACT)


def test_normalize_keeps_case():
    assert normalize_for_match("  A B\t\nC ") == "A B C"


def _finding(rule_id, status, quote):
    return RuleFinding(
        rule_id=rule_id, status=status, evidence_quote=quote, rationale="r", confidence=0.9
    )


def test_ground_report_flags_fabricated_quote():
    report = AnalysisReport(
        framework="f",
        rules_version="1",
        findings=[
            _finding("DPA-02", Status.SATISFIED, "documented instructions from the Controller"),
            _finding("DPA-09", Status.SATISFIED, "The Controller may audit at any time"),
            _finding("DPA-08", Status.MISSING, None),
        ],
    )
    out = ground_report(report, CONTRACT)
    grounded = {f.rule_id: f.grounded for f in out.findings}
    assert grounded == {"DPA-02": True, "DPA-09": False, "DPA-08": False}
    assert out.needs_human_review == ["DPA-09"]


def test_ground_report_keeps_existing_review_flags():
    report = AnalysisReport(
        framework="f",
        rules_version="1",
        findings=[_finding("DPA-08", Status.MISSING, None)],
        needs_human_review=["DPA-08"],
    )
    assert ground_report(report, CONTRACT).needs_human_review == ["DPA-08"]
