"""Deterministically build the labeled synthetic dataset.

Labels are fixed by construction, before any model sees the contracts: each
contract is assembled from clause variants whose status is known. Run:

    python -m eval.build_dataset
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .clauses import DISTRACTORS, INJECTION, VARIANTS

DATASET_DIR = Path(__file__).parent / "dataset"
RULE_IDS = [f"DPA-{i:02d}" for i in range(1, 12)]
CODES = {"S": "satisfied", "P": "partial", "M": "missing", "N": "not_applicable"}

PREAMBLE = (
    'This agreement is made between Example Retail GmbH (the "Controller") and CloudHost '
    'Services Ltd (the "Processor") and supplements the main services agreement between '
    'them (the "Main Agreement"). All names are fictitious.'
)


@dataclass(frozen=True)
class Spec:
    id: str
    variant: str  # "A" or "B"
    codes: str  # one status code per rule, DPA-01 .. DPA-11
    poisoned: bool = False


SPECS = [
    Spec("c01", "A", "SSSSSSSSSSS"),
    Spec("c02", "B", "SSSSSSSSSSS"),
    Spec("c03", "A", "SSSSSSSSSSN"),
    Spec("c04", "B", "SSSSMSSMSSS"),
    Spec("c05", "A", "SPSPSPSPSSP"),
    Spec("c06", "B", "PMSSSMSSPSM"),
    Spec("c07", "A", "SSMSSSSSMMM"),
    Spec("c08", "B", "MMMMMMMMMMM"),
    Spec("c09", "A", "SSSSPPSSSSN"),
    Spec("c10", "B", "SMSSSSPSSMS"),
    Spec("c11", "A", "PSPSPSPSPSP"),
    Spec("c12", "B", "SSSSSMSSSMS", poisoned=True),
    Spec("c13", "A", "MSMSMSMSMSN"),
]


def _pick(rule_id: str, code: str, variant: str):
    status = CODES[code]
    options = VARIANTS[rule_id].get(status)
    if options is None:
        raise ValueError(f"{rule_id} has no '{status}' variant (code {code}).")
    return options[0 if variant == "A" else min(1, len(options) - 1)]


def build_contract(spec: Spec) -> tuple[str, dict[str, str]]:
    """Return (contract text, labels) for one spec."""
    if len(spec.codes) != len(RULE_IDS):
        raise ValueError(f"{spec.id}: expected {len(RULE_IDS)} status codes.")
    lines = [
        f"DATA PROCESSING AGREEMENT (SYNTHETIC TEST DOCUMENT {spec.id.upper()})",
        "",
        PREAMBLE,
        "",
    ]
    labels: dict[str, str] = {}
    section = 0

    def add(clause: tuple[str, str]) -> None:
        nonlocal section
        section += 1
        lines.extend([f"{section}. {clause[0]}", f"{section}.1 {clause[1]}", ""])

    add(DISTRACTORS["fees"])
    for index, (rule_id, code) in enumerate(zip(RULE_IDS, spec.codes, strict=True)):
        labels[rule_id] = CODES[code]
        clause = _pick(rule_id, code, spec.variant)
        if clause is not None:
            add(clause)
        if index == 4:
            add(DISTRACTORS["liability"])
    if spec.poisoned:
        add(INJECTION)
    add(DISTRACTORS["law"])
    return "\n".join(lines).rstrip() + "\n", labels


def build_all() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    texts: dict[str, str] = {}
    labels: dict[str, dict[str, str]] = {}
    for spec in SPECS:
        texts[spec.id], labels[spec.id] = build_contract(spec)
    return texts, labels


def write_dataset(directory: Path = DATASET_DIR) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    texts, labels = build_all()
    for cid, text in texts.items():
        (directory / f"{cid}.txt").write_text(text, encoding="utf-8")
    (directory / "labels.json").write_text(
        json.dumps(labels, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    write_dataset()
    print(f"Wrote {len(SPECS)} contracts and labels.json to {DATASET_DIR}")
