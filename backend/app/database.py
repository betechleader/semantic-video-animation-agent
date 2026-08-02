from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_PATH, PROJECT_ROOT, STORAGE_ROOT
from .models import TaskEvent, TaskStatus, VideoTask

_engine: Engine | None = None
_engine_path: Path | None = None
_session_factory: sessionmaker[Session] | None = None


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def get_engine() -> Engine:
    global _engine, _engine_path, _session_factory
    path = DATABASE_PATH.resolve()
    if _engine is None or _engine_path != path:
        path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(_database_url(path), connect_args={"check_same_thread": False})
        _engine_path = path
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Generator[Session, None, None]:
    get_engine()
    assert _session_factory is not None
    with _session_factory() as session:
        yield session


def initialize_database() -> None:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", _database_url(DATABASE_PATH))
    command.upgrade(config, "head")
    get_engine()


def _event(task_id: str, event_type: str, message: str, payload: dict | None = None) -> TaskEvent:
    return TaskEvent(task_id=task_id, event_type=event_type, message=message, payload=payload or {})


def create_task(task_id: str, metadata: dict, trace_id: str = "legacy") -> None:
    initialize_database()
    with next(get_session()) as session:
        session.add(VideoTask(task_id=task_id, status=TaskStatus.PENDING, metadata_json=metadata, trace_id=trace_id))
        session.add(_event(task_id, "created", "Upload accepted", {"status": TaskStatus.PENDING.value}))
        session.commit()


def transition_task(task_id: str, status: TaskStatus, message: str, *, transcript: dict | None = None, plan: dict | None = None, error: str | None = None) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return False
        if task.cancel_requested and status not in {TaskStatus.CANCELLED, TaskStatus.FAILED}:
            task.status = TaskStatus.CANCELLED
            session.add(_event(task_id, "cancelled", "Cancellation requested", {"status": TaskStatus.CANCELLED.value}))
            session.commit()
            return False
        task.status = status
        if transcript is not None:
            task.transcript_json = transcript
        if plan is not None:
            task.plan_json = plan
        task.error = error
        session.add(_event(task_id, status.value, message, {"status": status.value}))
        session.commit()
        return True


def request_cancellation(task_id: str) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return False
        task.cancel_requested = True
        session.add(_event(task_id, "cancel_requested", "Cancellation requested", {}))
        session.commit()
        return True


def is_cancellation_requested(task_id: str) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        return bool(task and task.cancel_requested)


def is_terminal(task_id: str) -> bool:
    task = get_task(task_id)
    return task is None or task["status"] in {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value}


def update_task(task_id: str, status: str, transcript: dict | None = None, plan: dict | None = None, error: str | None = None) -> None:
    """Compatibility adapter for the phase-one API while services migrate."""
    transition_task(task_id, TaskStatus(status), f"Task {status}", transcript=transcript, plan=plan, error=error)


def get_task(task_id: str) -> dict | None:
    initialize_database()
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None:
            return None
        return {
            "task_id": task.task_id, "status": task.status.value,
            "metadata": task.metadata_json, "transcript": task.transcript_json,
            "plan": task.plan_json, "error": task.error, "trace_id": task.trace_id,
            "cancel_requested": task.cancel_requested,
        }


def get_task_events(task_id: str) -> list[dict]:
    initialize_database()
    with next(get_session()) as session:
        events = session.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.id)).all()
        return [{"id": event.id, "type": event.event_type, "message": event.message, "payload": event.payload, "created_at": event.created_at.isoformat()} for event in events]


def update_transcript(task_id: str, transcript: dict) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status in {TaskStatus.PROCESSING, TaskStatus.RENDERING}:
            return False
        task.transcript_json = transcript
        session.add(_event(task_id, "transcript_updated", "Transcript updated", {}))
        session.commit()
        return True


def start_review_render(task_id: str, transcript: dict, plan: dict) -> bool:
    """Persist a user-approved review edit and return a completed task to rendering."""
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status != TaskStatus.COMPLETED:
            return False
        task.status = TaskStatus.RENDERING
        task.transcript_json = transcript
        task.plan_json = plan
        task.error = None
        task.cancel_requested = False
        session.add(_event(task_id, "review_rendering", "Review changes saved; rendering updated result", {"status": TaskStatus.RENDERING.value}))
        session.commit()
        return True
