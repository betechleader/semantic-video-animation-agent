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


class RawAsrTranscript(BaseModel):
    """Immutable ASR provider output retained for reviewer comparison."""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=2, max_length=16)
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    full_text: str = Field(min_length=1)
    segments: list[TranscriptSegment] = Field(min_length=1)


class TranscriptCorrection(BaseModel):
    """A text correction tied only to an interval already emitted by ASR."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    segment_index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    kind: Literal["dictionary", "manual"] = "dictionary"

    @model_validator(mode="after")
    def validate_time_range(self) -> "TranscriptCorrection":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class Transcript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str = Field(min_length=2, max_length=16)
    language_confidence: float | None = Field(default=None, ge=0, le=1)
    full_text: str = Field(min_length=1)
    segments: list[TranscriptSegment] = Field(min_length=1)
    raw_asr: RawAsrTranscript | None = None
    corrections: list[TranscriptCorrection] = Field(default_factory=list)


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


class MediaVisualParameters(BaseModel):
    """A task-local visual chosen from a recorded search candidate or generated locally."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^media_[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=48)
    theme: Literal["book", "factory", "product", "money", "learning", "people", "place", "concept", "wellbeing", "business", "technology"]
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    search_query: str = Field(default="knowledge concept", min_length=1, max_length=120)
    desired_asset_kind: Literal["external_image", "external_video"] = "external_image"
    display_mode: Literal["side_card", "full_screen"] = "side_card"
    selected_candidate_id: str | None = Field(default=None, pattern=r"^candidate_[A-Za-z0-9_-]+$")
    enabled: bool = True


class InformationGraphicParameters(BaseModel):
    """Transcript-grounded original visual for a list, contrast, or flow idea."""

    model_config = ConfigDict(extra="forbid")

    variant: Literal["number_list", "comparison", "flow"]
    headline: str = Field(min_length=1, max_length=48)
    items: list[str] = Field(min_length=1, max_length=4)
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_item_count(self) -> "InformationGraphicParameters":
        if self.variant in {"comparison", "flow"} and len(self.items) < 2:
            raise ValueError(f"{self.variant} information graphics require at least two items")
        return self


class MediaAssetAudit(BaseModel):
    """Task-local provenance for a generated or external prototype media asset."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^media_[A-Za-z0-9_-]+$")
    provider: str = Field(default="legacy_local", min_length=1, max_length=80)
    search_query: str = Field(default="legacy visual", min_length=1, max_length=120)
    source_url: str | None = Field(default=None, max_length=2_000)
    source_page_url: str | None = Field(default=None, max_length=2_000)
    author_or_provider: str = Field(min_length=1, max_length=160)
    license: str = Field(min_length=1, max_length=240)
    usage_conditions: str = Field(min_length=1, max_length=600)
    acquired_at: str = Field(min_length=20, max_length=40)
    candidate_id: str | None = Field(default=None, pattern=r"^candidate_[A-Za-z0-9_-]+$")
    local_path: str = Field(min_length=1, max_length=320)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_kind: Literal["generated_original", "generated_infographic", "external_image", "external_video"]
    mime_type: str = Field(default="image/svg+xml", min_length=1, max_length=120)
    usage_start_ms: int = Field(default=0, ge=0)
    usage_end_ms: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_usage_range(self) -> "MediaAssetAudit":
        if self.usage_end_ms <= self.usage_start_ms:
            raise ValueError("usage_end_ms must be greater than usage_start_ms")
        return self


class MediaCandidate(BaseModel):
    """A search result stored in the task-local review candidate manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^candidate_[A-Za-z0-9_-]+$")
    provider: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=120)
    asset_kind: Literal["external_image", "external_video"]
    source_url: str = Field(min_length=8, max_length=2_000)
    source_page_url: str | None = Field(default=None, max_length=2_000)
    title: str = Field(min_length=1, max_length=240)
    author_or_provider: str = Field(min_length=1, max_length=160)
    license: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(min_length=1, max_length=120)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: float | None = Field(default=None, gt=0)


class MediaSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=120)
    asset_kind: Literal["external_image", "external_video"] = "external_image"


class ManualMediaCandidateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=120)
    source_url: str = Field(pattern=r"^https?://", max_length=2_000)
    source_page_url: str | None = Field(default=None, pattern=r"^https?://", max_length=2_000)
    title: str = Field(min_length=1, max_length=240)
    author_or_provider: str = Field(default="manual reviewer", min_length=1, max_length=160)
    license: str = Field(default="Unverified external material (prototype only)", min_length=1, max_length=240)
    mime_type: str = Field(default="image/jpeg", min_length=1, max_length=120)
    asset_kind: Literal["external_image", "external_video"] = "external_image"
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    duration_seconds: float | None = Field(default=None, gt=0)


class FaceRegion(BaseModel):
    """A non-biometric, timestamped face bounding box in source-video pixels."""

    model_config = ConfigDict(extra="forbid")

    timestamp_ms: int = Field(ge=0)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class MediaPlacement(BaseModel):
    """Renderer layout chosen locally after face and subtitle safe-area analysis."""

    model_config = ConfigDict(extra="forbid")

    animation_id: str = Field(pattern=r"^animation_[A-Za-z0-9_-]+$")
    corner: Literal["top-left", "top-right", "bottom-left", "bottom-right"] | None = None
    scale: float = Field(ge=0, le=1)
    skipped: bool
    reason: Literal["safe_corner", "no_safe_area", "full_screen"]

    @model_validator(mode="after")
    def validate_skip_state(self) -> "MediaPlacement":
        if self.skipped and (self.corner is not None or self.scale != 0):
            raise ValueError("skipped media placements must have no corner and zero scale")
        if not self.skipped and self.reason == "full_screen" and (self.corner is not None or self.scale != 1):
            raise ValueError("full-screen media placements must have no corner and scale one")
        if not self.skipped and self.reason != "full_screen" and (self.corner is None or self.scale == 0):
            raise ValueError("visible media placements must have a corner and positive scale")
        return self


class EvidenceReference(BaseModel):
    """A versioned project-knowledge chunk cited by one or more animations."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(pattern=r"^chunk_[0-9a-f]{32}$")
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{24}$")
    source: str = Field(min_length=1, max_length=255)
    excerpt: str = Field(min_length=1, max_length=1_200)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score: float = Field(ge=0, le=1)
    retrieval_method: Literal["keyword", "vector", "hybrid"]
    index_version: str = Field(min_length=1, max_length=80)


class Animation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^animation_[A-Za-z0-9_-]+$")
    type: Literal["keyword_pop", "quote_card", "media_visual", "info_graphic"]
    template_id: Literal["keyword_pop_v1", "quote_card_v1", "media_visual_v1", "knowledge_infographic_v1"]
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    trigger_text: str = Field(min_length=1)
    parameters: KeywordPopParameters | QuoteCardParameters | MediaVisualParameters | InformationGraphicParameters
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    confidence: float | None = Field(default=None, ge=0, le=1)
    selection_reason: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def validate_time_range(self) -> "Animation":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if self.type == "keyword_pop" and (self.template_id != "keyword_pop_v1" or not isinstance(self.parameters, KeywordPopParameters)):
            raise ValueError("keyword_pop requires keyword_pop_v1 parameters")
        if self.type == "quote_card" and (self.template_id != "quote_card_v1" or not isinstance(self.parameters, QuoteCardParameters)):
            raise ValueError("quote_card requires quote_card_v1 parameters")
        if self.type == "media_visual" and (self.template_id != "media_visual_v1" or not isinstance(self.parameters, MediaVisualParameters)):
            raise ValueError("media_visual requires media_visual_v1 parameters")
        if self.type == "info_graphic" and (self.template_id != "knowledge_infographic_v1" or not isinstance(self.parameters, InformationGraphicParameters)):
            raise ValueError("info_graphic requires knowledge_infographic_v1 parameters")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("animation evidence_ids must be unique")
        if self.evidence_ids and (self.confidence is None or self.selection_reason is None):
            raise ValueError("cited animations require confidence and selection_reason")
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

    media_provider: Literal["mock", "manual", "knowledge", "wikimedia_commons", "pexels"] = "mock"
    animations: list[Animation] = Field(min_length=1)
    semantic_segments: list[SemanticSegment] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=50)
    media_assets: list[MediaAssetAudit] = Field(default_factory=list)
    face_regions: list[FaceRegion] = Field(default_factory=list)
    media_placements: list[MediaPlacement] = Field(default_factory=list)


class ReviewUpdate(BaseModel):
    """User-approved transcript and plan submitted for a review re-render."""

    model_config = ConfigDict(extra="forbid")

    transcript: Transcript
    plan: AnimationPlan


class AgentApprovalEdit(BaseModel):
    """A reviewer-provided replacement plan for a paused Agent run."""

    model_config = ConfigDict(extra="forbid")

    plan: AnimationPlan


class KnowledgeSearchRequest(BaseModel):
    """A bounded project-knowledge retrieval request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    method: Literal["keyword", "vector", "hybrid"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=20)
    rerank: bool = False
