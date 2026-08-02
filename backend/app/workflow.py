import logging
import threading
from pathlib import Path

from .audio import AudioExtractionError, AudioService
from .config import MODEL_ROOT, SETTINGS
from .database import transition_task
from .models import TaskStatus
from .processing import ProcessingCancelled, ProcessingError, render_and_composite
from .providers import FasterWhisperProvider, MockAnimationPlanningProvider, MockSpeechRecognitionProvider
from .schemas import VideoMetadata

logger = logging.getLogger("semantic_video")


def process_task(task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str) -> None:
    try:
        if not transition_task(task_id, TaskStatus.PROCESSING, "Extracting audio and transcribing speech"):
            return
        if not metadata.has_audio:
            raise ProcessingError("Video has no audio track for speech recognition")
        audio_path = AudioService().extract_wav(task_dir / "source.mp4", task_dir / "audio.wav")
        provider = MockSpeechRecognitionProvider() if SETTINGS.asr_provider == "mock" else FasterWhisperProvider(SETTINGS.asr_model, MODEL_ROOT)
        transcript = provider.transcribe(audio_path)
        plan = MockAnimationPlanningProvider().plan(transcript)
        if not transition_task(task_id, TaskStatus.RENDERING, "Rendering animation and compositing video"):
            return
        transcript, plan = render_and_composite(task_dir, metadata, transcript, plan, task_id=task_id)
        transition_task(task_id, TaskStatus.COMPLETED, "Result video created", transcript=transcript, plan=plan)
        logger.info("task_completed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "completed"})
    except ProcessingCancelled:
        transition_task(task_id, TaskStatus.CANCELLED, "External rendering process cancelled")
        logger.info("task_cancelled", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "cancelled"})
    except (ProcessingError, AudioExtractionError, RuntimeError) as exc:
        transition_task(task_id, TaskStatus.FAILED, "Rendering failed", error=str(exc))
        logger.error("task_failed", extra={"task_id": task_id, "trace_id": trace_id, "event_type": "failed"})


def start_task(task_id: str, task_dir: Path, metadata: VideoMetadata, trace_id: str) -> threading.Thread:
    thread = threading.Thread(target=process_task, args=(task_id, task_dir, metadata, trace_id), daemon=True, name=f"video-task-{task_id}")
    thread.start()
    return thread
