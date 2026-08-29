from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import database, main
from backend.app.models import TaskStatus
from backend.app.plan_patches import PlanPatchError, apply_plan_patch, build_rule_plan_patch
from backend.app.schemas import AnimationPlan, PlanPatch


def _transcript() -> dict:
    return {
        "language": "zh",
        "full_text": "前三秒说明重点",
        "segments": [{
            "text": "前三秒说明重点", "start_ms": 0, "end_ms": 2000,
            "words": [{"text": "前三秒说明重点", "start_ms": 0, "end_ms": 2000}],
        }],
    }


def _plan() -> dict:
    return {
        "media_provider": "mock",
        "animations": [{
            "id": "animation_intro", "type": "keyword_pop", "template_id": "keyword_pop_v1",
            "start_ms": 0, "end_ms": 1000, "trigger_text": "前三秒说明重点",
            "parameters": {"text": "说明重点", "color": "#FFFFFF", "position": "top-left"},
        }],
    }


def _configure(tmp_path: Path, monkeypatch) -> str:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    task_id = "agent-plan-patch-task"
    (storage / task_id).mkdir(parents=True)
    database.create_task(
        task_id,
        {"duration_seconds": 2, "width": 360, "height": 640, "frame_rate": 30, "video_codec": "h264", "audio_codec": "aac", "has_video": True, "has_audio": True},
        workflow_mode="agent",
        processing_profile="mock",
    )
    assert database.transition_task(task_id, TaskStatus.COMPLETED, "ready", transcript=_transcript(), plan=_plan())
    return task_id


def test_rule_patch_is_typed_and_checks_authoritative_before_snapshot() -> None:
    plan = AnimationPlan.model_validate(_plan())
    patch = build_rule_plan_patch("前三秒更抓人", plan)
    assert patch.schema_version == "plan-patch-v1"
    assert patch.operations[0].after.parameters.color == "#FFD166"
    changed = apply_plan_patch(plan, patch, [patch.operations[0].operation_id])
    assert changed.animations[0].parameters.position == "center"
    stale = plan.model_copy(deep=True)
    stale.animations[0].parameters.color = "#000000"
    try:
        apply_plan_patch(stale, patch, [patch.operations[0].operation_id])
    except PlanPatchError as exc:
        assert "formal plan changed" in str(exc)
    else:
        raise AssertionError("stale patch was accepted")


def test_combined_instruction_merges_changes_and_clears_renderer_owned_fields() -> None:
    data = _plan()
    data["animations"][0] = {
        "id": "animation_intro", "type": "media_visual", "template_id": "media_visual_v1",
        "start_ms": 0, "end_ms": 1000, "trigger_text": "前三秒说明重点",
        "parameters": {
            "asset_id": "media_intro", "title": "开场", "theme": "concept",
            "accent_color": "#FFFFFF", "search_query": "abstract concept",
            "desired_asset_kind": "external_image", "display_mode": "full_screen",
        },
    }
    plan = AnimationPlan.model_validate(data)
    patch = build_rule_plan_patch("前三秒更抓人，减少全屏素材", plan)
    assert len(patch.operations) == 1
    assert patch.operations[0].after.parameters.accent_color == "#FFD166"
    assert patch.operations[0].after.parameters.display_mode == "side_card"
    changed = apply_plan_patch(plan, patch, [patch.operations[0].operation_id])
    assert changed.media_assets == []
    assert changed.face_regions == []
    assert changed.media_placements == []


def test_malicious_or_out_of_range_patch_is_rejected_by_typed_boundary() -> None:
    before = _plan()["animations"][0]
    after = {**before, "id": "animation_other", "end_ms": 99_999}
    with pytest.raises(ValidationError):
        PlanPatch.model_validate({
            "schema_version": "plan-patch-v1",
            "operations": [{
                "operation_id": "operation_bad",
                "operation": "replace_animation",
                "target_animation_id": "animation_intro",
                "before": before,
                "after": after,
                "reason": "attempted authority bypass",
                "confidence": 1,
                "evidence_ids": [],
                "server_path": "D:/outside",
            }],
        })


def test_preview_approve_apply_and_undo_are_separate_and_versioned(tmp_path: Path, monkeypatch) -> None:
    task_id = _configure(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "_start_patch_render", lambda *_args: None)
    client = TestClient(main.app)
    assert client.get(f"/api/videos/{task_id}/plan-versions").json()["versions"] == []

    preview = client.post(
        f"/api/videos/{task_id}/plan-patches/preview",
        json={"instruction": "前三秒更抓人"},
    )
    assert preview.status_code == 201
    payload = preview.json()
    patch_id = payload["patch_id"]
    operation_id = payload["patch"]["operations"][0]["operation_id"]
    assert database.get_task(task_id)["plan"] == _plan()

    approved = client.post(
        f"/api/videos/{task_id}/plan-patches/{patch_id}/approve",
        json={"operation_ids": [operation_id]},
    )
    assert approved.status_code == 200
    assert database.get_task(task_id)["plan"] == _plan()

    applied = client.post(f"/api/videos/{task_id}/plan-patches/{patch_id}/apply")
    assert applied.status_code == 202
    assert applied.json()["plan_version"] == 2
    assert database.get_task(task_id)["plan"]["animations"][0]["parameters"]["color"] == "#FFD166"
    assert client.post(f"/api/videos/{task_id}/plan-patches/{patch_id}/apply").status_code == 409

    assert database.transition_task(task_id, TaskStatus.COMPLETED, "rendered")
    database.finish_plan_patch(task_id, patch_id, True)
    undone = client.post(f"/api/videos/{task_id}/plan-patches/undo")
    assert undone.status_code == 202
    assert undone.json()["plan_version"] == 3
    assert database.get_task(task_id)["plan"]["animations"][0]["parameters"]["color"] == "#FFFFFF"


def test_patch_reject_and_standard_boundary(tmp_path: Path, monkeypatch) -> None:
    task_id = _configure(tmp_path, monkeypatch)
    client = TestClient(main.app)
    preview = client.post(f"/api/videos/{task_id}/plan-patches/preview", json={"instruction": "前三秒更抓人"}).json()
    rejected = client.post(
        f"/api/videos/{task_id}/plan-patches/{preview['patch_id']}/reject",
        json={"reason": "Keep the original"},
    )
    assert rejected.status_code == 200
    assert client.post(f"/api/videos/{task_id}/plan-patches/{preview['patch_id']}/apply").status_code == 409

    standard_id = "standard-plan-patch-task"
    database.create_task(standard_id, {"duration_seconds": 2}, workflow_mode="standard")
    assert database.transition_task(standard_id, TaskStatus.COMPLETED, "ready", transcript=_transcript(), plan=_plan())
    response = client.post(f"/api/videos/{standard_id}/plan-patches/preview", json={"instruction": "前三秒更抓人"})
    assert response.status_code == 409
