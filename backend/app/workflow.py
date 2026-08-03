import logging
import threading
from pathlib import Path

from .audio import AudioExtractionError, AudioService
from .config import MODEL_ROOT, SETTINGS
from .database import get_task, transition_task
from .metrics import TaskMetrics, initialize_initial_metrics
from .models import TaskStatus
from .processing import ProcessingCancelled, ProcessingError, render_and_composite
from .providers import FasterWhisperProvider, LocalLlmAnimationPlanningProvider, MockAnimationPlanningProvider, MockSpeechRecognitionProvider, TranscriptAnimationPlanningProvider
from .planning_rules import PlanningRuleError, validate_animation_plan
from .schemas import AnimationPlan, Transcript, VideoMetadata

logger = logging.getLogger("semantic_video")


def process_task(task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str) -> None:
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
        if not metadata.has_audio:
            def missing_audio() -> None:
                raise ProcessingError("Video has no audio track for speech recognition")

            metrics.record_stage(attempt, "audio_extraction", missing_audio)
        audio_path = metrics.record_stage(attempt, "audio_extraction", lambda: AudioService().extract_wav(task_dir / "source.mp4", task_dir / "audio.wav"))
        provider = MockSpeechRecognitionProvider() if SETTINGS.asr_provider == "mock" else FasterWhisperProvider(SETTINGS.asr_model, MODEL_ROOT, SETTINGS.asr_local_files_only)
        transcript = metrics.record_stage(attempt, "asr", lambda: provider.transcribe(audio_path))

        def build_plan() -> AnimationPlan:
            if SETTINGS.planner_provider == "mock":
                planner = MockAnimationPlanningProvider()
            elif SETTINGS.planner_provider == "rule_based":
                planner = TranscriptAnimationPlanningProvider()
            elif SETTINGS.planner_provider == "local_llm":
                planner = LocalLlmAnimationPlanningProvider(
                    SETTINGS.planner_model, SETTINGS.planner_base_url, SETTINGS.planner_timeout_seconds,
                )
            else:
                raise ProcessingError("PLANNER_PROVIDER must be mock, rule_based, or local_llm")
            return validate_animation_plan(planner.plan(transcript), transcript)

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


def start_task(task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str) -> threading.Thread:
    thread = threading.Thread(target=process_task, args=(task_id, task_dir, metadata, trace_id), daemon=True, name=f"video-task-{task_id}")
    thread.start()
    return thread


def rerender_review(task_id: str, task_dir: Path, metadata: VideoMetadata, transcript: Transcript, plan: AnimationPlan, trace_id: str) -> None:
    metrics = TaskMetrics(task_dir, task_id)
    attempt = metrics.current_or_start_attempt("review")
    output_quality: dict | None = None
    try:
        transcript_data, plan_data, output_quality = render_and_composite(
            task_dir, metadata, transcript, plan, task_id=task_id, stage_runner=lambda stage, action: metrics.record_stage(attempt, stage, action),
        )
        transition_task(task_id, TaskStatus.COMPLETED, "Review result video created", transcript=transcript_data, plan=plan_data)
        logger.info("review_task_completed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "completed"})
    except ProcessingCancelled:
        transition_task(task_id, TaskStatus.CANCELLED, "Review rendering cancelled")
    except (ProcessingError, RuntimeError) as exc:
        transition_task(task_id, TaskStatus.FAILED, "Review rendering failed", error=str(exc))
        logger.error("review_task_failed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "failed"})
    finally:
        task = get_task(task_id)
        if task and task["status"] in {"completed", "failed", "cancelled"}:
            failure_category = "cancelled" if task["status"] == "cancelled" else "review_rendering"
            metrics.finalize(attempt, task["status"], failure_category=failure_category, output_quality=output_quality)


def start_review_task(task_id: str, task_dir: Path, metadata: VideoMetadata, transcript: Transcript, plan: AnimationPlan, trace_id: str) -> threading.Thread:
    thread = threading.Thread(
        target=rerender_review,
        args=(task_id, task_dir, metadata, transcript, plan, trace_id),
        daemon=True,
        name=f"review-video-task-{task_id}",
    )
    thread.start()
    return thread
