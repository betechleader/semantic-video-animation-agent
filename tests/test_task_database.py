from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from backend.app import database
from backend.app.models import TaskStatus


def configure_test_database(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)


def test_existing_0001_task_gets_workflow_defaults_when_upgraded_to_head(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = Config(str(database.PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database._database_url(database.DATABASE_PATH))
    command.upgrade(config, "0001_task_models")

    legacy_engine = create_engine(database._database_url(database.DATABASE_PATH))
    with legacy_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO video_tasks (
                    task_id, status, metadata_json, trace_id, cancel_requested
                ) VALUES (
                    :task_id, :status, :metadata_json, :trace_id, :cancel_requested
                )
                """
            ),
            {
                "task_id": "legacy-task",
                "status": "PENDING",
                "metadata_json": '{"duration_seconds": 1.0}',
                "trace_id": "legacy-trace",
                "cancel_requested": False,
            },
        )
    legacy_engine.dispose()

    command.upgrade(config, "head")

    task = database.get_task("legacy-task")
    assert task is not None
    assert task["workflow_mode"] == "standard"
    assert task["processing_profile"] == "configured"
    assert task["media_provider"] == "mock"
    assert task["director_instruction"] is None
    assert task["approval_policy"] is None


def test_agent_director_instruction_survives_migration_and_standard_discards_it(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.create_task(
        "agent-directed",
        {},
        workflow_mode="agent",
        director_instruction="突出开场",
    )
    database.create_task(
        "standard-undirected",
        {},
        workflow_mode="standard",
        director_instruction="不应保存",
    )

    assert database.get_task("agent-directed")["director_instruction"] == "突出开场"
    assert database.get_task("standard-undirected")["director_instruction"] is None


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


def test_recoverable_tasks_include_only_nonterminal_agent_workflows(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.create_task("standard-pending", {}, workflow_mode="standard")
    database.create_task("agent-pending", {}, workflow_mode="agent")
    database.create_task("agent-processing", {}, workflow_mode="agent")
    database.create_task("agent-rendering", {}, workflow_mode="agent")
    database.create_task("agent-review-rendering", {}, workflow_mode="agent")
    database.create_task("agent-completed", {}, workflow_mode="agent")
    database.create_task("agent-failed", {}, workflow_mode="agent")
    database.create_task("agent-cancelled", {}, workflow_mode="agent")

    assert database.transition_task("agent-processing", TaskStatus.PROCESSING, "Processing")
    assert database.transition_task("agent-rendering", TaskStatus.RENDERING, "Rendering")
    assert database.transition_task("agent-review-rendering", TaskStatus.RENDERING, "Rendering")
    assert database.append_task_event(
        "agent-review-rendering",
        "review_rendering",
        "Review changes saved; rendering updated result",
        {"status": "rendering"},
    )
    assert database.transition_task("agent-completed", TaskStatus.COMPLETED, "Completed")
    assert database.transition_task("agent-failed", TaskStatus.FAILED, "Failed")
    assert database.transition_task("agent-cancelled", TaskStatus.CANCELLED, "Cancelled")

    recoverable = database.list_recoverable_agent_tasks()
    assert {task["task_id"] for task in recoverable} == {
        "agent-pending",
        "agent-processing",
        "agent-rendering",
    }
    assert all(task["workflow_mode"] == "agent" for task in recoverable)


def test_task_events_deduplicate_by_task_local_key(tmp_path: Path, monkeypatch) -> None:
    configure_test_database(tmp_path, monkeypatch)
    database.create_task("task-dedupe-a", {})
    database.create_task("task-dedupe-b", {})

    assert database.append_task_event(
        "task-dedupe-a",
        "agent_node_completed",
        "ASR completed",
        {"node": "audio_asr"},
        dedupe_key="node:audio_asr:completed",
    )
    assert not database.append_task_event(
        "task-dedupe-a",
        "agent_node_completed",
        "ASR completed again",
        {"node": "audio_asr"},
        dedupe_key="node:audio_asr:completed",
    )
    assert database.append_task_event(
        "task-dedupe-b",
        "agent_node_completed",
        "ASR completed",
        {"node": "audio_asr"},
        dedupe_key="node:audio_asr:completed",
    )

    task_a_events = database.get_task_events("task-dedupe-a")
    deduplicated = [event for event in task_a_events if event["dedupe_key"] == "node:audio_asr:completed"]
    assert len(deduplicated) == 1
    assert deduplicated[0]["message"] == "ASR completed"
