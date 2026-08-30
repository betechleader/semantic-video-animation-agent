import json
import hashlib
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import KNOWLEDGE_ROOT, MAX_UPLOAD_BYTES, PROJECT_ROOT, SETTINGS, STORAGE_ROOT
from .asr_corrections import correct_transcript, load_phrase_corrections, normalize_review_transcript
from .database import (
    append_task_event,
    begin_latest_plan_undo,
    begin_plan_patch_apply,
    create_task,
    create_plan_patch,
    decide_plan_patch,
    decide_agent_approval,
    ensure_plan_version,
    get_agent_approval,
    get_task,
    get_task_events,
    get_plan_patch,
    get_latest_plan_undo_candidate,
    initialize_database,
    request_cancellation,
    list_plan_versions,
    start_review_render,
    update_transcript,
)
from .errors import AppError
from .logging_config import configure_logging
from .metrics import TaskMetrics, initialize_initial_metrics, read_metrics
from .media_providers import MediaProviderError, get_media_provider_by_name, load_candidates, manual_candidate, save_candidates
from .process_control import process_registry
from .planning_rules import PlanningRuleError, validate_animation_plan
from .quality import QualityValidationError, validate_animation_safe_areas
from .providers import TranscriptAnimationPlanningProvider
from .schemas import AgentApprovalEdit, AnimationPlan, KnowledgeSearchRequest, ManualMediaCandidateInput, MediaSearchRequest, PlanPatch, PlanPatchApprovalRequest, PlanPatchPreviewRequest, PlanPatchRejectRequest, ReviewUpdate, Transcript, VideoMetadata
from .storage import StorageService
from .video import VideoProbeError, probe_video
from .workflow import start_review_task, start_task
from .agent_workflow import get_active_agent_thread, recover_agent_tasks, resume_agent_task, start_agent_task
from .execution import (
    active_worker_count,
    enqueue_agent_resume,
    enqueue_initial_task,
    enqueue_review,
    execution_metrics,
    recover_execution_jobs,
)
from .agent_tools import DIRECTOR_INSTRUCTION_MAX_LENGTH
from .agent_trace import AgentTraceError, read_agent_trace
from .rag_tools import (
    EvidenceValidationError,
    RetrieveEvidenceInput,
    build_evidence_queries,
    evidence_status,
    ground_candidate_with_evidence,
)
from .knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseService,
    KnowledgeEmbeddingError,
    KnowledgeNotFoundError,
    KnowledgeValidationError,
)
from .workflow_services import retrieve_agent_evidence, validate_agent_plan_evidence
from .plan_patches import PlanPatchError, apply_plan_patch, build_rule_plan_patch

@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    initialize_database()
    if SETTINGS.execution_mode == "worker":
        recover_execution_jobs()
    else:
        recover_agent_tasks(storage_root=STORAGE_ROOT)
    yield


app = FastAPI(title="Semantic Video Animation Agent", lifespan=lifespan)
logger = logging.getLogger("semantic_video")


@app.middleware("http")
async def trace_request(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid4()))
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message, "trace_id": trace_id}})


async def save_mp4(upload: UploadFile, destination: Path) -> None:
    total = 0
    try:
        with destination.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload exceeds 100 MB limit")
                output.write(chunk)
    finally:
        await upload.close()


@app.post("/api/videos", status_code=status.HTTP_202_ACCEPTED)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    processing_profile: str = Form("configured"),
    media_provider: str = Form("mock"),
    workflow_mode: str = Form("standard"),
    director_instruction: str | None = Form(None),
    approval_policy: str = Form("never"),
) -> dict:
    if workflow_mode not in {"standard", "agent"}:
        raise HTTPException(status_code=422, detail="workflow_mode must be standard or agent")
    if processing_profile not in {"configured", "real", "mock"}:
        raise HTTPException(status_code=422, detail="processing_profile must be configured, real, or mock")
    if media_provider not in {"mock", "manual", "knowledge", "wikimedia_commons", "pexels"}:
        raise HTTPException(status_code=422, detail="media_provider must be mock, manual, knowledge, wikimedia_commons, or pexels")
    if workflow_mode == "agent" and approval_policy not in {"never", "on_risk", "always"}:
        raise HTTPException(status_code=422, detail="approval_policy must be never, on_risk, or always")
    normalized_instruction = director_instruction.strip() if director_instruction else None
    if (
        workflow_mode == "agent"
        and normalized_instruction
        and len(normalized_instruction) > DIRECTOR_INSTRUCTION_MAX_LENGTH
    ):
        raise HTTPException(
            status_code=422,
            detail=f"director_instruction must be at most {DIRECTOR_INSTRUCTION_MAX_LENGTH} characters",
        )
    if workflow_mode == "standard":
        normalized_instruction = None
        approval_policy = "never"
    if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only .mp4 uploads are accepted")
    task_id = str(uuid4())
    storage = StorageService(STORAGE_ROOT)
    task_dir = storage.create_task_directory(task_id)
    source = task_dir / "source.mp4"
    upload_probe_started_at = time.perf_counter()
    try:
        await save_mp4(file, source)
        metadata = probe_video(source)
        create_task(
            task_id,
            metadata.model_dump(),
            request.state.trace_id,
            workflow_mode=workflow_mode,
            processing_profile=processing_profile,
            media_provider=media_provider,
            director_instruction=normalized_instruction,
            approval_policy=approval_policy,
        )
        initialize_initial_metrics(task_dir, task_id, request.state.trace_id, round((time.perf_counter() - upload_probe_started_at) * 1000))
        if SETTINGS.execution_mode == "worker":
            enqueue_initial_task(task_id, workflow_mode)
        elif workflow_mode == "agent":
            agent_args = (
                task_id,
                task_dir,
                metadata,
                request.state.trace_id,
                processing_profile,
                media_provider,
            )
            if normalized_instruction:
                start_agent_task(*agent_args, director_instruction=normalized_instruction)
            else:
                start_agent_task(*agent_args)
        else:
            start_task(task_id, task_dir, metadata, request.state.trace_id, processing_profile, media_provider)
    except HTTPException:
        storage.remove_task_directory(task_id)
        raise
    except VideoProbeError as exc:
        storage.remove_task_directory(task_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "task_id": task_id,
        "status": "pending",
        "workflow_mode": workflow_mode,
        "approval_policy": approval_policy if workflow_mode == "agent" else None,
        "metadata": metadata,
        "trace_id": request.state.trace_id,
    }


@app.get("/api/videos/{task_id}")
def get_video_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/videos/{task_id}/metrics")
def get_video_metrics(task_id: str) -> dict:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Task metrics not found") from None
    metrics = read_metrics(task_dir, task_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail="Task metrics not found")
    return metrics


@app.get("/api/videos/{task_id}/agent-trace")
def get_video_agent_trace(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["workflow_mode"] != "agent":
        raise HTTPException(status_code=409, detail="Agent trace is only available for Agent tasks")
    try:
        task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
        trace = read_agent_trace(task_dir, task_id)
    except (ValueError, AgentTraceError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if trace is None:
        raise HTTPException(status_code=404, detail="Agent trace not found")
    return trace


def _pending_agent_approval(task_id: str) -> tuple[dict, dict]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["workflow_mode"] != "agent":
        raise HTTPException(status_code=409, detail="Approval is only available for Agent tasks")
    approval = get_agent_approval(task_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Agent approval not found")
    return task, approval


def _validate_approval_plan(task: dict, plan: AnimationPlan) -> AnimationPlan:
    """Apply every deterministic pre-render validator before consuming approval."""

    validated = validate_animation_plan(plan, Transcript.model_validate(task["transcript"]))
    validated = validate_agent_plan_evidence(validated)
    metadata = VideoMetadata.model_validate(task["metadata"])
    validate_animation_safe_areas(validated, metadata.width, metadata.height)
    return validated


def _resume_after_approval(task_id: str) -> None:
    if SETTINGS.execution_mode == "worker":
        approval = get_agent_approval(task_id)
        if approval is not None:
            enqueue_agent_resume(task_id, int(approval["decision_version"]))
        return
    active = get_active_agent_thread(task_id)
    if active is None:
        resume_agent_task(task_id, STORAGE_ROOT)
        return

    def resume_when_paused_runner_exits() -> None:
        active.join()
        resume_agent_task(task_id, STORAGE_ROOT)

    threading.Thread(
        target=resume_when_paused_runner_exits,
        daemon=True,
        name=f"agent-approval-resume-{task_id}",
    ).start()


@app.get("/api/videos/{task_id}/approval")
def get_video_agent_approval(task_id: str) -> dict:
    _task, approval = _pending_agent_approval(task_id)
    return approval


@app.post("/api/videos/{task_id}/approval/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_video_agent_plan(task_id: str) -> dict:
    task, approval = _pending_agent_approval(task_id)
    if approval["status"] != "pending" or task["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    if approval["candidate_plan"] is None:
        raise HTTPException(status_code=409, detail="A valid edited plan is required before approval")
    try:
        plan = _validate_approval_plan(
            task, AnimationPlan.model_validate(approval["candidate_plan"])
        )
    except (EvidenceValidationError, PlanningRuleError, QualityValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    decided = decide_agent_approval(task_id, "approved", plan.model_dump())
    if decided is None:
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    append_task_event(
        task_id, "approved", "Agent plan approved", {"decision_version": decided["decision_version"]},
        dedupe_key=f"agent:approved:{decided['decision_version']}",
    )
    _resume_after_approval(task_id)
    return {"task_id": task_id, "status": "approved", "decision_version": decided["decision_version"]}


@app.post("/api/videos/{task_id}/approval/edit", status_code=status.HTTP_202_ACCEPTED)
def edit_video_agent_plan(task_id: str, edit: AgentApprovalEdit) -> dict:
    task, approval = _pending_agent_approval(task_id)
    if approval["status"] != "pending" or task["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    try:
        plan = _validate_approval_plan(task, edit.plan)
    except (EvidenceValidationError, PlanningRuleError, QualityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    decided = decide_agent_approval(task_id, "edited", plan.model_dump())
    if decided is None:
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    append_task_event(
        task_id, "edited", "Agent plan edited and approved", {"decision_version": decided["decision_version"]},
        dedupe_key=f"agent:edited:{decided['decision_version']}",
    )
    _resume_after_approval(task_id)
    return {"task_id": task_id, "status": "edited", "decision_version": decided["decision_version"]}


@app.post("/api/videos/{task_id}/approval/reject", status_code=status.HTTP_202_ACCEPTED)
def reject_video_agent_plan(task_id: str) -> dict:
    task, approval = _pending_agent_approval(task_id)
    if approval["status"] != "pending" or task["status"] != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    decided = decide_agent_approval(task_id, "rejected")
    if decided is None:
        raise HTTPException(status_code=409, detail="Agent approval has already been decided")
    _resume_after_approval(task_id)
    return {"task_id": task_id, "status": "rejected", "decision_version": decided["decision_version"]}


def _completed_agent_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["workflow_mode"] != "agent":
        raise HTTPException(status_code=409, detail="Natural-language plan patches are only available for Agent tasks")
    if task["status"] != "completed" or task.get("plan") is None or task.get("transcript") is None:
        raise HTTPException(status_code=409, detail="Plan patches are available after an Agent task completes")
    return task


def _validate_patched_plan(task: dict, plan: AnimationPlan) -> AnimationPlan:
    validated = validate_animation_plan(plan, Transcript.model_validate(task["transcript"]))
    validated = validate_agent_plan_evidence(validated)
    metadata = VideoMetadata.model_validate(task["metadata"])
    validate_animation_safe_areas(validated, metadata.width, metadata.height)
    return validated


def _start_patch_render(task_id: str, task: dict, plan: AnimationPlan, patch_id: str | None) -> None:
    task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
    metrics = TaskMetrics(task_dir, task_id)
    try:
        metrics.current_or_start_attempt("review")
    except RuntimeError:
        metrics = initialize_initial_metrics(task_dir, task_id, task["trace_id"], 0)
        metrics.finalize(1, "completed")
        metrics.current_or_start_attempt("review")
    if SETTINGS.execution_mode == "worker":
        enqueue_review(task_id, patch_id=patch_id)
        return
    start_review_task(
        task_id,
        task_dir,
        VideoMetadata.model_validate(task["metadata"]),
        Transcript.model_validate(task["transcript"]),
        plan,
        task["trace_id"],
        patch_id,
    )


@app.post("/api/videos/{task_id}/plan-patches/preview", status_code=status.HTTP_201_CREATED)
def preview_video_plan_patch(task_id: str, request: PlanPatchPreviewRequest) -> dict:
    task = _completed_agent_task(task_id)
    current = AnimationPlan.model_validate(task["plan"])
    try:
        patch = build_rule_plan_patch(request.instruction, current)
        preview = _validate_patched_plan(
            task, apply_plan_patch(current, patch, [item.operation_id for item in patch.operations])
        )
    except (PlanPatchError, PlanningRuleError, EvidenceValidationError, QualityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    base_version = ensure_plan_version(task_id, current.model_dump())
    patch_id = str(uuid4())
    record = create_plan_patch(
        task_id,
        patch_id,
        hashlib.sha256(request.instruction.encode("utf-8")).hexdigest(),
        base_version,
        patch.model_dump(),
    )
    append_task_event(task_id, "plan_patch_previewed", "Natural-language plan patch preview created", {
        "patch_id": patch_id, "base_version": base_version, "operation_count": len(patch.operations),
    })
    return {**record, "preview_plan": preview.model_dump()}


@app.get("/api/videos/{task_id}/plan-patches/{patch_id}")
def get_video_plan_patch(task_id: str, patch_id: str) -> dict:
    record = get_plan_patch(task_id, patch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan patch not found")
    return record


@app.get("/api/videos/{task_id}/plan-versions")
def get_video_plan_versions(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["workflow_mode"] != "agent":
        raise HTTPException(status_code=409, detail="Plan versions are only available for Agent tasks")
    return {"task_id": task_id, "versions": list_plan_versions(task_id)}


@app.post("/api/videos/{task_id}/plan-patches/{patch_id}/approve")
def approve_video_plan_patch(task_id: str, patch_id: str, request: PlanPatchApprovalRequest) -> dict:
    task = _completed_agent_task(task_id)
    record = get_plan_patch(task_id, patch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan patch not found")
    try:
        patch = PlanPatch.model_validate(record["patch"])
        preview = _validate_patched_plan(
            task,
            apply_plan_patch(AnimationPlan.model_validate(task["plan"]), patch, request.operation_ids),
        )
    except (PlanPatchError, PlanningRuleError, EvidenceValidationError, QualityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    decided = decide_plan_patch(task_id, patch_id, "approved", request.operation_ids)
    if decided is None:
        raise HTTPException(status_code=409, detail="Plan patch has already been decided")
    append_task_event(task_id, "plan_patch_approved", "Plan patch operations approved", {
        "patch_id": patch_id, "operation_count": len(request.operation_ids),
    })
    return {**decided, "preview_plan": preview.model_dump()}


@app.post("/api/videos/{task_id}/plan-patches/{patch_id}/reject")
def reject_video_plan_patch(task_id: str, patch_id: str, request: PlanPatchRejectRequest) -> dict:
    _completed_agent_task(task_id)
    decided = decide_plan_patch(task_id, patch_id, "rejected", reason=request.reason)
    if decided is None:
        raise HTTPException(status_code=409, detail="Plan patch has already been decided")
    append_task_event(task_id, "plan_patch_rejected", "Plan patch rejected", {"patch_id": patch_id})
    return decided


@app.post("/api/videos/{task_id}/plan-patches/{patch_id}/apply", status_code=status.HTTP_202_ACCEPTED)
def apply_video_plan_patch(task_id: str, patch_id: str) -> dict:
    task = _completed_agent_task(task_id)
    record = get_plan_patch(task_id, patch_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Plan patch not found")
    if record["status"] != "approved":
        raise HTTPException(status_code=409, detail="Plan patch must be approved before apply")
    try:
        plan = _validate_patched_plan(task, apply_plan_patch(
            AnimationPlan.model_validate(task["plan"]),
            PlanPatch.model_validate(record["patch"]),
            record["approved_operation_ids"],
        ))
    except (PlanPatchError, PlanningRuleError, EvidenceValidationError, QualityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    started = begin_plan_patch_apply(task_id, patch_id, plan.model_dump())
    if started is None:
        raise HTTPException(status_code=409, detail="Plan patch is stale, already applied, or the task is busy")
    _start_patch_render(task_id, task, plan, patch_id)
    return {"task_id": task_id, "patch_id": patch_id, "status": "rendering", "plan_version": started["resulting_version"]}


@app.post("/api/videos/{task_id}/plan-patches/undo", status_code=status.HTTP_202_ACCEPTED)
def undo_latest_video_plan_patch(task_id: str) -> dict:
    task = _completed_agent_task(task_id)
    candidate = get_latest_plan_undo_candidate(task_id)
    if candidate is None:
        raise HTTPException(status_code=409, detail="There is no applied plan patch to undo")
    try:
        plan = _validate_patched_plan(task, AnimationPlan.model_validate(candidate["plan"]))
    except (PlanningRuleError, EvidenceValidationError, QualityValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    restored = begin_latest_plan_undo(task_id, plan.model_dump())
    if restored is None:
        raise HTTPException(status_code=409, detail="The latest plan patch can no longer be undone")
    _start_patch_render(task_id, task, plan, None)
    return {"task_id": task_id, "patch_id": restored["patch_id"], "status": "rendering", "plan_version": restored["plan_version"]}


@app.get("/api/videos/{task_id}/evidence")
def get_video_agent_evidence(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["workflow_mode"] != "agent":
        raise HTTPException(status_code=409, detail="Evidence is only available for Agent tasks")
    if task.get("plan") is None:
        return {"valid": True, "count": 0, "items": []}
    try:
        return evidence_status(AnimationPlan.model_validate(task["plan"]), _knowledge_service())
    except (KnowledgeBaseError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _candidate_review(candidate: dict | object) -> dict:
    data = candidate.model_dump() if hasattr(candidate, "model_dump") else dict(candidate)
    query = str(data.get("query", "")).lower()
    searchable = f"{data.get('title', '')} {data.get('author_or_provider', '')}".lower()
    terms = {token for token in query.replace("-", " ").split() if len(token) > 1}
    matched = sorted(term for term in terms if term in searchable)
    relevance = round(len(matched) / max(1, len(terms)), 3)
    data["review_relevance"] = relevance
    data["selection_reason"] = (
        f"Matched candidate metadata: {', '.join(matched[:4])}"
        if matched else "No direct metadata match; reviewer confirmation required"
    )
    return data


@app.get("/api/videos/{task_id}/media")
def get_video_media_review(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["plan"] is None:
        raise HTTPException(status_code=409, detail="Media review is available after a plan is created")
    try:
        task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
        candidates = load_candidates(task_dir)
    except (ValueError, MediaProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    plan = task["plan"]
    usage = {
        animation["parameters"]["asset_id"]: {
            "animation_id": animation["id"], "start_ms": animation["start_ms"], "end_ms": animation["end_ms"],
            "enabled": animation["parameters"].get("enabled", True), "query": animation["parameters"].get("search_query", "legacy visual"),
        }
        for animation in plan["animations"] if animation["type"] == "media_visual"
    }
    return {"assets": plan.get("media_assets", []), "usage": usage, "candidates": [_candidate_review(item) for item in candidates]}


@app.post("/api/videos/{task_id}/media/search")
def search_video_media(task_id: str, request: MediaSearchRequest) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=409, detail="Media search is available when a task is ready for review")
    try:
        plan_provider = task["plan"].get("media_provider", SETTINGS.media_provider) if task.get("plan") else SETTINGS.media_provider
        candidates = get_media_provider_by_name(plan_provider, SETTINGS).search(request.query, request.asset_kind)
        task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
        save_candidates(task_dir, candidates)
    except (ValueError, MediaProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"query": request.query, "candidates": [_candidate_review(item) for item in candidates]}


@app.post("/api/videos/{task_id}/media/candidates")
def add_manual_video_media_candidate(task_id: str, request: ManualMediaCandidateInput) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=409, detail="Media review is available when a task is ready for review")
    try:
        candidate = manual_candidate(request)
        task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
        save_candidates(task_dir, [candidate])
    except (ValueError, MediaProviderError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"candidate": _candidate_review(candidate)}


@app.get("/api/videos/{task_id}/download")
def download_video(task_id: str, preview: bool = False) -> FileResponse:
    task = get_task(task_id)
    try:
        result = StorageService(STORAGE_ROOT).task_directory(task_id) / "result.mp4"
    except ValueError:
        raise HTTPException(status_code=404, detail="Result video not found") from None
    if task is None or task["status"] != "completed" or not result.is_file():
        raise HTTPException(status_code=404, detail="Result video not found")
    if preview:
        return FileResponse(
            result,
            media_type="video/mp4",
            headers={"Content-Disposition": "inline", "Accept-Ranges": "bytes", "Cache-Control": "no-store"},
        )
    return FileResponse(result, media_type="video/mp4", filename="result.mp4")


@app.get("/api/videos/{task_id}/events")
def stream_task_events(task_id: str, after_event_id: int = 0) -> StreamingResponse:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    def event_stream():
        last_event_id = max(0, after_event_id)
        while True:
            events = get_task_events(task_id)
            for event in events:
                if event["id"] > last_event_id:
                    last_event_id = event["id"]
                    yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            task = get_task(task_id)
            if task is None or task["status"] in {"completed", "failed", "cancelled", "rejected"}:
                break
            time.sleep(0.25)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/videos/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_video_task(task_id: str) -> dict:
    if not request_cancellation(task_id):
        raise HTTPException(status_code=409, detail="Task cannot be cancelled")
    process_registry.cancel(task_id)
    return {"task_id": task_id, "status": "cancellation_requested"}


@app.put("/api/videos/{task_id}/transcript")
def edit_transcript(task_id: str, transcript: Transcript) -> dict:
    if not update_transcript(task_id, transcript.model_dump()):
        raise HTTPException(status_code=409, detail="Transcript cannot be edited while task is processing or does not exist")
    return {"task_id": task_id, "transcript": transcript}


@app.post("/api/videos/{task_id}/review", status_code=status.HTTP_202_ACCEPTED)
def save_review_and_rerender(task_id: str, review: ReviewUpdate) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        stored_transcript = Transcript.model_validate(task["transcript"])
        transcript, transcript_changed = normalize_review_transcript(review.transcript, stored_transcript)
        corrected = correct_transcript(
            transcript,
            load_phrase_corrections(SETTINGS.asr_correction_dictionary_path),
        )
        if corrected.full_text != transcript.full_text or corrected.segments != transcript.segments:
            transcript_changed = True
        transcript = corrected
        if transcript_changed:
            plan = TranscriptAnimationPlanningProvider().plan(transcript).model_copy(update={
                "media_provider": review.plan.media_provider,
            })
            if task.get("workflow_mode") == "agent":
                retrieved = retrieve_agent_evidence(
                    RetrieveEvidenceInput(queries=build_evidence_queries(transcript))
                )
                plan = AnimationPlan.model_validate(
                    ground_candidate_with_evidence(plan.model_dump(), retrieved.evidence)
                )
        else:
            # Provenance, face detections, and placements are renderer-derived.
            # Never require a browser editor to keep them synchronized with
            # enabled visuals or candidate changes.
            plan = review.plan.model_copy(update={
                "media_assets": [], "face_regions": [], "media_placements": [],
            })
        plan = validate_animation_plan(plan, transcript)
        if task.get("workflow_mode") == "agent":
            plan = validate_agent_plan_evidence(plan)
    except (EvidenceValidationError, PlanningRuleError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not start_review_render(task_id, transcript.model_dump(), plan.model_dump()):
        raise HTTPException(status_code=409, detail="Review edits are only available for completed tasks")
    task_dir = StorageService(STORAGE_ROOT).task_directory(task_id)
    metrics = TaskMetrics(task_dir, task_id)
    try:
        metrics.current_or_start_attempt("review")
    except RuntimeError:
        # Older successful tasks predate metrics.json. Preserve review support
        # while recording the newly requested review attempt.
        metrics = initialize_initial_metrics(task_dir, task_id, task["trace_id"], 0)
        metrics.finalize(1, "completed")
        metrics.current_or_start_attempt("review")
    if SETTINGS.execution_mode == "worker":
        enqueue_review(task_id)
    else:
        start_review_task(task_id, task_dir, VideoMetadata.model_validate(task["metadata"]), transcript, plan, task["trace_id"])
    return {"task_id": task_id, "status": "rendering", "transcript": transcript, "plan": plan, "replanned": transcript_changed}


@app.get("/health/live")
def health_live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    initialize_database()
    workers = active_worker_count() if SETTINGS.execution_mode == "worker" else 0
    ready = SETTINGS.execution_mode == "local" or workers > 0
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "not_ready", "execution_mode": SETTINGS.execution_mode, "active_workers": workers},
    )


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> str:
    """Expose local aggregate counters only; labels never contain task or user content."""

    snapshot = execution_metrics()
    lines = [
        "# HELP semantic_video_active_workers Active persistent workers.",
        "# TYPE semantic_video_active_workers gauge",
        f"semantic_video_active_workers {snapshot['active_workers']}",
    ]
    for status_name, count in sorted(snapshot["tasks"].items()):
        lines.append(f'semantic_video_tasks{{status="{status_name}"}} {count}')
    for status_name, count in sorted(snapshot["jobs"].items()):
        lines.append(f'semantic_video_execution_jobs{{status="{status_name}"}} {count}')
    return "\n".join(lines) + "\n"


def _knowledge_service() -> KnowledgeBaseService:
    return KnowledgeBaseService(root=KNOWLEDGE_ROOT, settings=SETTINGS)


@app.post("/api/knowledge/documents", status_code=status.HTTP_201_CREATED)
async def import_knowledge_document(
    file: UploadFile = File(...),
    metadata_json: str = Form("{}"),
) -> dict:
    if len(metadata_json) > 8_000:
        raise HTTPException(status_code=422, detail="knowledge metadata is too large")
    try:
        metadata = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="knowledge metadata must be valid JSON") from exc
    maximum_bytes = SETTINGS.knowledge_max_file_mb * 1024 * 1024
    data = bytearray()
    try:
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > maximum_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"Knowledge upload exceeds {SETTINGS.knowledge_max_file_mb} MB limit",
                )
    finally:
        await file.close()
    try:
        return await run_in_threadpool(
            _knowledge_service().import_document,
            file.filename or "",
            bytes(data),
            metadata,
        )
    except KnowledgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KnowledgeEmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/knowledge/documents")
def list_knowledge_documents() -> dict:
    return {"documents": _knowledge_service().list_documents()}


@app.delete("/api/knowledge/documents/{document_id}")
def delete_knowledge_document(document_id: str) -> dict:
    try:
        return _knowledge_service().delete_document(document_id)
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KnowledgeBaseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/knowledge/search")
def search_project_knowledge(request: KnowledgeSearchRequest) -> dict:
    try:
        return _knowledge_service().search(
            request.query,
            method=request.method,
            limit=request.limit,
            rerank=request.rerank,
        )
    except KnowledgeValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KnowledgeEmbeddingError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
