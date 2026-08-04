import json
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import TypeVar

from .config import COMMAND_TIMEOUT_SECONDS, RENDERER_ROOT
from .face_safety import FaceSafetyError, analyse_face_safe_areas
from .database import is_cancellation_requested
from .media_assets import prepare_media_assets, renderer_media_assets
from .media_providers import MediaProviderError
from .process_control import process_registry
from .quality import QualityValidationError, validate_animation_safe_areas, verify_output_quality, verify_overlay_has_alpha, write_quality_report
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .subtitles import build_dynamic_subtitle_cues, renderer_font_data_uri, write_ass
from .video import ensure_storage_path


class ProcessingError(RuntimeError):
    pass


class ProcessingCancelled(ProcessingError):
    pass


T = TypeVar("T")
StageRunner = Callable[[str, Callable[[], T]], T]


def _run(command: list[str], *, cwd: Path | None = None, task_id: str | None = None) -> None:
    try:
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            creationflags=creationflags,
        )
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


def write_remotion_props(destination: Path, props: dict) -> Path:
    """Keep render input out of the Windows command line length limit."""
    destination = ensure_storage_path(destination)
    destination.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    return destination


def remotion_render_command(overlay: Path, props_file: Path) -> list[str]:
    return [
        "npx.cmd", "remotion", "render", "src/index.ts", "AnimationOverlay", str(overlay),
        "--codec=prores", "--prores-profile=4444", "--image-format=png", "--pixel-format=yuva444p10le",
        f"--props={props_file}",
    ]


def render_and_composite(
    task_dir: Path,
    metadata: VideoMetadata,
    transcript: Transcript,
    plan: AnimationPlan,
    task_id: str | None = None,
    stage_runner: StageRunner | None = None,
) -> tuple[dict, dict, dict]:
    def run_stage(stage: str, action: Callable[[], T]) -> T:
        return stage_runner(stage, action) if stage_runner else action()

    safe_dir = ensure_storage_path(task_dir)
    source = safe_dir / "source.mp4"
    overlay = safe_dir / "animation.mov"
    props_file = safe_dir / "remotion_props.json"
    subtitles = safe_dir / "subtitles.ass"
    result = safe_dir / "result.mp4"
    def acquire_media() -> AnimationPlan:
        try:
            return prepare_media_assets(safe_dir, plan)
        except (ValueError, MediaProviderError) as exc:
            raise ProcessingError(f"Media asset validation failed: {exc}") from exc

    plan = run_stage("media_asset_acquisition", acquire_media)

    def prepare_safe_media() -> AnimationPlan:
        try:
            prepared_plan = analyse_face_safe_areas(safe_dir, metadata, plan)
        except FaceSafetyError as exc:
            raise ProcessingError(f"Local face safety analysis failed: {exc}") from exc
        validate_animation_safe_areas(prepared_plan, metadata.width, metadata.height)
        return prepared_plan

    plan = run_stage("media_safety_analysis", prepare_safe_media)
    props = {
        "animations": [animation.model_dump() for animation in plan.animations],
        "mediaAssets": renderer_media_assets(safe_dir, plan),
        "mediaPlacements": [placement.model_dump() for placement in plan.media_placements],
        "subtitleCues": build_dynamic_subtitle_cues(transcript, plan),
        "fontDataUri": renderer_font_data_uri(),
        "width": metadata.width, "height": metadata.height,
        "fps": metadata.frame_rate, "durationInFrames": max(1, round(metadata.duration_seconds * metadata.frame_rate)),
    }
    write_remotion_props(props_file, props)

    def render_overlay() -> None:
        _run(remotion_render_command(overlay, props_file), cwd=RENDERER_ROOT, task_id=task_id)
        try:
            verify_overlay_has_alpha(overlay)
        except QualityValidationError as exc:
            raise ProcessingError(f"Animation overlay validation failed: {exc}") from exc

    run_stage("remotion_render", render_overlay)

    def composite() -> None:
        # Keep ASS as a task artifact/export fallback. The visible captions are
        # rendered in Remotion so word-level emphasis and kinetic timing can be
        # synchronized to the same props file as the semantic visual plan.
        write_ass(transcript, subtitles, metadata.width, metadata.height)
        command = [
            "ffmpeg", "-y", "-i", str(source), "-i", str(overlay),
            "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]", "-map", "[v]",
        ]
        if metadata.has_audio:
            command.extend(["-map", "0:a:0?", "-c:a", "aac"])
        command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest", str(result)])
        _run(command, task_id=task_id)
        if not result.is_file() or result.stat().st_size == 0:
            raise ProcessingError("Rendering completed without producing result.mp4")

    run_stage("compositing", composite)

    def check_quality() -> dict:
        try:
            quality = verify_output_quality(result, metadata)
            write_quality_report(safe_dir / "quality.json", quality)
            return asdict(quality)
        except QualityValidationError as exc:
            raise ProcessingError(f"Output quality validation failed: {exc}") from exc

    quality_data = run_stage("quality_check", check_quality)
    return transcript.model_dump(), plan.model_dump(), quality_data
