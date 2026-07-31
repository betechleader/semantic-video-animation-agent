import json
import subprocess
from pathlib import Path

from .config import COMMAND_TIMEOUT_SECONDS, RENDERER_ROOT
from .mock_services import create_mock_plan, create_mock_transcript
from .schemas import VideoMetadata
from .video import ensure_storage_path


class ProcessingError(RuntimeError):
    pass


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessingError(f"External command failed: {exc}") from exc
    if result.returncode != 0:
        raise ProcessingError(result.stderr.strip() or result.stdout.strip() or "External command failed")


def render_and_composite(task_dir: Path, metadata: VideoMetadata) -> tuple[dict, dict]:
    safe_dir = ensure_storage_path(task_dir)
    source = safe_dir / "source.mp4"
    overlay = safe_dir / "animation.mov"
    result = safe_dir / "result.mp4"
    transcript = create_mock_transcript()
    plan = create_mock_plan(transcript)
    animation = plan.animations[0]
    props = {
        "text": animation.parameters.text, "color": animation.parameters.color,
        "position": animation.parameters.position, "start_ms": animation.start_ms,
        "end_ms": animation.end_ms, "width": metadata.width, "height": metadata.height,
        "fps": metadata.frame_rate, "durationInFrames": max(1, round(metadata.duration_seconds * metadata.frame_rate)),
    }
    _run([
        "npx.cmd", "remotion", "render", "src/index.ts", "KeywordPop", str(overlay),
        "--codec=prores", "--prores-profile=4444", "--props=" + json.dumps(props, ensure_ascii=False),
    ], cwd=RENDERER_ROOT)
    command = [
        "ffmpeg", "-y", "-i", str(source), "-i", str(overlay),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]", "-map", "[v]",
    ]
    if metadata.has_audio:
        command += ["-map", "0:a:0?", "-c:a", "aac"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(result)]
    _run(command)
    if not result.is_file() or result.stat().st_size == 0:
        raise ProcessingError("Rendering completed without producing result.mp4")
    return transcript.model_dump(), plan.model_dump()
