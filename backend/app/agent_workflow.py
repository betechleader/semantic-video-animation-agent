"""Recoverable, task-local state graph for the Agent workflow mode.

The first Agent implementation intentionally stays small and explicit.  It uses
the existing processing services as graph nodes and persists the state after
every successful node in a dedicated SQLite database.  A task ID is also the
graph thread ID, so a process restart can reconstruct a run without replaying
nodes that have a completed checkpoint.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .database import (
    append_task_event,
    get_task,
    is_cancellation_requested,
    list_recoverable_agent_tasks,
    transition_task,
)
from .metrics import TaskMetrics, initialize_initial_metrics
from .models import TaskStatus
from .processing import (
    ProcessingCancelled,
    render_and_composite_video,
    verify_and_write_output_quality,
)
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .workflow_services import (
    build_animation_plan,
    correct_asr_transcript,
    extract_audio,
    transcribe_audio,
    validate_plan,
)

CHECKPOINT_FILENAME = "agent_checkpoints.sqlite3"
CHECKPOINT_SCHEMA_VERSION = 1
AGENT_NODES = (
    "upload_probe",
    "audio_asr",
    "correction",
    "planning",
    "validation",
    "render",
    "quality",
    "complete",
)


class AgentWorkflowError(RuntimeError):
    """Raised when a persisted Agent run cannot safely continue."""


class AgentCheckpointConflict(AgentWorkflowError):
    """Raised when another writer advanced the same checkpoint."""


@dataclass(frozen=True)
class AgentWorkflowServices:
    """Injectable node services; tests can replace every expensive operation."""

    extract_audio: Callable[[Path, VideoMetadata], Path] = extract_audio
    transcribe_audio: Callable[[Path, str], Transcript] = transcribe_audio
    correct_asr_transcript: Callable[[Transcript], Transcript] = correct_asr_transcript
    build_animation_plan: Callable[[Transcript, str, str | None], AnimationPlan] = build_animation_plan
    validate_plan: Callable[[AnimationPlan, Transcript], AnimationPlan] = validate_plan
    render_and_composite_video: Callable[
        [Path, VideoMetadata, Transcript, AnimationPlan, str | None, Any | None],
        tuple[dict, dict],
    ] = render_and_composite_video
    verify_and_write_output_quality: Callable[
        [Path, VideoMetadata, Any | None], dict
    ] = verify_and_write_output_quality


DEFAULT_AGENT_SERVICES = AgentWorkflowServices()


class AgentCheckpointStore:
    """Atomic JSON checkpoints backed by the standard-library SQLite driver."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialization_lock = threading.Lock()
        self._initialized = False

    @classmethod
    def for_storage_root(cls, storage_root: Path) -> "AgentCheckpointStore":
        return cls(storage_root.resolve() / CHECKPOINT_FILENAME)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._initialization_lock:
            if self._initialized:
                return
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = FULL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_checkpoints (
                        task_id TEXT PRIMARY KEY,
                        checkpoint_version INTEGER NOT NULL,
                        next_node TEXT,
                        run_status TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
            self._initialized = True

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict:
        try:
            state = json.loads(row["state_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise AgentWorkflowError("Agent checkpoint contains invalid JSON") from exc
        if not isinstance(state, dict):
            raise AgentWorkflowError("Agent checkpoint state must be a JSON object")
        return {
            "task_id": row["task_id"],
            "checkpoint_version": int(row["checkpoint_version"]),
            "next_node": row["next_node"],
            "run_status": row["run_status"],
            "state": state,
            "updated_at": row["updated_at"],
        }

    def load(self, task_id: str) -> dict | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_checkpoints WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return None if row is None else self._decode(row)

    def create(self, task_id: str, state: dict, next_node: str = AGENT_NODES[0]) -> dict:
        """Create the initial checkpoint, or return the already persisted one."""

        self.initialize()
        encoded = _encode_state(state)
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO agent_checkpoints
                    (task_id, checkpoint_version, next_node, run_status, state_json, updated_at)
                VALUES (?, 1, ?, 'ready', ?, ?)
                """,
                (task_id, next_node, encoded, now),
            )
            row = connection.execute(
                "SELECT * FROM agent_checkpoints WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._decode(row)

    def save(
        self,
        task_id: str,
        state: dict,
        *,
        next_node: str | None,
        run_status: str,
        expected_version: int,
    ) -> dict:
        """Compare-and-swap the full JSON state in one SQLite transaction."""

        if next_node is not None and next_node not in AGENT_NODES:
            raise ValueError(f"Unknown Agent node: {next_node}")
        encoded = _encode_state(state)
        now = _utc_now()
        self.initialize()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE agent_checkpoints
                SET checkpoint_version = checkpoint_version + 1,
                    next_node = ?, run_status = ?, state_json = ?, updated_at = ?
                WHERE task_id = ? AND checkpoint_version = ?
                """,
                (next_node, run_status, encoded, now, task_id, expected_version),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise AgentCheckpointConflict("Agent checkpoint was advanced by another runner")
            row = connection.execute(
                "SELECT * FROM agent_checkpoints WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            connection.commit()
        assert row is not None
        return self._decode(row)


InterruptAfter = str | Collection[str] | Callable[[str, dict], bool] | None


@dataclass(frozen=True)
class _RunContext:
    task_id: str
    task_dir: Path
    metadata: VideoMetadata
    trace_id: str
    processing_profile: str
    media_provider: str | None
    services: AgentWorkflowServices
    metrics: TaskMetrics
    attempt: int


_active_lock = threading.Lock()
_active_threads: dict[str, threading.Thread] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_state(state: dict) -> str:
    try:
        return json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise AgentWorkflowError("Agent state is not JSON serializable") from exc


def _resolve_task_directory(storage_root: Path, task_id: str) -> Path:
    """Resolve a task's immediate child directory without accepting traversal."""

    root = storage_root.resolve()
    candidate = (root / task_id).resolve()
    if candidate.parent != root or candidate.name != task_id:
        raise AgentWorkflowError("Agent task directory must be an immediate child of storage")
    return candidate


def _new_state(context: _RunContext) -> dict:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "thread_id": context.task_id,
        "metadata": context.metadata.model_dump(),
        "trace_id": context.trace_id,
        "processing_profile": context.processing_profile,
        "media_provider": context.media_provider,
        "completed_nodes": [],
        "node_versions": {},
        "transcript": None,
        "plan": None,
        "quality": None,
    }


def _validated_state(checkpoint: dict, task_id: str) -> dict:
    state = checkpoint["state"]
    if state.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise AgentWorkflowError("Unsupported Agent checkpoint schema version")
    if state.get("thread_id") != task_id:
        raise AgentWorkflowError("Agent checkpoint thread ID does not match task ID")
    completed = state.get("completed_nodes")
    if not isinstance(completed, list) or any(node not in AGENT_NODES for node in completed):
        raise AgentWorkflowError("Agent checkpoint has invalid completed nodes")
    return state


def _node_event(
    context: _RunContext,
    node: str,
    status: str,
    checkpoint_version: int,
    *,
    error_category: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "thread_id": context.task_id,
        "node": node,
        "status": status,
        "checkpoint_version": checkpoint_version,
    }
    if error_category is not None:
        payload["error_category"] = error_category
    append_task_event(
        context.task_id,
        "agent_node",
        f"Agent node {node} {status}",
        payload,
        dedupe_key=f"agent:{node}:{status}",
    )


def _resumed_event(context: _RunContext, checkpoint: dict) -> None:
    node = checkpoint["next_node"]
    append_task_event(
        context.task_id,
        "agent_node",
        f"Agent workflow resumed at {node}",
        {
            "thread_id": context.task_id,
            "node": node,
            "status": "resumed",
            "checkpoint_version": checkpoint["checkpoint_version"],
        },
        dedupe_key=f"agent:resume:{checkpoint['checkpoint_version']}:{node}",
    )


def _reconcile_completed_events(context: _RunContext, state: dict) -> None:
    versions = state.get("node_versions", {})
    for node in state["completed_nodes"]:
        _node_event(context, node, "completed", int(versions.get(node, 0)))


def _transition(context: _RunContext, status: TaskStatus, message: str, **values: Any) -> None:
    task = get_task(context.task_id)
    if task is None:
        raise AgentWorkflowError("Agent task does not exist")
    if task["status"] == status.value:
        return
    if not transition_task(context.task_id, status, message, **values):
        current = get_task(context.task_id)
        if current and current["status"] == TaskStatus.CANCELLED.value:
            raise ProcessingCancelled("Agent task was cancelled")
        raise AgentWorkflowError(f"Agent task cannot transition to {status.value}")


def _run_node(node: str, context: _RunContext, state: dict) -> dict:
    transcript = lambda: Transcript.model_validate(state["transcript"])
    plan = lambda: AnimationPlan.model_validate(state["plan"])

    if node == "upload_probe":
        source = context.task_dir / "source.mp4"
        if not source.is_file() or source.stat().st_size <= 0:
            raise AgentWorkflowError("Uploaded source video is missing")
        # Re-validation makes the persisted upload/probe result an explicit graph input.
        VideoMetadata.model_validate(state["metadata"])
        return state
    if node == "audio_asr":
        _transition(context, TaskStatus.PROCESSING, "Agent is extracting audio and transcribing speech")
        audio_path = context.metrics.record_stage(
            context.attempt,
            "audio_extraction",
            lambda: context.services.extract_audio(context.task_dir, context.metadata),
        )
        recognized = context.metrics.record_stage(
            context.attempt,
            "asr",
            lambda: context.services.transcribe_audio(audio_path, context.processing_profile),
        )
        return {**state, "transcript": Transcript.model_validate(recognized).model_dump()}
    if node == "correction":
        corrected = context.metrics.record_stage(
            context.attempt,
            "asr_correction",
            lambda: context.services.correct_asr_transcript(transcript()),
        )
        return {**state, "transcript": Transcript.model_validate(corrected).model_dump()}
    if node == "planning":
        planned = context.metrics.record_stage(
            context.attempt,
            "planning",
            lambda: context.services.build_animation_plan(
                transcript(),
                context.processing_profile,
                context.media_provider,
            ),
        )
        return {**state, "plan": AnimationPlan.model_validate(planned).model_dump()}
    if node == "validation":
        validated = context.services.validate_plan(plan(), transcript())
        return {**state, "plan": AnimationPlan.model_validate(validated).model_dump()}
    if node == "render":
        _transition(context, TaskStatus.RENDERING, "Agent is rendering animation and compositing video")
        transcript_data, plan_data = context.services.render_and_composite_video(
            context.task_dir,
            context.metadata,
            transcript(),
            plan(),
            context.task_id,
            lambda stage, action: context.metrics.record_stage(context.attempt, stage, action),
        )
        return {
            **state,
            "transcript": Transcript.model_validate(transcript_data).model_dump(),
            "plan": AnimationPlan.model_validate(plan_data).model_dump(),
        }
    if node == "quality":
        quality = context.services.verify_and_write_output_quality(
            context.task_dir,
            context.metadata,
            lambda stage, action: context.metrics.record_stage(context.attempt, stage, action),
        )
        if not isinstance(quality, dict):
            raise AgentWorkflowError("Quality node output must be a JSON object")
        return {**state, "quality": quality}
    if node == "complete":
        # Persisting the complete-node checkpoint and event must happen before
        # the task becomes terminal, otherwise SSE readers can close before
        # observing the real graph completion event.
        transcript()
        plan()
        return state
    raise AgentWorkflowError(f"Unknown Agent node: {node}")


def _should_interrupt(interrupt_after: InterruptAfter, node: str, state: dict) -> bool:
    if interrupt_after is None:
        return False
    if isinstance(interrupt_after, str):
        return node == interrupt_after
    if callable(interrupt_after):
        return bool(interrupt_after(node, state))
    return node in interrupt_after


def _reconcile_terminal_checkpoint(
    context: _RunContext,
    checkpoint: dict,
    *,
    error: str | None = None,
) -> None:
    """Finish the database/metrics side of an already durable terminal checkpoint."""

    state = checkpoint["state"]
    run_status = checkpoint["run_status"]
    task = get_task(context.task_id)
    if task is None:
        raise AgentWorkflowError("Agent task does not exist")
    if run_status == "completed":
        if task["status"] != TaskStatus.COMPLETED.value:
            _transition(
                context,
                TaskStatus.COMPLETED,
                "Agent workflow completed",
                transcript=Transcript.model_validate(state["transcript"]).model_dump(),
                plan=AnimationPlan.model_validate(state["plan"]).model_dump(),
            )
        context.metrics.finalize(
            context.attempt,
            TaskStatus.COMPLETED.value,
            output_quality=state.get("quality"),
        )
    elif run_status == "cancelled":
        node = checkpoint.get("next_node")
        if node in AGENT_NODES:
            _node_event(
                context,
                node,
                "failed",
                checkpoint["checkpoint_version"],
                error_category="cancelled",
            )
        if task["status"] != TaskStatus.CANCELLED.value:
            _transition(context, TaskStatus.CANCELLED, "Agent workflow cancelled")
        context.metrics.finalize(
            context.attempt,
            TaskStatus.CANCELLED.value,
            failure_category="cancelled",
            output_quality=state.get("quality"),
        )
    elif run_status == "failed":
        failure = state.get("failure") if isinstance(state.get("failure"), dict) else {}
        node = failure.get("node") or checkpoint.get("next_node")
        error_category = failure.get("error_category") or "AgentWorkflowError"
        if node in AGENT_NODES:
            _node_event(
                context,
                node,
                "failed",
                checkpoint["checkpoint_version"],
                error_category=str(error_category),
            )
        if task["status"] != TaskStatus.FAILED.value:
            _transition(
                context,
                TaskStatus.FAILED,
                "Agent workflow failed",
                error=error or "Agent workflow failed before task status was persisted",
            )
        context.metrics.finalize(
            context.attempt,
            TaskStatus.FAILED.value,
            failure_category=str(node or "workflow"),
            output_quality=state.get("quality"),
        )


def _record_unhandled_runner_failure(task_id: str, exc: Exception) -> None:
    """Converge corrupt/unreadable persisted work without exposing exception text."""

    task = get_task(task_id)
    if task is None or task["status"] in {
        TaskStatus.COMPLETED.value,
        TaskStatus.FAILED.value,
        TaskStatus.CANCELLED.value,
    }:
        return
    error_category = exc.__class__.__name__
    append_task_event(
        task_id,
        "agent_recovery_failed",
        "Agent workflow could not be recovered",
        {"thread_id": task_id, "error_category": error_category},
        dedupe_key=f"agent:recovery_failed:{error_category}",
    )
    transition_task(
        task_id,
        TaskStatus.FAILED,
        "Agent workflow recovery failed",
        error="Agent workflow persisted state could not be recovered",
    )


def run_agent_task(
    task_id: str,
    task_dir: Path,
    metadata: VideoMetadata,
    trace_id: str,
    processing_profile: str = "configured",
    media_provider: str | None = None,
    *,
    services: AgentWorkflowServices | None = None,
    checkpoint_store: AgentCheckpointStore | None = None,
    interrupt_after: InterruptAfter = None,
) -> dict:
    """Run or resume one task synchronously and return its latest checkpoint."""

    requested_task_dir = task_dir.resolve()
    storage_root = (
        checkpoint_store.path.parent.resolve()
        if checkpoint_store is not None
        else requested_task_dir.parent
    )
    safe_task_dir = _resolve_task_directory(storage_root, task_id)
    if safe_task_dir != requested_task_dir:
        raise AgentWorkflowError("Agent task directory does not match its task ID")
    metrics = TaskMetrics(safe_task_dir, task_id)
    try:
        attempt = metrics.current_or_start_attempt("initial")
    except RuntimeError:
        metrics = initialize_initial_metrics(safe_task_dir, task_id, trace_id, 0)
        attempt = 1
    context = _RunContext(
        task_id=task_id,
        task_dir=safe_task_dir,
        metadata=VideoMetadata.model_validate(metadata),
        trace_id=trace_id,
        processing_profile=processing_profile,
        media_provider=media_provider,
        services=services or DEFAULT_AGENT_SERVICES,
        metrics=metrics,
        attempt=attempt,
    )
    store = checkpoint_store or AgentCheckpointStore.for_storage_root(storage_root)
    existing = store.load(task_id)
    checkpoint = store.create(task_id, _new_state(context)) if existing is None else existing
    state = _validated_state(checkpoint, task_id)
    _reconcile_completed_events(context, state)

    if checkpoint["run_status"] in {"completed", "cancelled", "failed"}:
        _reconcile_terminal_checkpoint(context, checkpoint)
        return checkpoint
    if existing is not None:
        _resumed_event(context, checkpoint)

    while checkpoint["next_node"] is not None:
        node = checkpoint["next_node"]
        if node not in AGENT_NODES:
            raise AgentWorkflowError(f"Unknown Agent node: {node}")
        if is_cancellation_requested(task_id):
            checkpoint = store.save(
                task_id,
                state,
                next_node=node,
                run_status="cancelled",
                expected_version=checkpoint["checkpoint_version"],
            )
            _node_event(context, node, "failed", checkpoint["checkpoint_version"], error_category="cancelled")
            _reconcile_terminal_checkpoint(context, checkpoint)
            return checkpoint

        _node_event(context, node, "started", checkpoint["checkpoint_version"])
        try:
            updated = _run_node(node, context, state)
            completed_nodes = list(updated["completed_nodes"])
            if node not in completed_nodes:
                completed_nodes.append(node)
            updated = {**updated, "completed_nodes": completed_nodes}
            next_index = AGENT_NODES.index(node) + 1
            next_node = AGENT_NODES[next_index] if next_index < len(AGENT_NODES) else None
            interrupted = _should_interrupt(interrupt_after, node, updated) and next_node is not None
            # The version written by this save is recorded as the node's completion version.
            node_version = checkpoint["checkpoint_version"] + 1
            updated["node_versions"] = {**updated.get("node_versions", {}), node: node_version}
            checkpoint = store.save(
                task_id,
                updated,
                next_node=next_node,
                run_status="interrupted" if interrupted else "completed" if next_node is None else "running",
                expected_version=checkpoint["checkpoint_version"],
            )
            state = updated
            _node_event(context, node, "completed", checkpoint["checkpoint_version"])
            if interrupted:
                return checkpoint
        except ProcessingCancelled:
            checkpoint = store.save(
                task_id,
                state,
                next_node=node,
                run_status="cancelled",
                expected_version=checkpoint["checkpoint_version"],
            )
            _node_event(context, node, "failed", checkpoint["checkpoint_version"], error_category="cancelled")
            _reconcile_terminal_checkpoint(context, checkpoint)
            return checkpoint
        except Exception as exc:
            failed_state = {
                **state,
                "failure": {
                    "node": node,
                    "error_category": exc.__class__.__name__,
                },
            }
            checkpoint = store.save(
                task_id,
                failed_state,
                next_node=node,
                run_status="failed",
                expected_version=checkpoint["checkpoint_version"],
            )
            _reconcile_terminal_checkpoint(context, checkpoint, error=str(exc))
            return checkpoint
        if node == "complete":
            # Keep terminal reconciliation outside the node failure handler:
            # the graph checkpoint and completion event are already durable,
            # and a later startup can safely finish this small DB side effect.
            _reconcile_terminal_checkpoint(context, checkpoint)
            return checkpoint
    return checkpoint


def get_active_agent_thread(task_id: str) -> threading.Thread | None:
    with _active_lock:
        thread = _active_threads.get(task_id)
        return thread if thread is not None and thread.is_alive() else None


def is_agent_task_active(task_id: str) -> bool:
    return get_active_agent_thread(task_id) is not None


def start_agent_task(
    task_id: str,
    task_dir: Path,
    metadata: VideoMetadata,
    trace_id: str,
    processing_profile: str = "configured",
    media_provider: str | None = None,
    *,
    services: AgentWorkflowServices | None = None,
    checkpoint_store: AgentCheckpointStore | None = None,
    interrupt_after: InterruptAfter = None,
) -> threading.Thread:
    """Start one daemon runner, returning the existing runner on duplicate calls."""

    with _active_lock:
        active = _active_threads.get(task_id)
        if active is not None and active.is_alive():
            return active

        def target() -> None:
            try:
                run_agent_task(
                    task_id,
                    task_dir,
                    metadata,
                    trace_id,
                    processing_profile,
                    media_provider,
                    services=services,
                    checkpoint_store=checkpoint_store,
                    interrupt_after=interrupt_after,
                )
            except AgentCheckpointConflict:
                # Another process advanced the same task. P1 is single-process,
                # but leaving the public task non-terminal lets the winning
                # runner (or the next startup) reconcile it safely.
                append_task_event(
                    task_id,
                    "agent_checkpoint_conflict",
                    "Another Agent runner advanced the checkpoint",
                    {"thread_id": task_id, "error_category": "AgentCheckpointConflict"},
                    dedupe_key="agent:checkpoint_conflict",
                )
            except Exception as exc:
                _record_unhandled_runner_failure(task_id, exc)
            finally:
                with _active_lock:
                    if _active_threads.get(task_id) is threading.current_thread():
                        _active_threads.pop(task_id, None)

        thread = threading.Thread(target=target, daemon=True, name=f"agent-task-{task_id}")
        _active_threads[task_id] = thread
        thread.start()
        return thread


def resume_agent_task(
    task_id: str,
    storage_root: Path | None = None,
    *,
    services: AgentWorkflowServices | None = None,
    checkpoint_store: AgentCheckpointStore | None = None,
    interrupt_after: InterruptAfter = None,
) -> threading.Thread | None:
    """Resume a persisted non-terminal Agent task from its next node."""

    task = get_task(task_id)
    if task is None or task.get("workflow_mode") != "agent":
        return None
    if task["status"] in {status.value for status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)}:
        return None
    root = (storage_root or config.STORAGE_ROOT).resolve()
    metadata = VideoMetadata.model_validate(task["metadata"])
    return start_agent_task(
        task_id,
        _resolve_task_directory(root, task_id),
        metadata,
        task["trace_id"],
        task.get("processing_profile", "configured"),
        task.get("media_provider"),
        services=services,
        checkpoint_store=checkpoint_store or AgentCheckpointStore.for_storage_root(root),
        interrupt_after=interrupt_after,
    )


def recover_agent_tasks(
    storage_root: Path | None = None,
    *,
    services: AgentWorkflowServices | None = None,
    checkpoint_store: AgentCheckpointStore | None = None,
    interrupt_after: InterruptAfter = None,
) -> list[str]:
    """Start every persisted, non-terminal Agent task during application startup."""

    root = (storage_root or config.STORAGE_ROOT).resolve()
    store = checkpoint_store or AgentCheckpointStore.for_storage_root(root)
    started: list[str] = []
    for task in list_recoverable_agent_tasks():
        try:
            thread = resume_agent_task(
                task["task_id"],
                root,
                services=services,
                checkpoint_store=store,
                interrupt_after=interrupt_after,
            )
        except Exception as exc:
            _record_unhandled_runner_failure(task["task_id"], exc)
            continue
        if thread is not None:
            started.append(task["task_id"])
    return started
