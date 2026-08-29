from collections.abc import Generator
from pathlib import Path
from threading import Lock

from alembic import command
from alembic.config import Config
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .config import DATABASE_PATH, PROJECT_ROOT, STORAGE_ROOT
from .models import AgentApproval, AgentPlanPatch, ApprovalPolicy, PlanVersion, TaskEvent, TaskStatus, VideoTask, WorkflowMode

_engine: Engine | None = None
_engine_path: Path | None = None
_session_factory: sessionmaker[Session] | None = None
_initialization_lock = Lock()


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
    # A task worker and an API request can both reach this function. Alembic's
    # module-level environment is not safe to initialise concurrently.
    with _initialization_lock:
        STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", _database_url(DATABASE_PATH))
        command.upgrade(config, "head")
        get_engine()


def _event(
    task_id: str,
    event_type: str,
    message: str,
    payload: dict | None = None,
    *,
    dedupe_key: str | None = None,
) -> TaskEvent:
    return TaskEvent(
        task_id=task_id,
        event_type=event_type,
        message=message,
        payload=payload or {},
        dedupe_key=dedupe_key,
    )


def create_task(
    task_id: str,
    metadata: dict,
    trace_id: str = "legacy",
    *,
    workflow_mode: WorkflowMode | str = WorkflowMode.STANDARD,
    processing_profile: str = "configured",
    media_provider: str = "mock",
    director_instruction: str | None = None,
    approval_policy: ApprovalPolicy | str = ApprovalPolicy.NEVER,
) -> None:
    initialize_database()
    normalized_workflow_mode = WorkflowMode(workflow_mode)
    normalized_approval_policy = (
        ApprovalPolicy(approval_policy)
        if normalized_workflow_mode == WorkflowMode.AGENT
        else ApprovalPolicy.NEVER
    )
    with next(get_session()) as session:
        session.add(
            VideoTask(
                task_id=task_id,
                status=TaskStatus.PENDING,
                workflow_mode=normalized_workflow_mode,
                processing_profile=processing_profile,
                media_provider=media_provider,
                director_instruction=director_instruction if normalized_workflow_mode == WorkflowMode.AGENT else None,
                approval_policy=normalized_approval_policy,
                metadata_json=metadata,
                trace_id=trace_id,
            )
        )
        session.add(_event(task_id, "created", "Upload accepted", {"status": TaskStatus.PENDING.value}))
        session.commit()


def append_task_event(
    task_id: str,
    event_type: str,
    message: str,
    payload: dict | None = None,
    *,
    dedupe_key: str | None = None,
) -> bool:
    """Append an event, returning false when its task-local dedupe key already exists."""
    initialize_database()
    with next(get_session()) as session:
        session.add(_event(task_id, event_type, message, payload, dedupe_key=dedupe_key))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            if dedupe_key is None:
                raise
            duplicate = session.scalar(
                select(TaskEvent.id).where(
                    TaskEvent.task_id == task_id,
                    TaskEvent.dedupe_key == dedupe_key,
                )
            )
            if duplicate is None:
                raise
            return False
        return True


def transition_task(task_id: str, status: TaskStatus, message: str, *, transcript: dict | None = None, plan: dict | None = None, error: str | None = None) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status in {
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.REJECTED
        }:
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
        if task is None or task.status in {
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.REJECTED
        }:
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
    return task is None or task["status"] in {
        TaskStatus.COMPLETED.value, TaskStatus.FAILED.value,
        TaskStatus.CANCELLED.value, TaskStatus.REJECTED.value,
    }


def update_task(task_id: str, status: str, transcript: dict | None = None, plan: dict | None = None, error: str | None = None) -> None:
    """Compatibility adapter for the phase-one API while services migrate."""
    transition_task(task_id, TaskStatus(status), f"Task {status}", transcript=transcript, plan=plan, error=error)


def _serialize_task(task: VideoTask) -> dict:
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "metadata": task.metadata_json,
        "transcript": task.transcript_json,
        "plan": task.plan_json,
        "error": task.error,
        "trace_id": task.trace_id,
        "cancel_requested": task.cancel_requested,
        "workflow_mode": task.workflow_mode.value,
        "processing_profile": task.processing_profile,
        "media_provider": task.media_provider,
        "director_instruction": task.director_instruction if task.workflow_mode == WorkflowMode.AGENT else None,
        "approval_policy": (
            task.approval_policy.value if task.workflow_mode == WorkflowMode.AGENT else None
        ),
    }


def get_task(task_id: str) -> dict | None:
    initialize_database()
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        return None if task is None else _serialize_task(task)


def list_recoverable_agent_tasks() -> list[dict]:
    initialize_database()
    terminal_statuses = (
        TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.REJECTED
    )
    with next(get_session()) as session:
        # A completed Agent task may temporarily return to RENDERING through
        # the existing manual-review flow. Its graph checkpoint is already
        # terminal, so startup recovery must not overwrite that review with
        # the original Agent result. Review-worker recovery is a later phase.
        review_rendering_tasks = select(TaskEvent.task_id).where(
            TaskEvent.event_type == "review_rendering"
        )
        tasks = session.scalars(
            select(VideoTask)
            .where(
                VideoTask.workflow_mode == WorkflowMode.AGENT,
                VideoTask.status.not_in(terminal_statuses),
                VideoTask.task_id.not_in(review_rendering_tasks),
            )
            .order_by(VideoTask.created_at, VideoTask.task_id)
        ).all()
        return [_serialize_task(task) for task in tasks]


def get_task_events(task_id: str) -> list[dict]:
    initialize_database()
    with next(get_session()) as session:
        events = session.scalars(select(TaskEvent).where(TaskEvent.task_id == task_id).order_by(TaskEvent.id)).all()
        return [
            {
                "id": event.id,
                "type": event.event_type,
                "message": event.message,
                "payload": event.payload,
                "dedupe_key": event.dedupe_key,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]


def update_transcript(task_id: str, transcript: dict) -> bool:
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status in {
            TaskStatus.PROCESSING, TaskStatus.RENDERING, TaskStatus.AWAITING_APPROVAL,
            TaskStatus.REJECTED,
        }:
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


def create_pending_approval(
    task_id: str,
    policy: str,
    reasons: list[dict],
    candidate_plan: dict | None,
    violations: list[dict],
) -> dict:
    """Persist one approval request without replacing an existing decision."""

    with next(get_session()) as session:
        approval = session.get(AgentApproval, task_id)
        if approval is None:
            approval = AgentApproval(
                task_id=task_id,
                status="pending",
                policy=policy,
                reasons_json=reasons,
                candidate_plan_json=candidate_plan,
                violations_json=violations,
            )
            session.add(approval)
        session.commit()
        return _serialize_approval(approval)


def _serialize_approval(approval: AgentApproval) -> dict:
    return {
        "task_id": approval.task_id,
        "status": approval.status,
        "policy": approval.policy,
        "reasons": approval.reasons_json,
        "candidate_plan": approval.candidate_plan_json,
        "violations": approval.violations_json,
        "decision_version": approval.decision_version,
        "created_at": approval.created_at.isoformat(),
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }


def get_agent_approval(task_id: str) -> dict | None:
    initialize_database()
    with next(get_session()) as session:
        approval = session.get(AgentApproval, task_id)
        return None if approval is None else _serialize_approval(approval)


def decide_agent_approval(task_id: str, decision: str, plan: dict | None = None) -> dict | None:
    """Atomically accept exactly one decision for a pending approval."""

    if decision not in {"approved", "edited", "rejected"}:
        raise ValueError("Unsupported Agent approval decision")
    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        if task is None or task.status != TaskStatus.AWAITING_APPROVAL:
            return None
        values: dict = {
            "status": decision,
            "decision_version": AgentApproval.decision_version + 1,
            "decided_at": datetime.now(timezone.utc),
        }
        if plan is not None:
            values["candidate_plan_json"] = plan
            values["violations_json"] = []
        result = session.execute(
            update(AgentApproval)
            .where(AgentApproval.task_id == task_id, AgentApproval.status == "pending")
            .values(**values)
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        approval = session.get(AgentApproval, task_id)
        assert approval is not None
        return _serialize_approval(approval)


def _latest_plan_version(session: Session, task_id: str) -> int:
    return int(session.scalar(select(func.max(PlanVersion.version)).where(PlanVersion.task_id == task_id)) or 0)


def _version_plan(plan: dict) -> dict:
    normalized = dict(plan)
    normalized["media_assets"] = []
    normalized["face_regions"] = []
    normalized["media_placements"] = []
    return normalized


def ensure_plan_version(task_id: str, plan: dict) -> int:
    """Return the current version, creating the immutable baseline when needed."""

    initialize_database()
    with next(get_session()) as session:
        latest = _latest_plan_version(session, task_id)
        plan = _version_plan(plan)
        if latest == 0:
            session.add(PlanVersion(task_id=task_id, version=1, plan_json=plan, source="baseline"))
            session.commit()
            return 1
        row = session.scalar(select(PlanVersion).where(PlanVersion.task_id == task_id, PlanVersion.version == latest))
        if row is None or row.plan_json != plan:
            latest += 1
            session.add(PlanVersion(task_id=task_id, version=latest, plan_json=plan, source="external_review"))
            session.commit()
        return latest


def _serialize_plan_patch(row: AgentPlanPatch) -> dict:
    return {
        "patch_id": row.patch_id,
        "task_id": row.task_id,
        "status": row.status,
        "base_version": row.base_version,
        "patch": row.patch_json,
        "approved_operation_ids": row.approved_operation_ids_json,
        "resulting_version": row.resulting_version,
        "rejection_reason": row.rejection_reason,
        "instruction_sha256": row.instruction_sha256,
        "created_at": row.created_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def create_plan_patch(task_id: str, patch_id: str, instruction_sha256: str, base_version: int, patch: dict) -> dict:
    with next(get_session()) as session:
        row = AgentPlanPatch(
            patch_id=patch_id,
            task_id=task_id,
            status="pending",
            instruction_sha256=instruction_sha256,
            base_version=base_version,
            patch_json=patch,
            approved_operation_ids_json=[],
        )
        session.add(row)
        session.commit()
        return _serialize_plan_patch(row)


def get_plan_patch(task_id: str, patch_id: str) -> dict | None:
    initialize_database()
    with next(get_session()) as session:
        row = session.get(AgentPlanPatch, patch_id)
        return None if row is None or row.task_id != task_id else _serialize_plan_patch(row)


def list_plan_versions(task_id: str) -> list[dict]:
    initialize_database()
    with next(get_session()) as session:
        rows = session.scalars(select(PlanVersion).where(PlanVersion.task_id == task_id).order_by(PlanVersion.version)).all()
        return [{"version": row.version, "source": row.source, "source_patch_id": row.source_patch_id, "created_at": row.created_at.isoformat()} for row in rows]


def decide_plan_patch(task_id: str, patch_id: str, decision: str, operation_ids: list[str] | None = None, reason: str | None = None) -> dict | None:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Unsupported plan patch decision")
    with next(get_session()) as session:
        values = {
            "status": decision,
            "decided_at": datetime.now(timezone.utc),
            "approved_operation_ids_json": operation_ids or [],
            "rejection_reason": reason,
        }
        result = session.execute(update(AgentPlanPatch).where(
            AgentPlanPatch.patch_id == patch_id,
            AgentPlanPatch.task_id == task_id,
            AgentPlanPatch.status == "pending",
        ).values(**values))
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        row = session.get(AgentPlanPatch, patch_id)
        assert row is not None
        return _serialize_plan_patch(row)


def begin_plan_patch_apply(task_id: str, patch_id: str, plan: dict) -> dict | None:
    """Atomically consume one approved patch and return the task to rendering."""

    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        patch = session.get(AgentPlanPatch, patch_id)
        latest = _latest_plan_version(session, task_id)
        if (
            task is None or patch is None or patch.task_id != task_id
            or task.status != TaskStatus.COMPLETED or patch.status != "approved"
            or patch.base_version != latest
        ):
            return None
        new_version = latest + 1
        patch.status = "applying"
        patch.resulting_version = new_version
        task.status = TaskStatus.RENDERING
        task.plan_json = plan
        task.error = None
        task.cancel_requested = False
        session.add(PlanVersion(task_id=task_id, version=new_version, plan_json=plan, source="agent_patch", source_patch_id=patch_id))
        session.add(_event(task_id, "plan_patch_applying", "Approved plan patch is rendering", {"patch_id": patch_id, "plan_version": new_version}))
        session.commit()
        return _serialize_plan_patch(patch)


def finish_plan_patch(task_id: str, patch_id: str, succeeded: bool) -> None:
    with next(get_session()) as session:
        patch = session.get(AgentPlanPatch, patch_id)
        if patch is not None and patch.task_id == task_id and patch.status == "applying":
            patch.status = "applied" if succeeded else "failed"
            session.commit()


def get_latest_plan_undo_candidate(task_id: str) -> dict | None:
    initialize_database()
    with next(get_session()) as session:
        patch = session.scalar(select(AgentPlanPatch).where(
            AgentPlanPatch.task_id == task_id,
            AgentPlanPatch.status == "applied",
        ).order_by(AgentPlanPatch.decided_at.desc(), AgentPlanPatch.patch_id.desc()))
        latest = _latest_plan_version(session, task_id)
        if patch is None or patch.resulting_version != latest:
            return None
        previous = session.scalar(select(PlanVersion).where(
            PlanVersion.task_id == task_id, PlanVersion.version == patch.base_version,
        ))
        return None if previous is None else {"patch_id": patch.patch_id, "plan": previous.plan_json}


def begin_latest_plan_undo(task_id: str, validated_plan: dict) -> dict | None:
    """Restore the version preceding the most recently applied, non-undone patch."""

    with next(get_session()) as session:
        task = session.get(VideoTask, task_id)
        patch = session.scalar(select(AgentPlanPatch).where(
            AgentPlanPatch.task_id == task_id,
            AgentPlanPatch.status == "applied",
        ).order_by(AgentPlanPatch.decided_at.desc(), AgentPlanPatch.patch_id.desc()))
        latest = _latest_plan_version(session, task_id)
        if task is None or task.status != TaskStatus.COMPLETED or patch is None or patch.resulting_version != latest:
            return None
        previous = session.scalar(select(PlanVersion).where(
            PlanVersion.task_id == task_id,
            PlanVersion.version == patch.base_version,
        ))
        if previous is None or previous.plan_json != validated_plan:
            return None
        restored_version = latest + 1
        restored_plan = previous.plan_json
        patch.status = "undone"
        task.status = TaskStatus.RENDERING
        task.plan_json = restored_plan
        task.error = None
        session.add(PlanVersion(task_id=task_id, version=restored_version, plan_json=restored_plan, source="undo", source_patch_id=patch.patch_id))
        session.add(_event(task_id, "plan_patch_undone", "Latest applied plan patch was undone", {"patch_id": patch.patch_id, "plan_version": restored_version}))
        session.commit()
        return {"patch_id": patch.patch_id, "plan": restored_plan, "plan_version": restored_version}
