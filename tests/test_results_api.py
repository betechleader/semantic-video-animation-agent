from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.database import create_task


def test_task_lookup_and_download(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    task_id = str(uuid4())
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    create_task(task_id, {"duration_seconds": 2.0})
    (storage / task_id).mkdir()
    (storage / task_id / "result.mp4").write_bytes(b"video")
    from backend.app.database import update_task
    update_task(task_id, "completed")
    client = TestClient(main.app)

    task = client.get(f"/api/videos/{task_id}")
    assert task.status_code == 200
    assert task.json()["status"] == "completed"
    download = client.get(f"/api/videos/{task_id}/download")
    assert download.status_code == 200
    assert download.content == b"video"
    assert download.headers["content-disposition"].startswith("attachment;")

    preview = client.get(f"/api/videos/{task_id}/download?preview=true", headers={"Range": "bytes=0-1"})
    assert preview.status_code == 206
    assert preview.content == b"vi"
    assert preview.headers["content-disposition"] == "inline"
    assert preview.headers["accept-ranges"] == "bytes"


def test_missing_task_is_not_found() -> None:
    client = TestClient(main.app)
    assert client.get("/api/videos/missing").status_code == 404
