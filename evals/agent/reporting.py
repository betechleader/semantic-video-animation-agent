"""Threshold evaluation and JSON/Markdown report output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_thresholds(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("modes"), dict):
        raise ValueError("Threshold file must contain a modes object")
    return payload


def evaluate_thresholds(report: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for mode, rules in thresholds["modes"].items():
        actual_metrics = report["modes"][mode]
        for metric, bounds in rules.items():
            value = actual_metrics.get(metric)
            passed = value is not None
            if passed and "min" in bounds:
                passed = value >= bounds["min"]
            if passed and "max" in bounds:
                passed = value <= bounds["max"]
            checks.append(
                {
                    "mode": mode,
                    "metric": metric,
                    "actual": value,
                    "min": bounds.get("min"),
                    "max": bounds.get("max"),
                    "passed": passed,
                }
            )
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def render_markdown(report: dict[str, Any]) -> str:
    metric_names = (
        "animation_plan_schema_pass_rate",
        "transcript_grounding_precision",
        "time_interval_valid_rate",
        "overlap_violation_rate",
        "tool_call_success_rate",
        "auto_repair_success_rate",
        "average_retry_count",
        "human_intervention_rate",
        "task_success_rate",
    )
    lines = [
        "# Offline Agent Evaluation Report",
        "",
        f"Dataset: `{report['dataset']['name']}` ({report['dataset']['case_count']} self-authored Chinese cases)",
        "",
        "| Metric | Standard | Agent | Agent - Standard |",
        "|---|---:|---:|---:|",
    ]
    for name in metric_names:
        values = report["comparison"][name]
        lines.append(
            f"| `{name}` | {_display(values['standard'])} | {_display(values['agent'])} | "
            f"{_display(values['delta_agent_minus_standard'])} |"
        )
    lines.extend(["", "## Stage latency (ms)", "", "| Mode | Stage | Samples | P50 | P95 |", "|---|---|---:|---:|---:|"])
    for mode in ("standard", "agent"):
        for stage, values in report["modes"][mode]["stage_latency_ms"].items():
            lines.append(
                f"| {mode} | {stage} | {values['sample_count']} | {values['p50']} | {values['p95']} |"
            )
    regression = report.get("regression", {"passed": True, "checks": []})
    lines.extend(
        [
            "",
            "## Regression gates",
            "",
            f"Overall: **{'PASS' if regression['passed'] else 'FAIL'}**",
            "",
            "| Mode | Metric | Actual | Min | Max | Result |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for check in regression["checks"]:
        lines.append(
            f"| {check['mode']} | `{check['metric']}` | {_display(check['actual'])} | "
            f"{_display(check['min'])} | {_display(check['max'])} | "
            f"{'PASS' if check['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "The report contains aggregate metrics and stable run/node/tool identifiers only. "
            "It contains no transcript text, user storage content, or absolute paths.",
            "",
        ]
    )
    return "\n".join(lines)


def _display(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_reports(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "agent_eval_report.json"
    markdown_path = output_dir / "agent_eval_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path
