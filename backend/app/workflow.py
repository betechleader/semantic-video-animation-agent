import logging
import threading
from pathlib import Path

from .audio import AudioExtractionError, AudioService
from .database import finish_plan_patch, get_task, transition_task
from .metrics import TaskMetrics, initialize_initial_metrics
from .models import TaskStatus
from .processing import ProcessingCancelled, ProcessingError, render_and_composite
from .providers import FasterWhisperProvider, LocalLlmAnimationPlanningProvider, MockAnimationPlanningProvider, MockSpeechRecognitionProvider, TranscriptAnimationPlanningProvider
from .planning_rules import PlanningRuleError, validate_animation_plan
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .workflow_services import build_animation_plan, correct_asr_transcript, extract_audio, transcribe_audio, validate_plan

logger = logging.getLogger("semantic_video")


def process_task(
    task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str,
    processing_profile: str = "configured", media_provider: str | None = None,
) -> None:
    metrics = TaskMetrics(task_dir, task_id)
    try:
        attempt = metrics.current_or_start_attempt("initial")
    except RuntimeError:
        # Keeps direct service invocation usable in tests and maintenance jobs.
        metrics = initialize_initial_metrics(task_dir, task_id, trace_id, 0)
        attempt = 1
    output_quality: dict | None = None
    try:
        if not transition_task(task_id, TaskStatus.PROCESSING, "Extracting audio and transcribing speech"):
            return
        audio_path = metrics.record_stage(
            attempt,
            "audio_extraction",
            lambda: extract_audio(task_dir, metadata),
        )
        transcript = metrics.record_stage(
            attempt,
            "asr",
            lambda: transcribe_audio(audio_path, processing_profile),
        )
        transcript = metrics.record_stage(
            attempt,
            "asr_correction",
            lambda: correct_asr_transcript(transcript),
        )

        def build_plan() -> AnimationPlan:
            planned = build_animation_plan(transcript, processing_profile, media_provider)
            return validate_plan(planned, transcript)

        # Providers validate their normal outputs, and the workflow validates again
        # at the trust boundary before an untrusted plan can reach the renderer.
        plan = metrics.record_stage(attempt, "planning", build_plan)
        if not transition_task(task_id, TaskStatus.RENDERING, "Rendering animation and compositing video"):
            return
        transcript, plan, output_quality = render_and_composite(
            task_dir, metadata, transcript, plan, task_id=task_id, stage_runner=lambda stage, action: metrics.record_stage(attempt, stage, action),
        )
        transition_task(task_id, TaskStatus.COMPLETED, "Result video created", transcript=transcript, plan=plan)
        logger.info("task_completed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "completed"})
    except ProcessingCancelled:
        transition_task(task_id, TaskStatus.CANCELLED, "External rendering process cancelled")
        logger.info("task_cancelled", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "cancelled"})
    except (ProcessingError, AudioExtractionError, PlanningRuleError, RuntimeError) as exc:
        transition_task(task_id, TaskStatus.FAILED, "Rendering failed", error=str(exc))
        logger.error("task_failed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "failed"})
    finally:
        task = get_task(task_id)
        if task and task["status"] in {"completed", "failed", "cancelled"}:
            failure_category = "cancelled" if task["status"] == "cancelled" else None
            metrics.finalize(attempt, task["status"], failure_category=failure_category, output_quality=output_quality)


def start_task(
    task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str,
    processing_profile: str = "configured", media_provider: str | None = None,
) -> threading.Thread:
    thread = threading.Thread(
        target=process_task,
        args=(task_id, task_dir, metadata, trace_id, processing_profile, media_provider),
        daemon=True, name=f"video-task-{task_id}",
    )
    thread.start()
    return thread


def rerender_review(task_id: str, task_dir: Path, metadata: VideoMetadata, transcript: Transcript, plan: AnimationPlan, trace_id: str, patch_id: str | None = None) -> None:
    metrics = TaskMetrics(task_dir, task_id)
    attempt = metrics.current_or_start_attempt("review")
    output_quality: dict | None = None
    try:
        transcript_data, plan_data, output_quality = render_and_composite(
            task_dir, metadata, transcript, plan, task_id=task_id, stage_runner=lambda stage, action: metrics.record_stage(attempt, stage, action),
        )
        transition_task(task_id, TaskStatus.COMPLETED, "Review result video created", transcript=transcript_data, plan=plan_data)
        if patch_id:
            finish_plan_patch(task_id, patch_id, True)
        logger.info("review_task_completed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "completed"})
    except ProcessingCancelled:
        transition_task(task_id, TaskStatus.CANCELLED, "Review rendering cancelled")
        if patch_id:
            finish_plan_patch(task_id, patch_id, False)
    except (ProcessingError, RuntimeError) as exc:
        transition_task(task_id, TaskStatus.FAILED, "Review rendering failed", error=str(exc))
        if patch_id:
            finish_plan_patch(task_id, patch_id, False)
        logger.error("review_task_failed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "failed"})
    finally:
        task = get_task(task_id)
        if task and task["status"] in {"completed", "failed", "cancelled"}:
            failure_category = "cancelled" if task["status"] == "cancelled" else "review_rendering"
            metrics.finalize(attempt, task["status"], failure_category=failure_category, output_quality=output_quality)


def start_review_task(task_id: str, task_dir: Path, metadata: VideoMetadata, transcript: Transcript, plan: AnimationPlan, trace_id: str, patch_id: str | None = None) -> threading.Thread:
    thread = threading.Thread(
        target=rerender_review,
        args=(task_id, task_dir, metadata, transcript, plan, trace_id, patch_id),
        daemon=True,
        name=f"review-video-task-{task_id}",
    )
    thread.start()
    return thread
