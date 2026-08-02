from pathlib import Path

from backend.app import database
from backend.app.models import TaskStatus


def configure_test_database(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    database._engine = None
    database._engine_path = None
    database._session_factory = None


def test_migration_persists_task_state_and_events(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.create_task("task-001", {"duration_seconds": 1.0}, trace_id="trace-001")
    assert database.transition_task("task-001", TaskStatus.PROCESSING, "Processing started")
    assert database.transition_task("task-001", TaskStatus.COMPLETED, "Processing completed", transcript={"language": "zh"}, plan={"animations": []})

    task = database.get_task("task-001")
    assert task is not None
    assert task["status"] == "completed"
    assert task["trace_id"] == "trace-001"
    assert [event["type"] for event in database.get_task_events("task-001")] == ["created", "processing", "completed"]


def test_cancellation_prevents_nonterminal_transition(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.create_task("task-002", {}, trace_id="trace-002")
    assert database.request_cancellation("task-002")
    assert not database.transition_task("task-002", TaskStatus.PROCESSING, "Processing started")
    assert database.get_task("task-002")["status"] == "cancelled"
