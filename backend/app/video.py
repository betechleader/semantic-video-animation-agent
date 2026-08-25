import json
import subprocess
from pathlib import Path

from .config import COMMAND_TIMEOUT_SECONDS, STORAGE_ROOT
from .schemas import VideoMetadata


class VideoProbeError(RuntimeError):
    pass


def ensure_storage_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(STORAGE_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Path must be inside storage") from exc
    return resolved


def _frame_rate(value: str | None) -> float:
    if not value or value == "0/0":
        raise VideoProbeError("Video stream has no valid frame rate")
    numerator, denominator = value.split("/", 1)
    rate = float(numerator) / float(denominator)
    if rate <= 0:
        raise VideoProbeError("Video stream has no valid frame rate")
    return rate


def parse_ffprobe_payload(payload: dict) -> VideoMetadata:
    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise VideoProbeError("Uploaded file does not contain a video stream")
    format_info = payload.get("format", {})
    try:
        duration = float(format_info["duration"])
        width = int(video["width"])
        height = int(video["height"])
        codec = str(video["codec_name"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VideoProbeError("ffprobe returned incomplete video metadata") from exc
    return VideoMetadata(
        duration_seconds=duration,
        width=width,
        height=height,
        frame_rate=_frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        video_codec=codec,
        audio_codec=str(audio["codec_name"]) if audio and audio.get("codec_name") else None,
        has_video=True,
        has_audio=audio is not None,
    )


def probe_video(path: Path) -> VideoMetadata:
    safe_path = ensure_storage_path(path)
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate",
        "-of", "json", str(safe_path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VideoProbeError(f"ffprobe failed: {exc}") from exc
    if result.returncode != 0:
        raise VideoProbeError(f"ffprobe failed: {result.stderr.strip()}")
    try:
        return parse_ffprobe_payload(json.loads(result.stdout))
    except json.JSONDecodeError as exc:
        raise VideoProbeError(f"ffprobe returned invalid JSON: {exc}") from exc
