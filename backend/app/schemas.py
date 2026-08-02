from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_rate: float = Field(gt=0)
    video_codec: str
    audio_codec: str | None = None
    has_video: bool
    has_audio: bool


class WordTiming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> "WordTiming":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    words: list[WordTiming] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TranscriptSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=2, max_length=16)
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    full_text: str = Field(min_length=1)
    segments: list[TranscriptSegment] = Field(min_length=1)


class KeywordPopParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    position: Literal["top-left", "top-right", "bottom-left", "bottom-right", "center"]


class QuoteCardParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str = Field(min_length=1, max_length=48)
    body: str = Field(min_length=1, max_length=160)
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class Animation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^animation_[A-Za-z0-9_-]+$")
    type: Literal["keyword_pop", "quote_card"]
    template_id: Literal["keyword_pop_v1", "quote_card_v1"]
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    trigger_text: str = Field(min_length=1)
    parameters: KeywordPopParameters | QuoteCardParameters

    @model_validator(mode="after")
    def validate_time_range(self) -> "Animation":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if self.type == "keyword_pop" and (self.template_id != "keyword_pop_v1" or not isinstance(self.parameters, KeywordPopParameters)):
            raise ValueError("keyword_pop requires keyword_pop_v1 parameters")
        if self.type == "quote_card" and (self.template_id != "quote_card_v1" or not isinstance(self.parameters, QuoteCardParameters)):
            raise ValueError("quote_card requires quote_card_v1 parameters")
        return self


class SemanticSegment(BaseModel):
    """A local-LLM interpretation anchored to one or more transcript intervals."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^semantic_[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=240)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    intent: Literal["emphasis", "explanation", "transition", "summary"]
    keywords: list[str] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_time_range(self) -> "SemanticSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class AnimationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    animations: list[Animation] = Field(min_length=1)
    semantic_segments: list[SemanticSegment] = Field(default_factory=list)


class ReviewUpdate(BaseModel):
    """User-approved transcript and plan submitted for a review re-render."""

    model_config = ConfigDict(extra="forbid")

    transcript: Transcript
    plan: AnimationPlan
