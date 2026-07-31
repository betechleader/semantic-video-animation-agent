import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import MAX_UPLOAD_BYTES, PROJECT_ROOT, STORAGE_ROOT
from .database import create_task, get_task, initialize_database, update_task
from .processing import ProcessingError, render_and_composite
from .schemas import VideoMetadata
from .video import VideoProbeError, probe_video

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Semantic Video Animation Agent", lifespan=lifespan)


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
async def upload_video(file: UploadFile = File(...)) -> dict:
    if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only .mp4 uploads are accepted")
    task_id = str(uuid4())
    task_dir = STORAGE_ROOT / task_id
    source = task_dir / "source.mp4"
    task_dir.mkdir(parents=True, exist_ok=False)
    try:
        await save_mp4(file, source)
        metadata = probe_video(source)
        create_task(task_id, metadata.model_dump())
        transcript, plan = render_and_composite(task_dir, metadata)
        update_task(task_id, "completed", transcript, plan)
    except HTTPException:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise
    except VideoProbeError as exc:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProcessingError as exc:
        update_task(task_id, "failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Rendering failed: {exc}") from exc
    return {"task_id": task_id, "status": "completed", "metadata": metadata}


@app.get("/api/videos/{task_id}")
def get_video_task(task_id: str) -> dict:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/videos/{task_id}/download")
def download_video(task_id: str) -> FileResponse:
    task = get_task(task_id)
    result = STORAGE_ROOT / task_id / "result.mp4"
    if task is None or task["status"] != "completed" or not result.is_file():
        raise HTTPException(status_code=404, detail="Result video not found")
    return FileResponse(result, media_type="video/mp4", filename="result.mp4")


app.mount("/", StaticFiles(directory=PROJECT_ROOT / "frontend", html=True), name="frontend")
