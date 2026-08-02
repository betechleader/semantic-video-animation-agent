from typing import Protocol

from .mock_services import create_mock_plan, create_mock_transcript
from .schemas import AnimationPlan, Transcript


class SpeechRecognitionProvider(Protocol):
    def transcribe(self) -> Transcript: ...


class AnimationPlanningProvider(Protocol):
    def plan(self, transcript: Transcript) -> AnimationPlan: ...


class MockSpeechRecognitionProvider:
    def transcribe(self) -> Transcript:
        return create_mock_transcript()


class MockAnimationPlanningProvider:
    def plan(self, transcript: Transcript) -> AnimationPlan:
        return create_mock_plan(transcript)
