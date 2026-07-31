import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status

from .config import MAX_UPLOAD_BYTES, STORAGE_ROOT
from .schemas import VideoMetadata
from .video import VideoProbeError, probe_video

app = FastAPI(title="Semantic Video Animation Agent")


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
async def upload_video(file: UploadFile = File(...)) -> dict[str, str | VideoMetadata]:
    if not file.filename or Path(file.filename).suffix.lower() != ".mp4":
        raise HTTPException(status_code=400, detail="Only .mp4 uploads are accepted")
    task_id = str(uuid4())
    task_dir = STORAGE_ROOT / task_id
    source = task_dir / "source.mp4"
    task_dir.mkdir(parents=True, exist_ok=False)
    try:
        await save_mp4(file, source)
        metadata = probe_video(source)
    except HTTPException:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise
    except VideoProbeError as exc:
        shutil.rmtree(task_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"task_id": task_id, "metadata": metadata}
