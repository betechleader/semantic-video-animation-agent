import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import requests
from pydantic import ValidationError

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


class LocalLlmAnimationPlanningProvider:
    """Plan animations through a local OpenAI-compatible chat-completions server."""

    def __init__(self, model: str, base_url: str, timeout_seconds: int = 60) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("PLANNER_BASE_URL must point to a local loopback server")
        if timeout_seconds <= 0:
            raise ValueError("planner timeout must be positive")
        self.model = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _prompt(transcript: Transcript) -> str:
        return """You are a Chinese short-video semantic planner. Return one JSON object only, without Markdown.
Use only the supplied transcript text and timestamps. Do not invent words or times.
The object must match this schema exactly:
{
  "animations": [{"id": "animation_<id>", "type": "keyword_pop", "template_id": "keyword_pop_v1", "start_ms": 0, "end_ms": 1, "trigger_text": "source text", "parameters": {"text": "max 80 chars", "color": "#RRGGBB", "position": "top-left|top-right|bottom-left|bottom-right|center"}}],
  "semantic_segments": [{"id": "semantic_<id>", "text": "source text", "start_ms": 0, "end_ms": 1, "intent": "emphasis|explanation|transition|summary", "keywords": ["source keyword"]}]
}
Return at least one animation. Keep all timestamps within a supplied transcript segment.
For a quote_card use type quote_card, template_id quote_card_v1, and parameters {"headline": "max 48 chars", "body": "max 160 chars", "accent_color": "#RRGGBB"}.
Transcript JSON:
""" + transcript.model_dump_json()

    @staticmethod
    def _extract_json(content: str) -> dict:
        value = content.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1] if "\n" in value else ""
            if value.rstrip().endswith("```"):
                value = value.rstrip()[:-3]
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Local LLM returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Local LLM response must be a JSON object")
        return parsed

    def plan(self, transcript: Transcript) -> AnimationPlan:
        try:
            response = requests.post(
                self.endpoint,
                json={"model": self.model, "messages": [{"role": "user", "content": self._prompt(transcript)}], "temperature": 0.2},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Local LLM planning request failed: {exc}") from exc
        if not isinstance(content, str):
            raise RuntimeError("Local LLM response content must be text")
        try:
            return AnimationPlan.model_validate(self._extract_json(content))
        except (ValidationError, RuntimeError) as exc:
            raise RuntimeError(f"Local LLM returned an invalid animation plan: {exc}") from exc


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
