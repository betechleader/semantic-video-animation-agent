import json
import subprocess
from pathlib import Path

from .config import COMMAND_TIMEOUT_SECONDS, RENDERER_ROOT
from .database import is_cancellation_requested
from .process_control import process_registry
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .subtitles import ffmpeg_filter_path, write_ass
from .video import ensure_storage_path


class ProcessingError(RuntimeError):
    pass


class ProcessingCancelled(ProcessingError):
    pass


def _run(command: list[str], *, cwd: Path | None = None, task_id: str | None = None) -> None:
    try:
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
        if task_id:
            process_registry.register(task_id, process)
        stdout, stderr = process.communicate(timeout=COMMAND_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if "process" in locals() and process.poll() is None:
            process.terminate()
        raise ProcessingError(f"External command failed: {exc}") from exc
    finally:
        if task_id and "process" in locals():
            process_registry.unregister(task_id, process)
    if task_id and is_cancellation_requested(task_id):
        raise ProcessingCancelled("Task was cancelled while running an external command")
    if process.returncode != 0:
        raise ProcessingError(stderr.strip() or stdout.strip() or "External command failed")


def render_and_composite(task_dir: Path, metadata: VideoMetadata, transcript: Transcript, plan: AnimationPlan, task_id: str | None = None) -> tuple[dict, dict]:
    safe_dir = ensure_storage_path(task_dir)
    source = safe_dir / "source.mp4"
    overlay = safe_dir / "animation.mov"
    subtitles = safe_dir / "subtitles.ass"
    result = safe_dir / "result.mp4"
    props = {
        "animations": [animation.model_dump() for animation in plan.animations],
        "width": metadata.width, "height": metadata.height,
        "fps": metadata.frame_rate, "durationInFrames": max(1, round(metadata.duration_seconds * metadata.frame_rate)),
    }
    _run([
        "npx.cmd", "remotion", "render", "src/index.ts", "AnimationOverlay", str(overlay),
        "--codec=prores", "--prores-profile=4444", "--props=" + json.dumps(props, ensure_ascii=False),
    ], cwd=RENDERER_ROOT, task_id=task_id)
    write_ass(transcript, subtitles, metadata.width, metadata.height)
    command = [
        "ffmpeg", "-y", "-i", str(source), "-i", str(overlay),
        "-filter_complex", f"[0:v][1:v]overlay=0:0:format=auto[v0];[v0]subtitles='{ffmpeg_filter_path(subtitles)}'[v]", "-map", "[v]",
    ]
    if metadata.has_audio:
        command += ["-map", "0:a:0?", "-c:a", "aac"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(result)]
    _run(command, task_id=task_id)
    if not result.is_file() or result.stat().st_size == 0:
        raise ProcessingError("Rendering completed without producing result.mp4")
    return transcript.model_dump(), plan.model_dump()
