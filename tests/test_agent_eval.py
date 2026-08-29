from __future__ import annotations

import json
from pathlib import Path

from backend.app.agent_trace import AgentTrace, read_agent_trace
from evals.agent import cli
from evals.agent.cli import PACKAGE_DIR, main
from evals.agent.harness import load_dataset, run_evaluation
from evals.agent.reporting import evaluate_thresholds, load_thresholds, write_reports


def test_offline_dataset_and_standard_agent_metrics_are_deterministic() -> None:
    dataset = load_dataset(PACKAGE_DIR / "data" / "chinese_cases.json")
    assert len(dataset.cases) == 12
    assert all(case.source == "self_authored" for case in dataset.cases)

    first = run_evaluation(dataset)
    second = run_evaluation(dataset)
    # Compare deterministic quality/count metrics explicitly; wall-clock latency is observational.
    for mode in ("standard", "agent"):
        left = {key: value for key, value in first["modes"][mode].items() if key != "stage_latency_ms"}
        right = {key: value for key, value in second["modes"][mode].items() if key != "stage_latency_ms"}
        assert left == right

    assert first["modes"]["standard"]["task_success_rate"] == 1.0
    assert first["modes"]["agent"]["auto_repair_success_rate"] == 0.666667
    assert first["modes"]["agent"]["human_intervention_rate"] == 0.083333
    assert first["modes"]["agent"]["task_success_rate"] == 0.916667
    assert first["privacy"] == {
        "contains_user_storage_content": False,
        "contains_transcript_text": False,
        "contains_absolute_paths": False,
        "network_required": False,
    }
    encoded = json.dumps(first, ensure_ascii=False)
    assert dataset.cases[0].segments[0].text not in encoded


def test_reports_include_all_metrics_and_default_regression_passes(tmp_path: Path) -> None:
    report = run_evaluation(load_dataset(PACKAGE_DIR / "data" / "chinese_cases.json"))
    report["regression"] = evaluate_thresholds(
        report, load_thresholds(PACKAGE_DIR / "default_thresholds.json")
    )
    json_path, markdown_path = write_reports(report, tmp_path)

    assert report["regression"]["passed"] is True
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "agent-eval-v1"
    markdown = markdown_path.read_text(encoding="utf-8")
    for metric in (
        "animation_plan_schema_pass_rate",
        "transcript_grounding_precision",
        "time_interval_valid_rate",
        "overlap_violation_rate",
        "tool_call_success_rate",
        "auto_repair_success_rate",
        "average_retry_count",
        "human_intervention_rate",
        "task_success_rate",
    ):
        assert metric in markdown
    assert "P50" in markdown and "P95" in markdown


def test_cli_returns_nonzero_when_a_regression_gate_fails(tmp_path: Path, monkeypatch) -> None:
    thresholds = tmp_path / "strict_thresholds.json"
    thresholds.write_text(
        json.dumps(
            {
                "schema_version": "test",
                "modes": {"agent": {"task_success_rate": {"min": 1.0}}},
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "reports"
    monkeypatch.setattr(cli, "STORAGE_OUTPUT_ROOT", tmp_path)
    result = main(["--thresholds", str(thresholds), "--output-dir", str(output_dir)])

    assert result == 1
    payload = json.loads((output_dir / "agent_eval_report.json").read_text(encoding="utf-8"))
    assert payload["regression"]["passed"] is False


def test_cli_rejects_output_outside_project_storage(tmp_path: Path) -> None:
    try:
        cli._safe_output_dir(tmp_path)
    except ValueError as exc:
        assert str(exc) == "Agent eval output must stay inside project storage"
    else:
        raise AssertionError("outside output directory should have been rejected")


def test_agent_trace_v2_has_stable_run_node_tool_hierarchy_and_upgrades_v1(tmp_path: Path) -> None:
    task_id = "trace-hierarchy"
    trace = AgentTrace(tmp_path / task_id, task_id)
    trace.append(
        "tool_call",
        node="planning",
        tool_name="plan_animation",
        status="completed",
    )
    trace.append(
        "tool_call",
        node="planning",
        tool_name="plan_animation",
        status="completed",
    )
    payload = read_agent_trace(tmp_path / task_id, task_id)
    assert payload["schema_version"] == "agent-trace-v2"
    assert payload["run"] == {"run_id": task_id, "kind": "video_agent_workflow"}
    assert payload["entries"][0]["node_run_id"] == f"{task_id}:planning"
    assert payload["entries"][0]["tool_call_id"] == f"{task_id}:planning:plan_animation:1"
    assert payload["entries"][1]["tool_call_id"] == f"{task_id}:planning:plan_animation:2"

    legacy_id = "legacy-trace"
    legacy_dir = tmp_path / legacy_id
    legacy_dir.mkdir()
    (legacy_dir / "agent_trace.json").write_text(
        json.dumps(
            {
                "schema_version": "agent-trace-v1",
                "task_id": legacy_id,
                "workflow_mode": "agent",
                "prompt_version": "agent-planning-v1",
                "plan_schema_version": "animation-plan-v1",
                "planner": None,
                "summary": {"status": "running", "retry_count": 0, "last_failure_category": None},
                "entries": [
                    {"sequence": 1, "timestamp": "2026-01-01T00:00:00+00:00", "event_type": "tool_call", "node": "validation", "status": "completed"}
                ],
            }
        ),
        encoding="utf-8",
    )
    upgraded = read_agent_trace(legacy_dir, legacy_id)
    assert upgraded["schema_version"] == "agent-trace-v2"
    assert upgraded["entries"][0]["tool_call_id"] == f"{legacy_id}:validation:legacy_tool:1"
