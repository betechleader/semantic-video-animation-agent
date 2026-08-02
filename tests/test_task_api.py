from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import database, main


def configure_database(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    database._engine = None
    database._engine_path = None
    database._session_factory = None


def test_trace_header_and_event_replay(tmp_path, monkeypatch) -> None:
    configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    database.create_task(task_id, {"duration_seconds": 1}, trace_id="trace-test")
    client = TestClient(main.app)
    response = client.get(f"/api/videos/{task_id}", headers={"X-Trace-ID": "caller-trace"})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "caller-trace"
    events = client.get(f"/api/videos/{task_id}/events")
    assert events.status_code == 200
    assert "event: created" in events.text
    assert "trace-test" not in events.text


def test_task_cancellation_is_persisted(tmp_path, monkeypatch) -> None:
    configure_database(tmp_path, monkeypatch)
    task_id = str(uuid4())
    database.create_task(task_id, {}, trace_id="trace-test")
    client = TestClient(main.app)
    response = client.post(f"/api/videos/{task_id}/cancel")
    assert response.status_code == 202
    assert database.get_task(task_id)["cancel_requested"] is True
