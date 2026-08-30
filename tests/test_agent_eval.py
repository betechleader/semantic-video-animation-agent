from __future__ import annotations

import json
from pathlib import Path

from backend.app.agent_tools import PlanningToolInput
from backend.app.agent_trace import AgentTrace, read_agent_trace
from evals.agent import cli
from evals.agent.cli import PACKAGE_DIR, main
from evals.agent.harness import load_dataset, run_evaluation
from evals.agent.multi_agent import (
    critic_violations,
    no_evidence_search,
    run_critic,
    run_planner,
    run_researcher,
)
from evals.agent.reporting import (
    evaluate_multi_agent_promotion,
    evaluate_thresholds,
    load_promotion_policy,
    load_thresholds,
    write_reports,
)


def test_offline_dataset_and_standard_agent_metrics_are_deterministic() -> None:
    dataset = load_dataset(PACKAGE_DIR / "data" / "chinese_cases.json")
    assert len(dataset.cases) == 12
    assert all(case.source == "self_authored" for case in dataset.cases)

    first = run_evaluation(dataset)
    second = run_evaluation(dataset)
    # Compare deterministic quality/count metrics explicitly; wall-clock latency is observational.
    for mode in ("standard", "agent"):
        left = {
            key: value
            for key, value in first["modes"][mode].items()
            if key not in {"stage_latency_ms", "run_latency_ms"}
        }
        right = {
            key: value
            for key, value in second["modes"][mode].items()
            if key not in {"stage_latency_ms", "run_latency_ms"}
        }
        assert left == right

    assert first["modes"]["standard"]["task_success_rate"] == 1.0
    assert first["modes"]["agent"]["auto_repair_success_rate"] == 0.666667
    assert first["modes"]["agent"]["human_intervention_rate"] == 0.083333
    assert first["modes"]["agent"]["task_success_rate"] == 0.916667
    assert first["modes"]["agent"]["evidence_retrieval_hit_rate"] == 1.0
    assert first["modes"]["agent"]["citation_correctness_rate"] == 1.0
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
    assert json.loads(json_path.read_text(encoding="utf-8"))["schema_version"] == "agent-eval-v3-multi-agent"
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
        "evidence_retrieval_hit_rate",
        "citation_correctness_rate",
    ):
        assert metric in markdown
    assert "P50" in markdown and "P95" in markdown


def test_multi_agent_experiment_is_flagged_typed_and_not_promoted_without_gain() -> None:
    dataset = load_dataset(PACKAGE_DIR / "data" / "chinese_cases.json")
    report = run_evaluation(dataset, enable_multi_agent_experiment=True)
    promotion = evaluate_multi_agent_promotion(
        report,
        load_promotion_policy(PACKAGE_DIR / "multi_agent_promotion.json"),
    )
    report["multi_agent_experiment"]["promotion"] = promotion

    experiment = report["multi_agent_experiment"]
    assert experiment["enabled"] is True
    assert experiment["default_workflow_changed"] is False
    assert experiment["roles"] == {
        "researcher": "evidence_and_material_candidates_only",
        "planner": "animation_plan_candidate_only",
        "critic": "structured_issues_and_suggestions_only",
    }
    assert report["modes"]["multi_agent"]["task_success_rate"] == 1.0
    assert report["modes"]["multi_agent"]["human_intervention_rate"] == 0.0
    assert promotion["passed"] is False
    assert promotion["decision"] == "keep_single_agent_default"
    failed = [item for item in promotion["checks"] if not item["passed"]]
    assert failed == [
        {
            "kind": "quality_delta",
            "metric": "task_success_rate",
            "actual": 0.083333,
            "min": 0.1,
            "max": None,
            "passed": False,
        }
    ]

    multi_runs = [item for item in report["runs"] if item["mode"] == "multi_agent"]
    assert len(multi_runs) == 12
    assert all(
        call["tool_name"]
        in {
            "research_evidence_and_materials",
            "multi_agent_planner",
            "structured_plan_critic",
        }
        for run in multi_runs
        for call in run["calls"]
    )
    assert "render" not in json.dumps(multi_runs)
    encoded = json.dumps(report, ensure_ascii=False)
    assert dataset.cases[0].segments[0].text not in encoded


def test_cli_feature_flag_writes_multi_agent_decision(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "multi-agent-report"
    monkeypatch.setattr(cli, "STORAGE_OUTPUT_ROOT", tmp_path)

    result = main(
        [
            "--enable-multi-agent-experiment",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert result == 0
    payload = json.loads(
        (output_dir / "agent_eval_report.json").read_text(encoding="utf-8")
    )
    assert payload["multi_agent_experiment"]["promotion"]["decision"] == (
        "keep_single_agent_default"
    )
    markdown = (output_dir / "agent_eval_report.md").read_text(encoding="utf-8")
    assert "Feature-flagged multi-Agent experiment" in markdown
    assert "structured issues/suggestions; no render" in markdown


def test_multi_agent_roles_have_non_overlapping_typed_outputs() -> None:
    case = load_dataset(PACKAGE_DIR / "data" / "chinese_cases.json").cases[-1]
    transcript = case.transcript()
    research = run_researcher(transcript, no_evidence_search)
    assert set(research.model_dump()) == {
        "evidence",
        "material_candidates",
        "retrieval_errors",
    }

    first_candidate = run_planner(
        PlanningToolInput(transcript=transcript, repair_attempt=0),
        scenario="persistent_overlap",
        critic_issues=[],
    )
    critique = run_critic(transcript, first_candidate)
    assert critique.valid is False
    assert set(critique.model_dump()) == {"valid", "issues"}
    assert all(issue.suggestion for issue in critique.issues)

    repaired_candidate = run_planner(
        PlanningToolInput(
            transcript=transcript,
            repair_attempt=1,
            violations=critic_violations(critique.issues),
        ),
        scenario="persistent_overlap",
        critic_issues=critique.issues,
    )
    assert run_critic(transcript, repaired_candidate).valid is True


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
