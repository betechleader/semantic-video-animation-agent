import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import database, main
from backend.app.audio import AudioService


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


def test_audio_service_extracts_mono_wav(tmp_path: Path, monkeypatch) -> None:
    storage = configure_database(tmp_path, monkeypatch)
    task_dir = storage / str(uuid4())
    task_dir.mkdir(parents=True)
    source = task_dir / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", str(source)], capture_output=True, check=True)
    wav = AudioService().extract_wav(source, task_dir / "audio.wav")
    assert wav.is_file() and wav.stat().st_size > 0


def test_completed_task_transcript_can_be_edited(tmp_path: Path, monkeypatch) -> None:
    configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    database.create_task(task_id, {}, "trace")
    database.transition_task(task_id, database.TaskStatus.COMPLETED, "Done")
    client = TestClient(main.app)
    response = client.put(f"/api/videos/{task_id}/transcript", json={
        "language": "zh", "full_text": "已编辑", "segments": [{"text": "已编辑", "start_ms": 0, "end_ms": 1000, "words": [{"text": "已编辑", "start_ms": 0, "end_ms": 1000}]}],
    })
    assert response.status_code == 200
    assert database.get_task(task_id)["transcript"]["full_text"] == "已编辑"
