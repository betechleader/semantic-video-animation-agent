from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import database, main
from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.media_assets import prepare_media_assets
from backend.app.models import TaskStatus
from backend.app.providers import TranscriptAnimationPlanningProvider
from backend.app.schemas import AnimationPlan, Transcript


def configure_database(tmp_path: Path, monkeypatch) -> Path:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    database._engine = None
    database._engine_path = None
    database._session_factory = None
    return storage


def completed_task(tmp_path: Path, monkeypatch) -> tuple[str, dict, dict]:
    storage = configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    (storage / task_id).mkdir(parents=True)
    transcript = create_mock_transcript()
    plan = create_mock_plan(transcript)
    metadata = {"duration_seconds": 5, "width": 320, "height": 568, "frame_rate": 30, "video_codec": "h264", "audio_codec": "aac", "has_video": True, "has_audio": True}
    database.create_task(task_id, metadata, "trace")
    database.transition_task(task_id, TaskStatus.COMPLETED, "Done", transcript=transcript.model_dump(), plan=plan.model_dump())
    return task_id, transcript.model_dump(), plan.model_dump()


def test_review_api_saves_valid_edits_and_starts_rerender(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))
    client = TestClient(main.app)
    response = client.post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})
    assert response.status_code == 202
    assert response.json()["status"] == "rendering"
    assert database.get_task(task_id)["status"] == "rendering"
    assert len(calls) == 1


def test_review_api_discards_saved_local_face_safe_placement(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    plan["face_regions"] = [{"timestamp_ms": 3000, "x": 8, "y": 8, "width": 170, "height": 190}]
    plan["media_placements"] = [{"animation_id": "animation_002", "corner": "top-right", "scale": 1, "skipped": False, "reason": "safe_corner"}]
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))
    response = TestClient(main.app).post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})
    assert response.status_code == 202, response.text
    assert calls[0][4].media_placements == []
    assert calls[0][4].face_regions == []


def test_review_api_accepts_disabled_media_visual_with_stale_derived_data(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    task_dir = tmp_path / "storage" / task_id
    prepared = prepare_media_assets(task_dir, AnimationPlan.model_validate(plan))
    plan = prepared.model_dump()
    plan["animations"][1]["parameters"]["enabled"] = False
    plan["media_placements"] = [{"animation_id": "animation_002", "corner": "top-right", "scale": 1, "skipped": False, "reason": "safe_corner"}]
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))

    response = TestClient(main.app).post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})

    assert response.status_code == 202, response.text
    reviewed = calls[0][4]
    assert reviewed.animations[1].parameters.enabled is False
    assert reviewed.media_assets == []
    assert reviewed.media_placements == []


def test_review_api_accepts_candidate_replacement_and_clears_old_audit(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))
    client = TestClient(main.app)
    candidate = client.post(f"/api/videos/{task_id}/media/candidates", json={
        "query": "learning", "source_url": "https://example.test/new.jpg", "title": "New learning visual",
    }).json()["candidate"]
    old_audits = prepare_media_assets(tmp_path / "storage" / task_id, AnimationPlan.model_validate(plan)).model_dump()["media_assets"]
    plan["animations"][1]["parameters"]["selected_candidate_id"] = candidate["id"]
    plan["media_assets"] = old_audits

    response = client.post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})

    assert response.status_code == 202, response.text
    assert calls[0][4].animations[1].parameters.selected_candidate_id == candidate["id"]
    assert calls[0][4].media_assets == []


def test_review_api_replans_when_transcript_text_changes(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    transcript["segments"][0]["text"] = "重新改写灰姑娘的故事"
    transcript["full_text"] = transcript["segments"][0]["text"]
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))

    response = TestClient(main.app).post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})

    assert response.status_code == 202, response.text
    assert response.json()["replanned"] is True
    reviewed_transcript, reviewed_plan = calls[0][3], calls[0][4]
    assert reviewed_transcript.segments[0].words[0].text == "重新改写灰姑娘的故事"
    assert any("灰姑娘" in animation.trigger_text or "灰姑娘" in str(animation.parameters) for animation in reviewed_plan.animations)


def test_review_api_applies_new_dictionary_rules_to_an_older_completed_task(tmp_path: Path, monkeypatch) -> None:
    storage = configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    (storage / task_id).mkdir(parents=True)
    transcript = Transcript.model_validate({
        "language": "zh", "full_text": "介绍三种对抑提高创新性的方法", "segments": [{
            "text": "介绍三种对抑提高创新性的方法", "start_ms": 0, "end_ms": 3000,
            "words": [
                {"text": "介绍三种", "start_ms": 0, "end_ms": 900},
                {"text": "对抑", "start_ms": 900, "end_ms": 1200},
                {"text": "提高创新性的方法", "start_ms": 1200, "end_ms": 3000},
            ],
        }],
    })
    plan = TranscriptAnimationPlanningProvider().plan(transcript)
    metadata = {"duration_seconds": 3, "width": 320, "height": 568, "frame_rate": 30, "video_codec": "h264", "audio_codec": "aac", "has_video": True, "has_audio": True}
    database.create_task(task_id, metadata, "trace")
    database.transition_task(task_id, TaskStatus.COMPLETED, "Done", transcript=transcript.model_dump(), plan=plan.model_dump())
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))

    response = TestClient(main.app).post(
        f"/api/videos/{task_id}/review",
        json={"transcript": transcript.model_dump(), "plan": plan.model_dump()},
    )

    assert response.status_code == 202, response.text
    assert response.json()["replanned"] is True
    assert calls[0][3].full_text == "介绍三种可以提高创新性的方法"


def test_review_api_rejects_ungrounded_plan_without_changing_task(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    plan["animations"][0]["start_ms"] = 0
    client = TestClient(main.app)
    response = client.post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})
    assert response.status_code == 422
    assert "fully contained" in response.json()["detail"]
    assert database.get_task(task_id)["status"] == "completed"


def test_events_support_after_event_cursor(tmp_path: Path, monkeypatch) -> None:
    task_id, _, _ = completed_task(tmp_path, monkeypatch)
    client = TestClient(main.app)
    events = database.get_task_events(task_id)
    response = client.get(f"/api/videos/{task_id}/events?after_event_id={events[-1]['id']}")
    assert response.status_code == 200
    assert response.text == ""


def test_media_review_api_lists_assets_and_accepts_a_manual_candidate(tmp_path: Path, monkeypatch) -> None:
    task_id, _, _ = completed_task(tmp_path, monkeypatch)
    client = TestClient(main.app)
    initial = client.get(f"/api/videos/{task_id}/media")
    assert initial.status_code == 200
    assert initial.json()["assets"] == []
    added = client.post(f"/api/videos/{task_id}/media/candidates", json={
        "query": "supermarket product", "source_url": "https://example.test/product.jpg", "title": "Product shelf",
    })
    assert added.status_code == 200, added.text
    assert added.json()["candidate"]["provider"] == "manual"
    listed = client.get(f"/api/videos/{task_id}/media")
    assert listed.status_code == 200
    assert listed.json()["candidates"][0]["source_url"] == "https://example.test/product.jpg"
