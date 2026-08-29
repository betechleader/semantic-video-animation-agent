"""CLI for the local, fully offline Agent evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from .harness import load_dataset, run_evaluation
from .reporting import evaluate_thresholds, load_thresholds, write_reports

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
STORAGE_OUTPUT_ROOT = PROJECT_ROOT / "storage"


def _safe_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(STORAGE_OUTPUT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Agent eval output must stay inside project storage") from exc
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=PACKAGE_DIR / "data" / "chinese_cases.json")
    parser.add_argument("--thresholds", type=Path, default=PACKAGE_DIR / "default_thresholds.json")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "storage" / "agent_evals" / "latest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = _safe_output_dir(args.output_dir)
    report = run_evaluation(load_dataset(args.dataset))
    report["regression"] = evaluate_thresholds(report, load_thresholds(args.thresholds))
    json_path, markdown_path = write_reports(report, output_dir)
    print(f"Agent eval {'PASS' if report['regression']['passed'] else 'FAIL'}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {markdown_path}")
    return 0 if report["regression"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
