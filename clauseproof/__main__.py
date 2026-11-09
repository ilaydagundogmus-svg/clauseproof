"""Command line entry point: python -m clauseproof analyze path/to/dpa.txt"""

from __future__ import annotations

import argparse
import logging
import sys

from .analyzer import AnalysisError, Analyzer
from .config import ConfigError, load_settings
from .parsing import ParsingError, read_document
from .pipeline import run_analysis
from .rules.loader import RuleSetError, load_rules
from .scoring import ScoringError, rule_color, summarize

DISCLAIMER = (
    "This tool does not provide legal advice; results must be reviewed by a qualified lawyer."
)

EXIT_OK, EXIT_INPUT, EXIT_CONFIG, EXIT_ANALYSIS = 0, 2, 3, 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clauseproof", description=DISCLAIMER)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("analyze", help="Analyze a DPA (.txt or text-based .pdf)")
    p.add_argument("path", help="Path to the contract file")
    p.add_argument("--framework", default="gdpr_art28_dpa", help="Rule set name")
    p.add_argument("--json", action="store_true", dest="as_json", help="Print JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        text = read_document(args.path)
        ruleset = load_rules(args.framework)
        settings = load_settings()
        report = run_analysis(text, ruleset, Analyzer(settings))
    except ParsingError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return EXIT_INPUT
    except (ConfigError, RuleSetError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except (AnalysisError, ScoringError) as exc:
        print(f"Analysis failed: {exc}", file=sys.stderr)
        return EXIT_ANALYSIS

    if args.as_json:
        print(report.model_dump_json(indent=2))
    else:
        titles = {r.id: r for r in ruleset.rules}
        print(f"Framework: {report.framework} (rules v{report.rules_version})")
        if report.score is not None:
            print(f"Compliance score: {report.score * 100:.0f}%")
        print(f"{summarize(report.findings, ruleset).summary()}\n")
        for f in report.findings:
            rule = titles[f.rule_id]
            color = rule_color(f, rule).value.upper()
            print(f"{f.rule_id} [{f.status.value.upper()} / {color}] {rule.title}")
            print(f"  Legal basis: {rule.legal_basis}   Clause: {f.clause_ref or '-'}")
            print(f"  Rationale: {f.rationale}")
            if f.evidence_quote:
                badge = "verified" if f.grounded else "NOT VERIFIED - counted as missing"
                print(f'  Quote ({badge}): "{f.evidence_quote}"')
            if f.suggested_revision:
                print(f"  Suggested revision: {f.suggested_revision}")
            print(f"  Confidence: {f.confidence:.2f}\n")
        if report.needs_human_review:
            print(f"Needs human review: {', '.join(report.needs_human_review)}\n")
    print(DISCLAIMER, file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
