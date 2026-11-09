"""Load the labeled dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .build_dataset import DATASET_DIR, RULE_IDS

VALID_STATUSES = {"satisfied", "partial", "missing", "not_applicable"}


class DatasetError(ValueError):
    """Raised when the dataset is incomplete or inconsistent."""


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    gold: dict[str, str]


def load_dataset(directory: Path = DATASET_DIR) -> list[Case]:
    labels_path = directory / "labels.json"
    if not labels_path.is_file():
        raise DatasetError(
            f"labels.json not found in {directory}. Run: python -m eval.build_dataset"
        )
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    cases = []
    for cid in sorted(labels):
        path = directory / f"{cid}.txt"
        if not path.is_file():
            raise DatasetError(f"Missing contract file for {cid}.")
        gold = labels[cid]
        if set(gold) != set(RULE_IDS):
            raise DatasetError(f"{cid}: labels must cover exactly {RULE_IDS[0]}..{RULE_IDS[-1]}.")
        bad = {s for s in gold.values() if s not in VALID_STATUSES}
        if bad:
            raise DatasetError(f"{cid}: invalid status labels {sorted(bad)}.")
        cases.append(Case(id=cid, text=path.read_text(encoding="utf-8"), gold=gold))
    if not cases:
        raise DatasetError("The dataset is empty.")
    return cases
