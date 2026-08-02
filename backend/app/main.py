import shutil
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import MAX_UPLOAD_BYTES, PROJECT_ROOT, STORAGE_ROOT
from .database import create_task, get_task, get_task_events, initialize_database, request_cancellation, transition_task
from .errors import AppError
from .logging_config import configure_logging
from .models import TaskStatus
from .processing import ProcessingError, render_and_composite
from .schemas import VideoMetadata
from .storage import StorageService
from .video import VideoProbeError, probe_video

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


@app.post("/api/videos", status_code=status.HTTP_201_CREATED)
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
        if not transition_task(task_id, TaskStatus.PROCESSING, "Video metadata validated"):
            raise AppError(409, "task_cancelled", "Task was cancelled before processing")
        if not transition_task(task_id, TaskStatus.RENDERING, "Rendering animation and compositing video"):
            raise AppError(409, "task_cancelled", "Task was cancelled before rendering")
        transcript, plan = render_and_composite(task_dir, metadata)
        transition_task(task_id, TaskStatus.COMPLETED, "Result video created", transcript=transcript, plan=plan)
    except HTTPException:
        storage.remove_task_directory(task_id)
        raise
    except VideoProbeError as exc:
        storage.remove_task_directory(task_id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProcessingError as exc:
        transition_task(task_id, TaskStatus.FAILED, "Rendering failed", error=str(exc))
        logger.error("task_failed", extra={"task_id": task_id, "trace_id": request.state.trace_id, "event_type": "failed"})
        raise HTTPException(status_code=500, detail=f"Rendering failed: {exc}") from exc
    logger.info("task_completed", extra={"task_id": task_id, "trace_id": request.state.trace_id, "event_type": "completed"})
    return {"task_id": task_id, "status": "completed", "metadata": metadata, "trace_id": request.state.trace_id}


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
def stream_task_events(task_id: str) -> StreamingResponse:
    if get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    def event_stream():
        for event in get_task_events(task_id):
            yield f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/videos/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_video_task(task_id: str) -> dict:
    if not request_cancellation(task_id):
        raise HTTPException(status_code=409, detail="Task cannot be cancelled")
    return {"task_id": task_id, "status": "cancellation_requested"}


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
