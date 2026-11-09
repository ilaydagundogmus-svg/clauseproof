"""Run the evaluation against the real API and write measured results.

    python -m eval.run_eval --check-dataset          # no API key needed
    python -m eval.run_eval --method both --runs 3   # needs ANTHROPIC_API_KEY / ANTHROPIC_MODEL

Only numbers that were actually measured are written. Nothing is estimated.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from clauseproof.analyzer import Analyzer
from clauseproof.config import ConfigError, load_settings
from clauseproof.pipeline import run_analysis
from clauseproof.rules.loader import load_rules

from .baseline import BaselineAnalyzer
from .data import DatasetError, load_dataset
from .metrics import evaluate, render_table

RESULTS_DIR = Path(__file__).parent / "results"


def _runner(analyzer: Analyzer, ruleset):
    return lambda text: run_analysis(text, ruleset, analyzer).findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.run_eval")
    parser.add_argument("--method", choices=["pipeline", "baseline", "both"], default="both")
    parser.add_argument("--runs", type=int, default=1, help="Repeat count (use 3 for consistency)")
    parser.add_argument("--limit", type=int, default=0, help="Only the first N contracts")
    parser.add_argument(
        "--check-dataset", action="store_true", help="Validate the dataset and exit"
    )
    args = parser.parse_args(argv)

    try:
        cases = load_dataset()
    except DatasetError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2
    if args.limit:
        cases = cases[: args.limit]
    if args.check_dataset:
        print(f"Dataset OK: {len(cases)} contracts, {len(cases) * 11} labeled rule pairs.")
        return 0
    if args.runs < 1:
        print("--runs must be at least 1.", file=sys.stderr)
        return 2

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 3

    ruleset = load_rules()
    methods = ["pipeline", "baseline"] if args.method == "both" else [args.method]
    calls_per_contract = {"pipeline": 3, "baseline": 1}
    planned = sum(calls_per_contract[m] for m in methods) * len(cases) * args.runs
    print(
        f"Planned API calls: about {planned} (more if retries or repairs occur).", file=sys.stderr
    )

    results = {}
    for method in methods:
        analyzer = (Analyzer if method == "pipeline" else BaselineAnalyzer)(settings)
        result = evaluate(cases, _runner(analyzer, ruleset), runs=args.runs)
        result["usage"] = {
            "api_calls": analyzer.api_calls,
            "input_tokens": analyzer.input_tokens,
            "output_tokens": analyzer.output_tokens,
        }
        results[method] = result

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{stamp}.json"
    payload = {
        "timestamp_utc": stamp,
        "model": settings.model,
        "rules_version": ruleset.version,
        "dataset": "synthetic, labels by construction (see eval/dataset/README.md)",
        "results": results,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(render_table(results))
    print(f"\nModel: {settings.model} | contracts: {len(cases)} | runs: {args.runs}")
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
