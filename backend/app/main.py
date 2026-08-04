import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import MAX_UPLOAD_BYTES, PROJECT_ROOT, SETTINGS, STORAGE_ROOT
from .database import create_task, get_task, get_task_events, initialize_database, request_cancellation, start_review_render, update_transcript
from .errors import AppError
from .logging_config import configure_logging
from .metrics import TaskMetrics, initialize_initial_metrics, read_metrics
from .media_providers import MediaProviderError, get_media_provider_by_name, load_candidates, manual_candidate, save_candidates
from .process_control import process_registry
from .planning_rules import PlanningRuleError, validate_animation_plan
from .schemas import ManualMediaCandidateInput, MediaSearchRequest, ReviewUpdate, Transcript, VideoMetadata
from .storage import StorageService
from .video import VideoProbeError, probe_video
from .workflow import start_review_task, start_task

@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    initialize_database()
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
) -> dict:
    if processing_profile not in {"configured", "real", "mock"}:
        raise HTTPException(status_code=422, detail="processing_profile must be configured, real, or mock")
    if media_provider not in {"mock", "manual", "wikimedia_commons", "pexels"}:
        raise HTTPException(status_code=422, detail="media_provider must be mock, manual, wikimedia_commons, or pexels")
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
        create_task(task_id, metadata.model_dump(), request.state.trace_id)
        initialize_initial_metrics(task_dir, task_id, request.state.trace_id, round((time.perf_counter() - upload_probe_started_at) * 1000))
        start_task(task_id, task_dir, metadata, request.state.trace_id, processing_profile, media_provider)
    except HTTPException:
        storage.remove_task_directory(task_id)
        raise
    except VideoProbeError as exc:
        storage.remove_task_directory(task_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "pending", "metadata": metadata, "trace_id": request.state.trace_id}


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
    return {"assets": plan.get("media_assets", []), "usage": usage, "candidates": candidates}


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
    return {"query": request.query, "candidates": candidates}


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
    return {"candidate": candidate}


@app.get("/api/videos/{task_id}/download")
def download_video(task_id: str) -> FileResponse:
    task = get_task(task_id)
    try:
        result = StorageService(STORAGE_ROOT).task_directory(task_id) / "result.mp4"
    except ValueError:
        raise HTTPException(status_code=404, detail="Result video not found") from None
    if task is None or task["status"] != "completed" or not result.is_file():
        raise HTTPException(status_code=404, detail="Result video not found")
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
            if task is None or task["status"] in {"completed", "failed", "cancelled"}:
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
    try:
        plan = validate_animation_plan(review.plan, review.transcript)
    except PlanningRuleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not start_review_render(task_id, review.transcript.model_dump(), plan.model_dump()):
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
    start_review_task(task_id, task_dir, VideoMetadata.model_validate(task["metadata"]), review.transcript, plan, task["trace_id"])
    return {"task_id": task_id, "status": "rendering", "transcript": review.transcript, "plan": plan}


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
