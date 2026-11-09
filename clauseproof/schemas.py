"""Pydantic models shared by the tool schema and output validation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Status(StrEnum):
    SATISFIED = "satisfied"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class RuleFinding(BaseModel):
    """One finding for one rule. `grounded` is set by code, never by the model."""

    rule_id: str
    status: Status
    clause_ref: str | None = Field(None, description="Clause number, e.g. '7.2'")
    evidence_quote: str | None = Field(
        None, description="VERBATIM quote from the contract; null if none"
    )
    rationale: str = Field(description="Short, reasoned explanation")
    suggested_revision: str | None = Field(
        None, description="Only for partial or missing status; null otherwise"
    )
    confidence: float = Field(ge=0, le=1)
    grounded: bool = False

    @model_validator(mode="after")
    def _check_consistency(self) -> RuleFinding:
        if self.status in (Status.SATISFIED, Status.PARTIAL) and not (
            self.evidence_quote and self.evidence_quote.strip()
        ):
            raise ValueError(f"{self.rule_id}: '{self.status.value}' requires a verbatim quote")
        return self


class FindingBatch(BaseModel):
    """Tool input schema: findings for one group of rules."""

    findings: list[RuleFinding]


class AnalysisReport(BaseModel):
    framework: str
    rules_version: str
    findings: list[RuleFinding]
    score: float | None = None
    needs_human_review: list[str] = []


def tool_input_schema() -> dict[str, Any]:
    """JSON schema for the forced tool, with code-owned fields removed."""
    schema = FindingBatch.model_json_schema()
    finding = schema.get("$defs", {}).get("RuleFinding", {})
    finding.get("properties", {}).pop("grounded", None)
    return schema
