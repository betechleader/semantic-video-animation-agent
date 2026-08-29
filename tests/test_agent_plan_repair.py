from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import agent_workflow, database, main
from backend.app.agent_tools import PlanningToolInput, PlanningToolOutput
from backend.app.agent_trace import read_agent_trace
from backend.app.agent_workflow import AgentCheckpointStore, AgentWorkflowServices
from backend.app.planning_rules import validate_animation_plan
from backend.app.schemas import AnimationPlan
from tests.test_agent_workflow import (
    RecordingServices,
    _create_task,
    _metadata,
    _plan,
    isolated_database,
)


class ScriptedPlannerServices(RecordingServices):
    def __init__(self, candidates: list[dict]) -> None:
        super().__init__()
        self.candidates = candidates
        self.planning_inputs: list[PlanningToolInput] = []

    def bundle(self) -> AgentWorkflowServices:
        base = super().bundle()
        return AgentWorkflowServices(
            extract_audio=base.extract_audio,
            transcribe_audio=base.transcribe_audio,
            correct_asr_transcript=base.correct_asr_transcript,
            build_animation_plan=base.build_animation_plan,
            plan_agent_candidate=self.plan_candidate,
            validate_plan=base.validate_plan,
            render_and_composite_video=base.render_and_composite_video,
            verify_and_write_output_quality=base.verify_and_write_output_quality,
        )

    def plan_candidate(
        self,
        tool_input: PlanningToolInput,
        processing_profile: str,
        media_provider: str | None,
    ) -> PlanningToolOutput:
        self.calls.append("planning")
        self.planning_inputs.append(tool_input)
        assert processing_profile == "mock"
        assert media_provider == "mock"
        index = min(len(self.planning_inputs) - 1, len(self.candidates) - 1)
        return PlanningToolOutput(
            candidate=self.candidates[index],
            planner_id="scripted",
            model_id="scripted-v1",
        )

    def validate_plan(self, plan: AnimationPlan, transcript) -> AnimationPlan:
        self.calls.append("validation")
        return validate_animation_plan(plan, transcript)


def invalid_schema_candidate() -> dict:
    return {"media_provider": "mock", "animations": []}


def invalid_rule_candidate() -> dict:
    candidate = _plan().model_dump()
    candidate["animations"][0]["start_ms"] = 0
    return candidate


def test_invalid_first_plan_is_repaired_once_and_trace_is_redacted(isolated_database: Path) -> None:
    task_id = "agent-repair-success"
    task_dir = _create_task(isolated_database, task_id)
    instruction = "前三秒突出结构化输出"
    services = ScriptedPlannerServices([invalid_schema_candidate(), _plan().model_dump()])

    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        instruction,
        services=services.bundle(),
        checkpoint_store=AgentCheckpointStore.for_storage_root(isolated_database),
    )

    assert checkpoint["run_status"] == "completed"
    assert checkpoint["state"]["repair_attempts"] == 1
    assert [item.repair_attempt for item in services.planning_inputs] == [0, 1]
    assert services.planning_inputs[0].director_instruction == instruction
    assert services.planning_inputs[1].violations[0].code.startswith("schema.")
    trace = read_agent_trace(task_dir, task_id)
    assert trace is not None
    assert trace["summary"] == {
        "status": "completed",
        "retry_count": 1,
        "last_failure_category": None,
    }
    encoded = json.dumps(trace, ensure_ascii=False)
    assert instruction not in encoded
    assert "已校正" not in encoded
    assert str(task_dir.resolve()) not in encoded
    assert trace["planner"]["planner_id"] == "scripted"
    assert trace["planner"]["model_id"] == "scripted-v1"
    assert trace["prompt_version"] == "agent-planning-v2-rag"
    assert trace["plan_schema_version"] == "animation-plan-v2-evidence"
    assert any(entry["event_type"] == "validation_error" for entry in trace["entries"])
    assert any(entry["event_type"] == "retry" for entry in trace["entries"])
    completed_node_runs = {
        entry["node"]
        for entry in trace["entries"]
        if entry["event_type"] == "node_run" and entry["status"] == "completed"
    }
    assert completed_node_runs == set(agent_workflow.AGENT_NODES)


def test_persistent_invalid_plan_stops_after_two_repairs_for_human_approval(isolated_database: Path) -> None:
    task_id = "agent-repair-exhausted"
    task_dir = _create_task(isolated_database, task_id)
    services = ScriptedPlannerServices([invalid_rule_candidate()])

    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        "不要遮挡人脸",
        services=services.bundle(),
        checkpoint_store=AgentCheckpointStore.for_storage_root(isolated_database),
    )

    assert checkpoint["run_status"] == "awaiting_approval"
    assert checkpoint["next_node"] == "render"
    assert checkpoint["state"]["approval_reasons"][0]["code"] == "plan_repair_exhausted"
    assert [item.repair_attempt for item in services.planning_inputs] == [0, 1, 2]
    assert all(
        item.violations[0].code == "planning_rule"
        for item in services.planning_inputs[1:]
    )
    assert services.calls.count("render") == 0
    task = database.get_task(task_id)
    assert task["status"] == "awaiting_approval"
    approval = database.get_agent_approval(task_id)
    assert approval["status"] == "pending"
    assert approval["candidate_plan"] is None
    assert approval["violations"][0]["code"] == "planning_rule"
    trace = read_agent_trace(task_dir, task_id)
    assert trace["summary"] == {
        "status": "awaiting_approval",
        "retry_count": 2,
        "last_failure_category": "plan_repair_exhausted",
    }
    assert sum(entry["event_type"] == "retry" for entry in trace["entries"]) == 2


def test_agent_trace_api_is_agent_only_and_returns_audit(isolated_database: Path, monkeypatch) -> None:
    agent_id = "11111111-1111-4111-8111-111111111111"
    agent_dir = _create_task(isolated_database, agent_id)
    standard_id = "22222222-2222-4222-8222-222222222222"
    _create_task(isolated_database, standard_id, workflow_mode="standard")
    services = ScriptedPlannerServices([_plan().model_dump()])
    agent_workflow.run_agent_task(
        agent_id,
        agent_dir,
        _metadata(),
        f"trace-{agent_id}",
        "mock",
        "mock",
        services=services.bundle(),
        checkpoint_store=AgentCheckpointStore.for_storage_root(isolated_database),
    )
    monkeypatch.setattr(main, "STORAGE_ROOT", isolated_database)

    with TestClient(main.app) as client:
        response = client.get(f"/api/videos/{agent_id}/agent-trace")
        assert response.status_code == 200
        assert response.json()["summary"]["retry_count"] == 0
        standard = client.get(f"/api/videos/{standard_id}/agent-trace")
        assert standard.status_code == 409
