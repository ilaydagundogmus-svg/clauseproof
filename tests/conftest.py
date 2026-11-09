"""Shared fixtures. No test calls the real Anthropic API."""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any

import pytest

SAMPLE_DPA = """\
DATA PROCESSING AGREEMENT

1. Subject matter
1.1 The Processor processes personal data on behalf of the Controller
to provide the hosting Services.
1.2 The processing lasts for the term of the Services agreement.

2. Instructions
2.1 The Processor shall process personal data only on documented instructions from the Controller.

3. Confidentiality
3.1 The Processor shall ensure that authorised persons are bound by confidentiality obligations.

4. Deletion
4.1 At the Controller's choice, the Processor shall delete or return all personal data
after the end of the Services.
"""


def tool_response(findings: list[dict[str, Any]], tool_id: str = "toolu_1") -> SimpleNamespace:
    block = SimpleNamespace(
        type="tool_use", id=tool_id, name="report_findings", input={"findings": findings}
    )
    return SimpleNamespace(
        stop_reason="tool_use",
        content=[block],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def good_finding(rule_id: str, status: str = "missing", **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "rule_id": rule_id,
        "status": status,
        "clause_ref": None,
        "evidence_quote": None,
        "rationale": "Test rationale.",
        "suggested_revision": None,
        "confidence": 0.9,
    }
    if status in ("satisfied", "partial"):
        base["evidence_quote"] = "documented instructions from the Controller"
        base["clause_ref"] = "2.1"
    base.update(over)
    return base


def requested_ids(kwargs: dict[str, Any]) -> list[str]:
    """Extract the rule ids the analyzer asked for from the last user message."""
    last = kwargs["messages"][0]["content"]
    match = re.search(r"Evaluate exactly these rules: ([^.]+)\.", last)
    return [s.strip() for s in match.group(1).split(",")]


class FakeClient:
    """Minimal stand-in for anthropic.Anthropic. `script` is a list of callables/values."""

    def __init__(self, script: list[Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._script = list(script or [])
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self._script:
            return tool_response([good_finding(i) for i in requested_ids(kwargs)])
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(kwargs) if callable(item) else item


@pytest.fixture
def sample_dpa() -> str:
    return SAMPLE_DPA


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tenacity back-off instant in tests."""
    monkeypatch.setattr("tenacity.nap.time.sleep", lambda _s: None)
