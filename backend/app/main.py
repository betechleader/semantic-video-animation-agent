import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import MAX_UPLOAD_BYTES, PROJECT_ROOT, STORAGE_ROOT
from .database import create_task, get_task, get_task_events, initialize_database, request_cancellation, start_review_render, update_transcript
from .errors import AppError
from .logging_config import configure_logging
from .process_control import process_registry
from .planning_rules import PlanningRuleError, validate_animation_plan
from .schemas import ReviewUpdate, Transcript, VideoMetadata
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
async def upload_video(request: Request, file: UploadFile = File(...)) -> dict:
    if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only .mp4 uploads are accepted")
    task_id = str(uuid4())
    storage = StorageService(STORAGE_ROOT)
    task_dir = storage.create_task_directory(task_id)
    source = task_dir / "source.mp4"
    try:
        await save_mp4(file, source)
        metadata = probe_video(source)
        create_task(task_id, metadata.model_dump(), request.state.trace_id)
        start_task(task_id, task_dir, metadata, request.state.trace_id)
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
    start_review_task(task_id, task_dir, VideoMetadata.model_validate(task["metadata"]), review.transcript, plan, task["trace_id"])
    return {"task_id": task_id, "status": "rendering", "transcript": review.transcript, "plan": plan}


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
