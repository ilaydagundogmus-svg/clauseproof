"""Load and validate YAML rule sets."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

RULES_DIR = Path(__file__).parent


class RuleSetError(ValueError):
    """Raised when a rule set is missing or invalid."""


class Rule(BaseModel):
    id: str
    title: str
    legal_basis: str
    weight: float = Field(gt=0)
    mandatory: bool
    question: str
    satisfied_when: list[str] = Field(min_length=1)
    red_flags: list[str] = []
    suggested_clause_hint: str

    @field_validator("question", "suggested_clause_hint")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class RuleSet(BaseModel):
    framework: str
    version: str
    date: str | None = None
    source: str
    verification_status: str | None = None
    rules: list[Rule] = Field(min_length=1)

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, rules: list[Rule]) -> list[Rule]:
        ids = [r.id for r in rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate rule ids: {sorted(dupes)}")
        return rules


def load_rules(framework: str = "gdpr_art28_dpa", directory: Path | None = None) -> RuleSet:
    """Load `<framework>.yaml` and validate it."""
    path = (directory or RULES_DIR) / f"{framework}.yaml"
    if not path.is_file():
        raise RuleSetError(f"Rule set not found: {framework}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return RuleSet.model_validate(data)
    except (yaml.YAMLError, ValidationError) as exc:
        raise RuleSetError(f"Invalid rule set '{framework}': {exc}") from exc
