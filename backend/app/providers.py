from pathlib import Path
from typing import Protocol

from .mock_services import create_mock_plan, create_mock_transcript
from .schemas import AnimationPlan, Transcript


class SpeechRecognitionProvider(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript: ...


class AnimationPlanningProvider(Protocol):
    def plan(self, transcript: Transcript) -> AnimationPlan: ...


class MockSpeechRecognitionProvider:
    def transcribe(self, _audio_path: Path) -> Transcript:
        return create_mock_transcript()


class MockAnimationPlanningProvider:
    def plan(self, transcript: Transcript) -> AnimationPlan:
        return create_mock_plan(transcript)


class FasterWhisperProvider:
    def __init__(self, model_name: str, model_dir: Path, local_files_only: bool = True) -> None:
        self.model_name = model_name
        self.model_dir = model_dir
        self.local_files_only = local_files_only

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed; keep ASR_PROVIDER=mock or install the optional dependency") from exc
        self.model_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(self.model_name, device="cpu", compute_type="int8", download_root=str(self.model_dir), local_files_only=self.local_files_only)
        segments, info = model.transcribe(str(audio_path), language="zh", word_timestamps=True)
        converted = []
        for segment in segments:
            words = [
                {
                    "text": word.word.strip(),
                    "start_ms": max(0, round(word.start * 1000)),
                    # Faster-whisper timestamps have sub-millisecond precision. Preserve a
                    # valid interval when rounding collapses a very short word to one ms.
                    "end_ms": max(max(0, round(word.start * 1000)) + 1, round(word.end * 1000)),
                }
                for word in (segment.words or []) if word.start is not None and word.end is not None and word.word.strip()
            ]
            if words:
                start_ms = max(0, round(segment.start * 1000))
                converted.append({"text": segment.text.strip(), "start_ms": start_ms, "end_ms": max(start_ms + 1, round(segment.end * 1000)), "words": words})
        if not converted:
            raise RuntimeError("faster-whisper returned no word timestamps")
        return Transcript(language=info.language or "zh", language_confidence=getattr(info, "language_probability", None), full_text="".join(item["text"] for item in converted), segments=converted)
