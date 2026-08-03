"""Deterministic output quality and animation safe-area checks."""

import json
import math
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import COMMAND_TIMEOUT_SECONDS
from .schemas import AnimationPlan, VideoMetadata
from .video import VideoProbeError, _frame_rate, ensure_storage_path


class QualityValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutputQuality:
    duration_seconds: float
    width: int
    height: int
    frame_rate: float
    frame_count: int
    has_audio: bool


def validate_animation_safe_areas(plan: AnimationPlan, width: int, height: int) -> None:
    """Reject text that cannot fit inside the renderer's 8% horizontal safe area."""
    safe_width = width * 0.84
    keyword_font_size = max(28, min(72, round(width / 10)))
    for animation in plan.animations:
        if animation.type == "keyword_pop":
            available_text_width = safe_width - 68
            characters_per_line = max(1, math.floor(available_text_width / keyword_font_size))
            line_count = math.ceil(len(animation.parameters.text) / characters_per_line)
            if line_count > 3:
                raise QualityValidationError(
                    f"{animation.id} keyword text exceeds the {round(safe_width)} px horizontal safe area"
                )
        if animation.type == "media_visual" and width * 0.27 > safe_width:
            raise QualityValidationError(f"{animation.id} media visual exceeds the horizontal safe area")
    if width < 240 or height < 240:
        raise QualityValidationError("video dimensions are too small for the supported safe-area layout")


def verify_overlay_has_alpha(overlay: Path) -> None:
    """Require the Remotion overlay to preserve transparency before compositing."""
    overlay = ensure_storage_path(overlay)
    result = _run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=pix_fmt", "-of", "json", str(overlay),
    ])
    if result.returncode != 0:
        raise QualityValidationError(f"overlay probe failed: {result.stderr.strip()}")
    try:
        pixel_format = json.loads(result.stdout)["streams"][0]["pix_fmt"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise QualityValidationError("overlay probe returned incomplete metadata") from exc
    if "a" not in pixel_format:
        raise QualityValidationError("animation overlay has no alpha channel")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=COMMAND_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualityValidationError(f"quality command failed: {exc}") from exc


def _probe_output(path: Path) -> OutputQuality:
    result = _run([
        "ffprobe", "-v", "error", "-count_frames",
        "-show_entries", "format=duration:stream=codec_type,width,height,avg_frame_rate,r_frame_rate,nb_read_frames",
        "-of", "json", str(path),
    ])
    if result.returncode != 0:
        raise QualityValidationError(f"ffprobe quality check failed: {result.stderr.strip()}")
    try:
        payload = json.loads(result.stdout)
        video = next(stream for stream in payload["streams"] if stream.get("codec_type") == "video")
        duration = float(payload["format"]["duration"])
        frame_count = int(video["nb_read_frames"])
        quality = OutputQuality(
            duration_seconds=duration,
            width=int(video["width"]),
            height=int(video["height"]),
            frame_rate=_frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
            frame_count=frame_count,
            has_audio=any(stream.get("codec_type") == "audio" for stream in payload["streams"]),
        )
    except (KeyError, StopIteration, TypeError, ValueError, VideoProbeError) as exc:
        raise QualityValidationError("ffprobe quality check returned incomplete metadata") from exc
    if quality.duration_seconds <= 0 or quality.frame_count <= 0:
        raise QualityValidationError("output has no decodable video frames")
    return quality


def verify_output_quality(result: Path, source: VideoMetadata) -> OutputQuality:
    """Decode the output and enforce source-compatible delivery constraints."""
    result = ensure_storage_path(result)
    quality = _probe_output(result)
    if (quality.width, quality.height) != (source.width, source.height):
        raise QualityValidationError("output dimensions do not match source video")
    if abs(quality.frame_rate - source.frame_rate) > 0.1:
        raise QualityValidationError("output frame rate does not match source video")
    duration_tolerance = max(0.25, 3 / source.frame_rate)
    if abs(quality.duration_seconds - source.duration_seconds) > duration_tolerance:
        raise QualityValidationError("output duration is outside the allowed tolerance")
    expected_frames = round(source.duration_seconds * source.frame_rate)
    if abs(quality.frame_count - expected_frames) > 3:
        raise QualityValidationError("output frame count is outside the allowed tolerance")
    if source.has_audio and not quality.has_audio:
        raise QualityValidationError("output is missing the source audio stream")

    for stream in (["0:v:0"] + (["0:a:0"] if source.has_audio else [])):
        decoded = _run(["ffmpeg", "-v", "error", "-i", str(result), "-map", stream, "-f", "null", "-"])
        if decoded.returncode != 0:
            raise QualityValidationError(f"output {stream} stream could not be decoded: {decoded.stderr.strip()}")
    return quality


def write_quality_report(destination: Path, quality: OutputQuality) -> Path:
    destination = ensure_storage_path(destination)
    destination.write_text(json.dumps(asdict(quality), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
