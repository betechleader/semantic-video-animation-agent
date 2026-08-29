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
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .database import (
    append_task_event,
    create_pending_approval,
    get_agent_approval,
    get_task,
    is_cancellation_requested,
    list_recoverable_agent_tasks,
    transition_task,
)
from .metrics import TaskMetrics, initialize_initial_metrics
from .models import TaskStatus
from .agent_tools import (
    DIRECTOR_INSTRUCTION_MAX_LENGTH,
    MAX_PLAN_REPAIR_ATTEMPTS,
    PlanViolation,
    PlanningToolInput,
    PlanningToolOutput,
    ValidationToolInput,
    invoke_planning_tool,
    invoke_validation_tool,
)
from .agent_trace import AgentTrace
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
    plan_agent_candidate,
    transcribe_audio,
    validate_plan,
)

CHECKPOINT_FILENAME = "agent_checkpoints.sqlite3"
CHECKPOINT_SCHEMA_VERSION = 2
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


class PlanRepairExhausted(AgentWorkflowError):
    """Raised after the bounded repair budget cannot produce a valid plan."""

    def __init__(self, attempts: int, violation_codes: list[str]) -> None:
        self.attempts = attempts
        self.violation_codes = violation_codes
        super().__init__(
            f"Agent plan repair exhausted after {attempts} retries; "
            f"violation codes: {', '.join(violation_codes)}"
        )


class AgentPlannerCallError(AgentWorkflowError):
    """Raised when a planner call fails rather than returning an invalid plan."""


@dataclass(frozen=True)
class AgentWorkflowServices:
    """Injectable node services; tests can replace every expensive operation."""

    extract_audio: Callable[[Path, VideoMetadata], Path] = extract_audio
    transcribe_audio: Callable[[Path, str], Transcript] = transcribe_audio
    correct_asr_transcript: Callable[[Transcript], Transcript] = correct_asr_transcript
    build_animation_plan: Callable[[Transcript, str, str | None], AnimationPlan] = build_animation_plan
    plan_agent_candidate: Callable[
        [PlanningToolInput, str, str | None], PlanningToolOutput
    ] | None = None
    validate_plan: Callable[[AnimationPlan, Transcript], AnimationPlan] = validate_plan
    render_and_composite_video: Callable[
        [Path, VideoMetadata, Transcript, AnimationPlan, str | None, Any | None],
        tuple[dict, dict],
    ] = render_and_composite_video
    verify_and_write_output_quality: Callable[
        [Path, VideoMetadata, Any | None], dict
    ] = verify_and_write_output_quality


DEFAULT_AGENT_SERVICES = AgentWorkflowServices(plan_agent_candidate=plan_agent_candidate)


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
    agent_trace: AgentTrace


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


def _new_state(context: _RunContext, director_instruction: str | None) -> dict:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "thread_id": context.task_id,
        "metadata": context.metadata.model_dump(),
        "trace_id": context.trace_id,
        "processing_profile": context.processing_profile,
        "media_provider": context.media_provider,
        "director_instruction": director_instruction,
        "completed_nodes": [],
        "node_versions": {},
        "transcript": None,
        "plan_candidate": None,
        "plan": None,
        "repair_attempts": 0,
        "validation_violations": [],
        "approval_reasons": [],
        "quality": None,
    }


def _validated_state(checkpoint: dict, task_id: str) -> dict:
    state = checkpoint["state"]
    schema_version = state.get("schema_version")
    if schema_version not in {1, CHECKPOINT_SCHEMA_VERSION}:
        raise AgentWorkflowError("Unsupported Agent checkpoint schema version")
    if state.get("thread_id") != task_id:
        raise AgentWorkflowError("Agent checkpoint thread ID does not match task ID")
    completed = state.get("completed_nodes")
    if not isinstance(completed, list) or any(node not in AGENT_NODES for node in completed):
        raise AgentWorkflowError("Agent checkpoint has invalid completed nodes")
    if schema_version == 1:
        # P1 checkpoints remain resumable. A previously schema-valid plan is
        # also a valid candidate for the new explicit validation boundary.
        state = {
            **state,
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "director_instruction": None,
            "plan_candidate": state.get("plan"),
            "repair_attempts": 0,
            "validation_violations": [],
        }
    instruction = state.get("director_instruction")
    if instruction is not None and (
        not isinstance(instruction, str)
        or len(instruction) > DIRECTOR_INSTRUCTION_MAX_LENGTH
    ):
        raise AgentWorkflowError("Agent checkpoint has an invalid director instruction")
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


def _planning_tool_call(
    context: _RunContext,
    state: dict,
    *,
    repair_attempt: int,
    violations: list[PlanViolation],
) -> PlanningToolOutput:
    tool_input = PlanningToolInput(
        transcript=Transcript.model_validate(state["transcript"]),
        director_instruction=state.get("director_instruction"),
        repair_attempt=repair_attempt,
        violations=violations,
    )
    started_at = time.perf_counter()
    if context.services.plan_agent_candidate is not None:
        output = context.services.plan_agent_candidate(
            tool_input,
            context.processing_profile,
            context.media_provider,
        )
        output = PlanningToolOutput.model_validate(output)
    else:
        # Compatibility adapter for P1 service bundles and deterministic tests.
        output = invoke_planning_tool(
            tool_input,
            lambda value: context.services.build_animation_plan(
                value.transcript,
                context.processing_profile,
                context.media_provider,
            ),
            planner_id="injected",
            model_id=None,
        )
    duration_ms = round((time.perf_counter() - started_at) * 1_000)
    planner = {
        "planner_id": output.planner_id,
        "model_id": output.model_id,
        "prompt_version": output.prompt_version,
        "schema_version": output.schema_version,
    }
    input_summary = {
        "transcript_segment_count": len(tool_input.transcript.segments),
        "transcript_character_count": len(tool_input.transcript.full_text),
        "director_instruction_present": bool(tool_input.director_instruction),
        "director_instruction_length": len(tool_input.director_instruction or ""),
        "repair_attempt": repair_attempt,
        "violation_count": len(violations),
    }
    output_summary = {
        "candidate_present": output.candidate is not None,
        "animation_count": len(output.candidate.get("animations", []))
        if isinstance(output.candidate, dict) and isinstance(output.candidate.get("animations"), list)
        else None,
        "violation_count": len(output.violations),
    }
    if output.planner_id == "local_llm":
        context.agent_trace.append(
            "model_call",
            node="planning",
            tool_name="planner_model",
            status="completed" if output.candidate is not None else "failed",
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            error_category="planner_error" if output.violations else None,
            planner=planner,
            retry_count=repair_attempt,
        )
    context.agent_trace.append(
        "tool_call",
        node="planning",
        tool_name="plan_animation",
        status="completed" if output.candidate is not None else "failed",
        duration_ms=duration_ms,
        input_summary=input_summary,
        output_summary=output_summary,
        error_category="planner_error" if output.violations else None,
        violations=[item.model_dump() for item in output.violations],
        planner=planner,
        retry_count=repair_attempt,
    )
    return output


def _validation_tool_call(
    context: _RunContext,
    state: dict,
    candidate: dict[str, Any] | None,
    *,
    repair_attempt: int,
) -> tuple[AnimationPlan | None, list[PlanViolation]]:
    started_at = time.perf_counter()
    result = invoke_validation_tool(
        ValidationToolInput(
            transcript=Transcript.model_validate(state["transcript"]),
            candidate=candidate,
        ),
        context.services.validate_plan,
    )
    duration_ms = round((time.perf_counter() - started_at) * 1_000)
    violations = [item.model_dump() for item in result.violations]
    context.agent_trace.append(
        "tool_call",
        node="validation",
        tool_name="validate_animation_plan",
        status="completed" if result.valid else "failed",
        duration_ms=duration_ms,
        input_summary={
            "candidate_present": candidate is not None,
            "repair_attempt": repair_attempt,
        },
        output_summary={
            "valid": result.valid,
            "violation_count": len(result.violations),
        },
        error_category="plan_validation_failed" if not result.valid else None,
        violations=violations,
        retry_count=repair_attempt,
    )
    if not result.valid:
        context.agent_trace.append(
            "validation_error",
            node="validation",
            status="failed",
            error_category="plan_validation_failed",
            violations=violations,
            retry_count=repair_attempt,
        )
    return result.plan, result.violations


def _merge_violations(*groups: list[PlanViolation]) -> list[PlanViolation]:
    merged: list[PlanViolation] = []
    seen: set[tuple[str, tuple[str | int, ...], str]] = set()
    for group in groups:
        for item in group:
            key = (item.code, tuple(item.path), item.message)
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged[:50]


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
            lambda: _planning_tool_call(context, state, repair_attempt=0, violations=[]),
        )
        if planned.candidate is None:
            codes = sorted({item.code for item in planned.violations})
            raise AgentPlannerCallError(
                f"Agent planner failed before returning a candidate; violation codes: {', '.join(codes)}"
            )
        return {
            **state,
            "plan_candidate": planned.candidate,
            "validation_violations": [item.model_dump() for item in planned.violations],
        }
    if node == "validation":
        candidate = state.get("plan_candidate") or state.get("plan")
        repair_attempt = int(state.get("repair_attempts", 0))
        validated, violations = _validation_tool_call(
            context,
            state,
            candidate,
            repair_attempt=repair_attempt,
        )
        recorded_violations = [
            PlanViolation.model_validate(item)
            for item in state.get("validation_violations", [])
        ]
        violations = _merge_violations(recorded_violations, violations)
        while validated is None and repair_attempt < MAX_PLAN_REPAIR_ATTEMPTS:
            repair_attempt += 1
            context.agent_trace.append(
                "retry",
                node="planning",
                status="started",
                input_summary={"repair_attempt": repair_attempt, "violation_count": len(violations)},
                retry_count=repair_attempt,
            )
            planned = _planning_tool_call(
                context,
                state,
                repair_attempt=repair_attempt,
                violations=violations,
            )
            if planned.candidate is None and planned.violations:
                codes = sorted({item.code for item in planned.violations})
                raise AgentPlannerCallError(
                    f"Agent planner failed during repair attempt {repair_attempt}; "
                    f"violation codes: {', '.join(codes)}"
                )
            candidate = planned.candidate
            planner_violations = planned.violations
            validated, violations = _validation_tool_call(
                context,
                state,
                candidate,
                repair_attempt=repair_attempt,
            )
            violations = _merge_violations(planner_violations, violations)
        if validated is None:
            codes = sorted({item.code for item in violations})
            return {
                **state,
                "plan_candidate": candidate,
                "plan": None,
                "repair_attempts": repair_attempt,
                "validation_violations": [item.model_dump() for item in violations],
                "approval_reasons": [{
                    "code": "plan_repair_exhausted",
                    "message": "Automatic plan repair was exhausted; a validated edit is required",
                    "details": {"retry_count": repair_attempt, "violation_codes": codes[:20]},
                }],
            }
        validated_plan = AnimationPlan.model_validate(validated)
        return {
            **state,
            "plan_candidate": candidate,
            "plan": validated_plan.model_dump(),
            "repair_attempts": repair_attempt,
            "validation_violations": [],
            "approval_reasons": _approval_reasons(context, validated_plan),
        }
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


def _approval_reasons(context: _RunContext, plan: AnimationPlan) -> list[dict]:
    task = get_task(context.task_id) or {}
    policy = task.get("approval_policy") or "never"
    if policy == "always":
        return [{
            "code": "policy_always",
            "message": "The configured approval policy requires review before rendering",
            "details": {},
        }]
    if policy != "on_risk":
        return []
    external_visual_count = sum(
        1
        for animation in plan.animations
        if animation.type == "media_visual"
        and animation.parameters.enabled
        and plan.media_provider in {"knowledge", "wikimedia_commons", "pexels", "manual"}
    )
    if not external_visual_count:
        return []
    return [
        {
            "code": "media_relevance_unverified",
            "message": "External media relevance has not yet been confirmed by a reviewer",
            "details": {"visual_count": external_visual_count},
        },
        {
            "code": "external_media_rights_review",
            "message": "External media source and rights information requires human review",
            "details": {"visual_count": external_visual_count},
        },
    ]


def _persist_approval_pause(context: _RunContext, state: dict) -> None:
    reasons = state.get("approval_reasons", [])
    task = get_task(context.task_id) or {}
    create_pending_approval(
        context.task_id,
        task.get("approval_policy") or "never",
        reasons,
        state.get("plan"),
        state.get("validation_violations", []),
    )
    _transition(
        context,
        TaskStatus.AWAITING_APPROVAL,
        "Agent workflow is awaiting human approval",
        transcript=Transcript.model_validate(state["transcript"]).model_dump(),
        plan=state.get("plan"),
    )
    append_task_event(
        context.task_id,
        "awaiting_approval",
        "Agent workflow is awaiting human approval",
        {
            "thread_id": context.task_id,
            "reason_codes": [item.get("code") for item in reasons],
            "retry_count": int(state.get("repair_attempts", 0)),
        },
        dedupe_key="agent:awaiting_approval",
    )
    reason_codes = [item.get("code") for item in reasons]
    context.agent_trace.set_status(
        "awaiting_approval",
        retry_count=int(state.get("repair_attempts", 0)),
        failure_category=(
            "plan_repair_exhausted" if "plan_repair_exhausted" in reason_codes else None
        ),
    )


def _apply_persisted_decision(
    context: _RunContext,
    store: AgentCheckpointStore,
    checkpoint: dict,
    state: dict,
) -> tuple[dict, dict] | None:
    approval = get_agent_approval(context.task_id)
    if approval is None or approval["status"] == "pending":
        return None
    decision = approval["status"]
    context.agent_trace.append(
        "approval_decision",
        node="validation",
        status=decision,
        input_summary={"decision_version": approval["decision_version"]},
        output_summary={"resume_node": None if decision == "rejected" else "render"},
        retry_count=int(state.get("repair_attempts", 0)),
    )
    if decision == "rejected":
        rejected_state = {**state, "approval_decision": "rejected"}
        rejected = store.save(
            context.task_id,
            rejected_state,
            next_node=None,
            run_status="rejected",
            expected_version=checkpoint["checkpoint_version"],
        )
        _transition(context, TaskStatus.REJECTED, "Agent plan was rejected")
        context.metrics.finalize(
            context.attempt, TaskStatus.REJECTED.value, failure_category="human_rejected"
        )
        context.agent_trace.finalize(
            "rejected",
            retry_count=int(state.get("repair_attempts", 0)),
            failure_category="human_rejected",
        )
        return rejected, rejected_state
    approved_plan = approval.get("candidate_plan")
    if approved_plan is None:
        raise AgentWorkflowError("Approved Agent decision has no validated plan")
    updated = {
        **state,
        "plan_candidate": approved_plan,
        "plan": AnimationPlan.model_validate(approved_plan).model_dump(),
        "validation_violations": [],
        "approval_decision": decision,
    }
    resumed = store.save(
        context.task_id,
        updated,
        next_node="render",
        run_status="running",
        expected_version=checkpoint["checkpoint_version"],
    )
    append_task_event(
        context.task_id,
        "resumed",
        "Agent workflow resumed after human approval",
        {"thread_id": context.task_id, "decision": decision, "node": "render"},
        dedupe_key=f"agent:approval_resumed:{approval['decision_version']}",
    )
    return resumed, updated


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
        context.agent_trace.finalize(
            "completed",
            retry_count=int(state.get("repair_attempts", 0)),
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
        context.agent_trace.finalize(
            "cancelled",
            retry_count=int(state.get("repair_attempts", 0)),
            failure_category="cancelled",
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
        context.agent_trace.finalize(
            "failed",
            retry_count=int(state.get("repair_attempts", 0)),
            failure_category=str(error_category),
        )


def _record_unhandled_runner_failure(task_id: str, exc: Exception) -> None:
    """Converge corrupt/unreadable persisted work without exposing exception text."""

    task = get_task(task_id)
    if task is None or task["status"] in {
        TaskStatus.COMPLETED.value,
        TaskStatus.FAILED.value,
        TaskStatus.CANCELLED.value,
        TaskStatus.REJECTED.value,
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
    director_instruction: str | None = None,
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
        agent_trace=AgentTrace(safe_task_dir, task_id),
    )
    store = checkpoint_store or AgentCheckpointStore.for_storage_root(storage_root)
    existing = store.load(task_id)
    checkpoint = (
        store.create(task_id, _new_state(context, director_instruction))
        if existing is None
        else existing
    )
    state = _validated_state(checkpoint, task_id)
    _reconcile_completed_events(context, state)

    if checkpoint["run_status"] in {"completed", "cancelled", "failed"}:
        _reconcile_terminal_checkpoint(context, checkpoint)
        return checkpoint
    if checkpoint["run_status"] == "rejected":
        task = get_task(context.task_id)
        if task and task["status"] != TaskStatus.REJECTED.value:
            _transition(context, TaskStatus.REJECTED, "Agent plan was rejected")
        return checkpoint
    if checkpoint["run_status"] == "awaiting_approval":
        if is_cancellation_requested(task_id):
            checkpoint = store.save(
                task_id,
                state,
                next_node=checkpoint["next_node"],
                run_status="cancelled",
                expected_version=checkpoint["checkpoint_version"],
            )
            _reconcile_terminal_checkpoint(context, checkpoint)
            return checkpoint
        applied = _apply_persisted_decision(context, store, checkpoint, state)
        if applied is None:
            return checkpoint
        checkpoint, state = applied
        if checkpoint["run_status"] == "rejected":
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
        node_started_at = time.perf_counter()
        context.agent_trace.append(
            "node_run",
            node=node,
            status="started",
            retry_count=int(state.get("repair_attempts", 0)),
        )
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
            context.agent_trace.append(
                "node_run",
                node=node,
                status="completed",
                duration_ms=round((time.perf_counter() - node_started_at) * 1_000),
                retry_count=int(updated.get("repair_attempts", 0)),
            )
            if node == "validation" and updated.get("approval_reasons"):
                checkpoint = store.save(
                    task_id,
                    updated,
                    next_node=next_node,
                    run_status="awaiting_approval",
                    expected_version=checkpoint["checkpoint_version"],
                )
                _persist_approval_pause(context, updated)
                return checkpoint
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
            context.agent_trace.append(
                "node_run",
                node=node,
                status="failed",
                duration_ms=round((time.perf_counter() - node_started_at) * 1_000),
                error_category="cancelled",
                retry_count=int(state.get("repair_attempts", 0)),
            )
            _reconcile_terminal_checkpoint(context, checkpoint)
            return checkpoint
        except Exception as exc:
            error_category = (
                "plan_repair_exhausted"
                if isinstance(exc, PlanRepairExhausted)
                else exc.__class__.__name__
            )
            failed_state = {
                **state,
                "repair_attempts": (
                    exc.attempts if isinstance(exc, PlanRepairExhausted) else state.get("repair_attempts", 0)
                ),
                "failure": {
                    "node": node,
                    "error_category": error_category,
                },
            }
            checkpoint = store.save(
                task_id,
                failed_state,
                next_node=node,
                run_status="failed",
                expected_version=checkpoint["checkpoint_version"],
            )
            context.agent_trace.append(
                "node_run",
                node=node,
                status="failed",
                duration_ms=round((time.perf_counter() - node_started_at) * 1_000),
                error_category=error_category,
                retry_count=int(failed_state.get("repair_attempts", 0)),
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
    director_instruction: str | None = None,
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
                    director_instruction,
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
    if task["status"] in {
        status.value
        for status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.REJECTED)
    }:
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
        task.get("director_instruction"),
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
