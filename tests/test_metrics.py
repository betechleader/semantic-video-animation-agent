import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import database, main, workflow
from backend.app.metrics import TaskMetrics, initialize_initial_metrics
from backend.app.models import TaskStatus
from backend.app.processing import ProcessingError
from backend.app.schemas import VideoMetadata


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


def metadata() -> VideoMetadata:
    return VideoMetadata(
        duration_seconds=5, width=320, height=568, frame_rate=30, video_codec="h264",
        audio_codec="aac", has_video=True, has_audio=True,
    )


def create_metrics_task(tmp_path: Path, monkeypatch) -> tuple[Path, str]:
    storage = configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    task_dir = storage / task_id
    task_dir.mkdir(parents=True)
    database.create_task(task_id, metadata().model_dump(), trace_id="caller-supplied-trace")
    initialize_initial_metrics(task_dir, task_id, "caller-supplied-trace", 7)
    return task_dir, task_id


def test_metrics_api_is_read_only_and_excludes_sensitive_content(tmp_path: Path, monkeypatch) -> None:
    task_dir, task_id = create_metrics_task(tmp_path, monkeypatch)
    recorder = TaskMetrics(task_dir, task_id)
    attempt = recorder.current_or_start_attempt("initial")
    recorder.record_stage(attempt, "asr", lambda: None)
    recorder.finalize(attempt, "completed", output_quality={"width": 320, "height": 568, "has_audio": True})

    before = (task_dir / "metrics.json").read_bytes()
    response = TestClient(main.app).get(f"/api/videos/{task_id}/metrics")
    assert response.status_code == 200
    assert (task_dir / "metrics.json").read_bytes() == before
    metrics = response.json()
    assert metrics["trace_id_sha256"] != "caller-supplied-trace"
    assert metrics["privacy"]["local_only"] is True
    assert metrics["attempts"][0]["stages"]["upload_probe"]["duration_ms"] == 7
    serialized = json.dumps(metrics, ensure_ascii=False)
    assert str(task_dir.resolve()) not in serialized
    assert "caller-supplied-trace" not in serialized
    assert '"full_text"' not in serialized


def test_failed_and_cancelled_tasks_finalize_metrics(tmp_path: Path, monkeypatch) -> None:
    task_dir, task_id = create_metrics_task(tmp_path, monkeypatch)
    monkeypatch.setattr(workflow.AudioService, "extract_wav", lambda *_args: (_ for _ in ()).throw(ProcessingError("input path must stay private")))
    workflow.process_task(task_id, task_dir, metadata(), "caller-supplied-trace")
    failed = json.loads((task_dir / "metrics.json").read_text(encoding="utf-8"))
    assert database.get_task(task_id)["status"] == "failed"
    assert failed["status"] == "failed"
    assert failed["failure_category"] == "audio_extraction"
    assert failed["attempts"][0]["stages"]["audio_extraction"]["status"] == "failed"
    assert "input path must stay private" not in json.dumps(failed)

    cancelled_dir, cancelled_id = create_metrics_task(tmp_path / "cancelled", monkeypatch)
    assert database.request_cancellation(cancelled_id)
    workflow.process_task(cancelled_id, cancelled_dir, metadata(), "caller-supplied-trace")
    cancelled = json.loads((cancelled_dir / "metrics.json").read_text(encoding="utf-8"))
    assert database.get_task(cancelled_id)["status"] == "cancelled"
    assert cancelled["status"] == "cancelled"
    assert cancelled["failure_category"] == "cancelled"
    assert cancelled["attempts"][0]["stages"]["upload_probe"]["status"] == "completed"


def test_review_failure_is_recorded_as_a_separate_attempt(tmp_path: Path, monkeypatch) -> None:
    task_dir, task_id = create_metrics_task(tmp_path, monkeypatch)
    database.transition_task(task_id, TaskStatus.COMPLETED, "Done")
    TaskMetrics(task_dir, task_id).finalize(1, "completed")
    assert database.start_review_render(task_id, {"language": "zh", "full_text": "", "segments": []}, {"animations": []})
    attempt = TaskMetrics(task_dir, task_id).current_or_start_attempt("review")
    assert attempt == 2
    monkeypatch.setattr(workflow, "render_and_composite", lambda *_args, **_kwargs: (_ for _ in ()).throw(ProcessingError("private local path")))
    from backend.app.mock_services import create_mock_plan, create_mock_transcript

    transcript = create_mock_transcript()
    workflow.rerender_review(task_id, task_dir, metadata(), transcript, create_mock_plan(transcript), "caller-supplied-trace")
    metrics = json.loads((task_dir / "metrics.json").read_text(encoding="utf-8"))
    assert database.get_task(task_id)["status"] == "failed"
    assert metrics["attempts"][1]["kind"] == "review"
    assert metrics["attempts"][1]["status"] == "failed"
    assert metrics["attempts"][1]["failure_category"] == "review_rendering"
