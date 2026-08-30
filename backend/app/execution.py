"""Optional SQLite-backed persistent task execution for the local production profile."""

from __future__ import annotations

import logging
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .config import SETTINGS, STORAGE_ROOT
from .database import (
    append_task_event,
    get_agent_approval,
    get_session,
    get_task,
    get_task_events,
    initialize_database,
    is_cancellation_requested,
    transition_task,
)
from .models import ExecutionJob, TaskStatus, VideoTask, WorkerHeartbeat
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .storage import StorageService

logger = logging.getLogger("semantic_video")
JOB_KINDS = {"standard", "agent", "review"}
ACTIVE_JOB_STATUSES = {"queued", "running"}


def _utcnow() -> datetime:
    # SQLite persists DateTime values without an offset. Keep every queue
    # timestamp as naive UTC so ORM comparisons and database comparisons agree.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_job(job: ExecutionJob) -> dict:
    return {
        "job_id": job.job_id,
        "task_id": job.task_id,
        "kind": job.kind,
        "status": job.status,
        "dedupe_key": job.dedupe_key,
        "payload": job.payload_json,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "lease_owner": job.lease_owner,
        "lease_expires_at": job.lease_expires_at.isoformat()
        if job.lease_expires_at
        else None,
        "last_error_category": job.last_error_category,
    }


def enqueue_job(
    task_id: str,
    kind: str,
    dedupe_key: str,
    *,
    payload: dict | None = None,
    max_attempts: int | None = None,
) -> dict:
    """Persist one idempotent execution request and return the existing row on replay."""

    if kind not in JOB_KINDS:
        raise ValueError("Unsupported execution job kind")
    initialize_database()
    now = _utcnow()
    job = ExecutionJob(
        job_id=str(uuid4()),
        task_id=task_id,
        kind=kind,
        status="queued",
        dedupe_key=dedupe_key,
        payload_json=payload or {},
        attempt_count=0,
        max_attempts=max_attempts or SETTINGS.worker_max_attempts,
        available_at=now,
    )
    with next(get_session()) as session:
        session.add(job)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(
                select(ExecutionJob).where(
                    ExecutionJob.task_id == task_id,
                    ExecutionJob.dedupe_key == dedupe_key,
                )
            )
            if existing is None:
                raise
            return _serialize_job(existing)
    append_task_event(
        task_id,
        "worker_queued",
        "Task queued for persistent execution",
        {"job_id": job.job_id, "kind": kind},
        dedupe_key=f"worker:queued:{job.job_id}",
    )
    return _serialize_job(job)


def enqueue_initial_task(task_id: str, workflow_mode: str) -> dict:
    return enqueue_job(
        task_id,
        "agent" if workflow_mode == "agent" else "standard",
        f"initial:{workflow_mode}",
    )


def enqueue_agent_resume(task_id: str, decision_version: int) -> dict:
    return enqueue_job(task_id, "agent", f"approval:{decision_version}")


def enqueue_review(task_id: str, *, patch_id: str | None = None) -> dict:
    token = patch_id or str(uuid4())
    return enqueue_job(
        task_id, "review", f"review:{token}", payload={"patch_id": patch_id}
    )


def _mark_exhausted_leases(now: datetime) -> list[str]:
    exhausted_tasks: list[str] = []
    with next(get_session()) as session:
        rows = session.scalars(
            select(ExecutionJob).where(
                ExecutionJob.status == "running",
                ExecutionJob.lease_expires_at <= now,
                ExecutionJob.attempt_count >= ExecutionJob.max_attempts,
            )
        ).all()
        for row in rows:
            row.status = "failed"
            row.last_error_category = "lease_expired"
            row.lease_owner = None
            row.lease_expires_at = None
            exhausted_tasks.append(row.task_id)
        session.commit()
    for task_id in exhausted_tasks:
        transition_task(
            task_id,
            TaskStatus.FAILED,
            "Persistent worker retries exhausted",
            error="Persistent worker retries exhausted",
        )
    return exhausted_tasks


def claim_next_job(worker_id: str, lease_seconds: int) -> dict | None:
    """Atomically claim one queued or expired job; concurrent workers get one winner."""

    initialize_database()
    now = _utcnow()
    _mark_exhausted_leases(now)
    runnable = or_(
        and_(ExecutionJob.status == "queued", ExecutionJob.available_at <= now),
        and_(ExecutionJob.status == "running", ExecutionJob.lease_expires_at <= now),
    )
    for _ in range(8):
        with next(get_session()) as session:
            candidate = session.scalar(
                select(ExecutionJob)
                .where(runnable, ExecutionJob.attempt_count < ExecutionJob.max_attempts)
                .order_by(
                    ExecutionJob.available_at,
                    ExecutionJob.created_at,
                    ExecutionJob.job_id,
                )
            )
            if candidate is None:
                return None
            result = session.execute(
                update(ExecutionJob)
                .where(ExecutionJob.job_id == candidate.job_id, runnable)
                .values(
                    status="running",
                    lease_owner=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    heartbeat_at=now,
                    attempt_count=ExecutionJob.attempt_count + 1,
                    last_error_category=None,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 1:
                session.commit()
                session.expire_all()
                claimed = session.get(ExecutionJob, candidate.job_id)
                assert claimed is not None
                data = _serialize_job(claimed)
                append_task_event(
                    claimed.task_id,
                    "worker_claimed",
                    "Persistent worker claimed task",
                    {
                        "job_id": claimed.job_id,
                        "kind": claimed.kind,
                        "attempt": claimed.attempt_count,
                    },
                    dedupe_key=f"worker:claimed:{claimed.job_id}:{claimed.attempt_count}",
                )
                return data
            session.rollback()
    return None


def heartbeat_job(job_id: str, worker_id: str, lease_seconds: int) -> bool:
    now = _utcnow()
    with next(get_session()) as session:
        result = session.execute(
            update(ExecutionJob)
            .where(
                ExecutionJob.job_id == job_id,
                ExecutionJob.status == "running",
                ExecutionJob.lease_owner == worker_id,
            )
            .values(
                heartbeat_at=now,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
            )
        )
        session.commit()
        return result.rowcount == 1


def finish_job(
    job_id: str, worker_id: str, status: str, error_category: str | None = None
) -> bool:
    if status not in {"succeeded", "failed", "cancelled"}:
        raise ValueError("Unsupported terminal job status")
    with next(get_session()) as session:
        result = session.execute(
            update(ExecutionJob)
            .where(
                ExecutionJob.job_id == job_id,
                ExecutionJob.status == "running",
                ExecutionJob.lease_owner == worker_id,
            )
            .values(
                status=status,
                lease_owner=None,
                lease_expires_at=None,
                last_error_category=error_category,
            )
        )
        session.commit()
        return result.rowcount == 1


def retry_job(job_id: str, worker_id: str, error_category: str) -> bool:
    """Release a failed attempt with bounded backoff; the claim counter enforces the limit."""

    with next(get_session()) as session:
        job = session.get(ExecutionJob, job_id)
        if job is None or job.status != "running" or job.lease_owner != worker_id:
            return False
        exhausted = job.attempt_count >= job.max_attempts
        job.status = "failed" if exhausted else "queued"
        job.available_at = _utcnow() + timedelta(
            seconds=min(30, 2 ** max(0, job.attempt_count - 1))
        )
        job.lease_owner = None
        job.lease_expires_at = None
        job.last_error_category = error_category[:96]
        session.commit()
    if exhausted:
        transition_task(
            job.task_id,
            TaskStatus.FAILED,
            "Persistent worker retries exhausted",
            error="Persistent worker retries exhausted",
        )
    return True


def update_worker_heartbeat(worker_id: str, status: str = "running") -> None:
    now = _utcnow()
    with next(get_session()) as session:
        row = session.get(WorkerHeartbeat, worker_id)
        if row is None:
            row = WorkerHeartbeat(
                worker_id=worker_id, status=status, started_at=now, heartbeat_at=now
            )
            session.add(row)
        else:
            row.status = status
            row.heartbeat_at = now
        session.commit()


def active_worker_count(stale_after_seconds: int | None = None) -> int:
    initialize_database()
    stale_after = stale_after_seconds or SETTINGS.worker_lease_seconds
    threshold = _utcnow() - timedelta(seconds=stale_after)
    with next(get_session()) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(WorkerHeartbeat)
                .where(
                    WorkerHeartbeat.status == "running",
                    WorkerHeartbeat.heartbeat_at >= threshold,
                )
            )
            or 0
        )


def execution_metrics() -> dict:
    initialize_database()
    with next(get_session()) as session:
        task_counts = dict(
            session.execute(
                select(VideoTask.status, func.count()).group_by(VideoTask.status)
            ).all()
        )
        job_counts = dict(
            session.execute(
                select(ExecutionJob.status, func.count()).group_by(ExecutionJob.status)
            ).all()
        )
    return {
        "tasks": {
            (key.value if hasattr(key, "value") else str(key)).lower(): value
            for key, value in task_counts.items()
        },
        "jobs": {str(key): value for key, value in job_counts.items()},
        "active_workers": active_worker_count(),
    }


def _has_active_job(task_id: str) -> bool:
    with next(get_session()) as session:
        return bool(
            session.scalar(
                select(ExecutionJob.job_id).where(
                    ExecutionJob.task_id == task_id,
                    ExecutionJob.status.in_(ACTIVE_JOB_STATUSES),
                )
            )
        )


def recover_execution_jobs() -> list[str]:
    """Queue non-terminal tasks that were committed before their dispatch was persisted."""

    initialize_database()
    terminal = (
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
        TaskStatus.REJECTED,
    )
    with next(get_session()) as session:
        task_ids = list(
            session.scalars(
                select(VideoTask.task_id).where(VideoTask.status.not_in(terminal))
            )
        )
    recovered: list[str] = []
    for task_id in task_ids:
        if _has_active_job(task_id):
            continue
        task = get_task(task_id)
        if task is None:
            continue
        if task["status"] == "awaiting_approval":
            approval = get_agent_approval(task_id)
            if not approval or approval["status"] == "pending":
                continue
            enqueue_agent_resume(task_id, int(approval["decision_version"]))
        elif task["workflow_mode"] == "agent":
            enqueue_job(task_id, "agent", "recovery:agent")
        else:
            review_events = [
                event
                for event in get_task_events(task_id)
                if event["type"] == "review_rendering"
            ]
            if task["status"] == "rendering" and review_events:
                enqueue_job(
                    task_id, "review", f"recovery:review:{review_events[-1]['id']}"
                )
            else:
                enqueue_job(task_id, "standard", "recovery:standard")
        recovered.append(task_id)
    return recovered


def execute_job(job: dict, storage_root: Path = STORAGE_ROOT) -> None:
    """Reconstruct authoritative inputs from SQLite/task storage and execute one lease."""

    task = get_task(job["task_id"])
    if task is None:
        raise RuntimeError("execution_task_missing")
    if is_cancellation_requested(job["task_id"]):
        transition_task(
            job["task_id"], TaskStatus.CANCELLED, "Queued task cancellation applied"
        )
        return
    task_dir = StorageService(storage_root).task_directory(job["task_id"])
    metadata = VideoMetadata.model_validate(task["metadata"])
    if job["kind"] == "standard":
        from .workflow import process_task

        process_task(
            job["task_id"],
            task_dir,
            metadata,
            task["trace_id"],
            task["processing_profile"],
            task["media_provider"],
        )
    elif job["kind"] == "agent":
        from .agent_workflow import AgentCheckpointStore, run_agent_task

        run_agent_task(
            job["task_id"],
            task_dir,
            metadata,
            task["trace_id"],
            task["processing_profile"],
            task["media_provider"],
            task.get("director_instruction"),
            checkpoint_store=AgentCheckpointStore.for_storage_root(storage_root),
        )
    else:
        from .workflow import rerender_review

        if task.get("transcript") is None or task.get("plan") is None:
            raise RuntimeError("review_state_missing")
        rerender_review(
            job["task_id"],
            task_dir,
            metadata,
            Transcript.model_validate(task["transcript"]),
            AnimationPlan.model_validate(task["plan"]),
            task["trace_id"],
            job["payload"].get("patch_id"),
        )


class PersistentWorker:
    def __init__(
        self, worker_id: str | None = None, *, storage_root: Path = STORAGE_ROOT
    ) -> None:
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid4()}"
        self.storage_root = storage_root
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> bool:
        update_worker_heartbeat(self.worker_id)
        job = claim_next_job(self.worker_id, SETTINGS.worker_lease_seconds)
        if job is None:
            return False
        heartbeat_stop = threading.Event()

        def renew() -> None:
            while not heartbeat_stop.wait(SETTINGS.worker_heartbeat_seconds):
                update_worker_heartbeat(self.worker_id)
                if not heartbeat_job(
                    job["job_id"], self.worker_id, SETTINGS.worker_lease_seconds
                ):
                    return

        heartbeat = threading.Thread(
            target=renew, daemon=True, name=f"job-heartbeat-{job['job_id']}"
        )
        heartbeat.start()
        try:
            execute_job(job, self.storage_root)
            task = get_task(job["task_id"])
            if task is None or task["status"] == "failed":
                job_status = "failed"
            elif task["status"] == "cancelled":
                job_status = "cancelled"
            elif task["status"] in {"completed", "awaiting_approval", "rejected"}:
                job_status = "succeeded"
            else:
                raise RuntimeError("execution_finished_nonterminal")
            finish_job(job["job_id"], self.worker_id, job_status)
        except Exception as exc:
            category = exc.__class__.__name__[:96]
            logger.exception(
                "persistent_worker_attempt_failed",
                extra={"task_id": job["task_id"], "event_type": category},
            )
            retry_job(job["job_id"], self.worker_id, category)
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=SETTINGS.worker_heartbeat_seconds + 1)
            update_worker_heartbeat(self.worker_id)
        return True

    def run_forever(self) -> None:
        initialize_database()
        recover_execution_jobs()
        update_worker_heartbeat(self.worker_id)
        try:
            while not self._stop.is_set():
                if not self.run_once():
                    self._stop.wait(SETTINGS.worker_poll_seconds)
        finally:
            update_worker_heartbeat(self.worker_id, "stopped")
