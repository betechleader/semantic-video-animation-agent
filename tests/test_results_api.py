from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.database import create_task


def test_task_lookup_and_download(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    create_task("task-001", {"duration_seconds": 2.0})
    (storage / "task-001").mkdir()
    (storage / "task-001" / "result.mp4").write_bytes(b"video")
    from backend.app.database import update_task
    update_task("task-001", "completed")
    client = TestClient(main.app)

    task = client.get("/api/videos/task-001")
    assert task.status_code == 200
    assert task.json()["status"] == "completed"
    download = client.get("/api/videos/task-001/download")
    assert download.status_code == 200
    assert download.content == b"video"


def test_missing_task_is_not_found() -> None:
    client = TestClient(main.app)
    assert client.get("/api/videos/missing").status_code == 404
