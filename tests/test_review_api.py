from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import database, main
from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.models import TaskStatus


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


def test_review_api_accepts_saved_local_face_safe_placement(tmp_path: Path, monkeypatch) -> None:
    task_id, transcript, plan = completed_task(tmp_path, monkeypatch)
    plan["face_regions"] = [{"timestamp_ms": 3000, "x": 8, "y": 8, "width": 170, "height": 190}]
    plan["media_placements"] = [{"animation_id": "animation_002", "corner": "top-right", "scale": 1, "skipped": False, "reason": "safe_corner"}]
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))
    response = TestClient(main.app).post(f"/api/videos/{task_id}/review", json={"transcript": transcript, "plan": plan})
    assert response.status_code == 202, response.text
    assert calls[0][4].media_placements[0].corner == "top-right"


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
