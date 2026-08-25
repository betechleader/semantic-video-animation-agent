from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.app import agent_workflow, database, main
from backend.app.agent_workflow import AgentCheckpointStore
from backend.app.agent_trace import read_agent_trace
from backend.app.schemas import Animation, AnimationPlan
from tests.test_agent_workflow import (
    RecordingServices,
    _create_task,
    _metadata,
    _plan,
    _wait_for_status,
    isolated_database,
)


def _pause_for_approval(storage_root: Path, task_id: str, services: RecordingServices):
    task_dir = _create_task(storage_root, task_id, approval_policy="always")
    store = AgentCheckpointStore.for_storage_root(storage_root)
    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=services.bundle(),
        checkpoint_store=store,
    )
    assert checkpoint["run_status"] == "awaiting_approval"
    return task_dir, store, checkpoint


def test_always_policy_pauses_and_restart_approve_resumes_at_render(isolated_database: Path) -> None:
    task_id = "agent-approval-restart"
    services = RecordingServices()
    task_dir, store, paused = _pause_for_approval(isolated_database, task_id, services)

    assert paused["next_node"] == "render"
    assert services.calls == [
        "audio_asr.extract", "audio_asr.transcribe", "correction", "planning", "validation"
    ]
    approval = database.get_agent_approval(task_id)
    assert approval["status"] == "pending"
    assert approval["reasons"][0]["code"] == "policy_always"
    assert database.decide_agent_approval(task_id, "approved", approval["candidate_plan"])

    before_resume = list(services.calls)
    started = agent_workflow.recover_agent_tasks(
        storage_root=isolated_database,
        services=services.bundle(),
        checkpoint_store=AgentCheckpointStore(store.path),
    )

    assert started == [task_id]
    assert _wait_for_status(task_id, "completed")["status"] == "completed"
    completed = AgentCheckpointStore(store.path).load(task_id)
    assert completed["run_status"] == "completed"
    assert services.calls == before_resume + ["render", "quality"]
    assert services.calls.count("audio_asr.transcribe") == 1
    assert services.calls.count("planning") == 1
    event_types = [event["type"] for event in database.get_task_events(task_id)]
    assert "awaiting_approval" in event_types
    assert "resumed" in event_types
    trace = read_agent_trace(task_dir, task_id)
    assert any(entry["event_type"] == "approval_decision" for entry in trace["entries"])


def test_reject_is_terminal_and_duplicate_decisions_conflict(isolated_database: Path) -> None:
    task_id = "agent-approval-reject"
    services = RecordingServices()
    task_dir, store, _paused = _pause_for_approval(isolated_database, task_id, services)

    decided = database.decide_agent_approval(task_id, "rejected")
    assert decided and decided["status"] == "rejected"
    assert database.decide_agent_approval(task_id, "approved", _plan().model_dump()) is None
    rejected = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=services.bundle(),
        checkpoint_store=store,
    )
    assert rejected["run_status"] == "rejected"
    assert database.get_task(task_id)["status"] == "rejected"
    assert services.calls.count("render") == 0
    trace = read_agent_trace(task_dir, task_id)
    assert trace["summary"]["status"] == "rejected"


def test_concurrent_approval_decisions_have_one_winner(isolated_database: Path) -> None:
    task_id = "agent-approval-concurrent"
    services = RecordingServices()
    _pause_for_approval(isolated_database, task_id, services)
    plan = _plan().model_dump()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda decision: database.decide_agent_approval(
                task_id, decision, plan if decision == "approved" else None
            ),
            ["approved", "rejected"],
        ))

    assert sum(result is not None for result in results) == 1
    assert database.get_agent_approval(task_id)["decision_version"] == 1


def test_pending_approval_can_be_cancelled_without_resuming_expensive_nodes(isolated_database: Path) -> None:
    task_id = "agent-approval-cancel"
    services = RecordingServices()
    task_dir, store, _paused = _pause_for_approval(isolated_database, task_id, services)
    before = list(services.calls)
    assert database.update_transcript(task_id, {"language": "zh"}) is False
    assert database.request_cancellation(task_id)

    cancelled = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=services.bundle(),
        checkpoint_store=store,
    )

    assert cancelled["run_status"] == "cancelled"
    assert database.get_task(task_id)["status"] == "cancelled"
    assert services.calls == before


def test_approval_api_validates_edits_and_is_idempotent(isolated_database: Path, monkeypatch) -> None:
    task_id = "33333333-3333-4333-8333-333333333333"
    services = RecordingServices()
    _task_dir, _store, _paused = _pause_for_approval(isolated_database, task_id, services)
    monkeypatch.setattr(main, "STORAGE_ROOT", isolated_database)
    monkeypatch.setattr(main, "_resume_after_approval", lambda _task_id: None)

    invalid = _plan().model_dump()
    invalid["animations"][0]["start_ms"] = 0
    with TestClient(main.app) as client:
        pending = client.get(f"/api/videos/{task_id}/approval")
        assert pending.status_code == 200
        assert pending.json()["status"] == "pending"
        invalid_edit = client.post(
            f"/api/videos/{task_id}/approval/edit", json={"plan": invalid}
        )
        assert invalid_edit.status_code == 422
        assert database.get_agent_approval(task_id)["status"] == "pending"

        edited = client.post(
            f"/api/videos/{task_id}/approval/edit", json={"plan": _plan().model_dump()}
        )
        assert edited.status_code == 202
        assert edited.json()["status"] == "edited"
        duplicate = client.post(f"/api/videos/{task_id}/approval/approve")
        assert duplicate.status_code == 409

    events = database.get_task_events(task_id)
    assert sum(event["type"] == "edited" for event in events) == 1


def test_approval_edit_rejects_renderer_safe_area_violation_before_resume(
    isolated_database: Path, monkeypatch
) -> None:
    task_id = "44444444-4444-4444-8444-444444444444"
    services = RecordingServices()
    _task_dir, _store, _paused = _pause_for_approval(isolated_database, task_id, services)
    monkeypatch.setattr(main, "STORAGE_ROOT", isolated_database)
    monkeypatch.setattr(main, "_resume_after_approval", lambda _task_id: None)
    unsafe = _plan().model_dump()
    unsafe["animations"][0]["parameters"]["text"] = "超长关键词" * 4

    with TestClient(main.app) as client:
        response = client.post(
            f"/api/videos/{task_id}/approval/edit", json={"plan": unsafe}
        )

    assert response.status_code == 422
    assert "safe area" in response.json()["detail"]
    approval = database.get_agent_approval(task_id)
    assert approval["status"] == "pending"
    assert approval["decision_version"] == 0
    assert services.calls.count("render") == 0


def test_on_risk_policy_flags_external_media_review(isolated_database: Path) -> None:
    task_id = "agent-on-risk-media"
    task_dir = _create_task(isolated_database, task_id, approval_policy="on_risk")
    services = RecordingServices()
    external = AnimationPlan(
        media_provider="knowledge",
        animations=[
            Animation(
                id="animation_external_risk",
                type="media_visual",
                template_id="media_visual_v1",
                start_ms=500,
                end_ms=2_500,
                trigger_text="已校正",
                parameters={
                    "asset_id": "media_external_risk",
                    "title": "外部素材",
                    "theme": "concept",
                    "accent_color": "#FFD400",
                    "search_query": "external concept",
                    "desired_asset_kind": "external_image",
                    "display_mode": "side_card",
                },
            )
        ],
    )
    services.build_plan = lambda *_args: external
    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=services.bundle(),
        checkpoint_store=AgentCheckpointStore.for_storage_root(isolated_database),
    )
    assert checkpoint["run_status"] == "awaiting_approval"
    assert [item["code"] for item in checkpoint["state"]["approval_reasons"]] == [
        "media_relevance_unverified",
        "external_media_rights_review",
    ]
