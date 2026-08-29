"""Reusable processing services shared by standard and agent workflows."""

from pathlib import Path

from .audio import AudioService
from .asr_corrections import correct_transcript, load_phrase_corrections
from .config import KNOWLEDGE_ROOT, MODEL_ROOT, SETTINGS
from .knowledge_base import KnowledgeBaseService
from .processing import ProcessingError
from .providers import (
    AnimationPlanningProvider,
    DeepSeekAnimationPlanningProvider,
    FasterWhisperProvider,
    LocalLlmAnimationPlanningProvider,
    MockAnimationPlanningProvider,
    MockSpeechRecognitionProvider,
    SpeechRecognitionProvider,
    TranscriptAnimationPlanningProvider,
)
from .planning_rules import validate_animation_plan
from .schemas import AnimationPlan, Transcript, VideoMetadata
from .agent_tools import PlanningToolInput, PlanningToolOutput, invoke_planning_tool
from .rag_tools import (
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    ground_candidate_with_evidence,
    invoke_retrieve_evidence_tool,
    validate_evidence_citations,
)


def resolve_asr_provider(processing_profile: str = "configured") -> SpeechRecognitionProvider:
    """Resolve the existing profile/configuration pair to an ASR provider."""

    asr_name = (
        "faster_whisper"
        if processing_profile == "real"
        else "mock"
        if processing_profile == "mock"
        else SETTINGS.asr_provider
    )
    if asr_name == "mock":
        return MockSpeechRecognitionProvider()
    return FasterWhisperProvider(
        SETTINGS.asr_model,
        MODEL_ROOT,
        SETTINGS.asr_local_files_only,
    )


def resolve_planning_provider(processing_profile: str = "configured") -> AnimationPlanningProvider:
    """Resolve the existing profile/configuration pair to a planning provider."""

    planner_name = (
        "rule_based"
        if processing_profile == "real"
        else "mock"
        if processing_profile == "mock"
        else SETTINGS.planner_provider
    )
    if planner_name == "mock":
        return MockAnimationPlanningProvider()
    if planner_name == "rule_based":
        return TranscriptAnimationPlanningProvider()
    if planner_name == "local_llm":
        return LocalLlmAnimationPlanningProvider(
            SETTINGS.planner_model,
            SETTINGS.planner_base_url,
            SETTINGS.planner_timeout_seconds,
        )
    if planner_name == "deepseek":
        return DeepSeekAnimationPlanningProvider(
            SETTINGS.deepseek_model,
            SETTINGS.planner_timeout_seconds,
        )
    raise ProcessingError(
        "PLANNER_PROVIDER must be mock, rule_based, local_llm, or deepseek"
    )


def extract_audio(task_dir: Path, metadata: VideoMetadata) -> Path:
    """Extract the task source audio into the stable task-local WAV path."""

    if not metadata.has_audio:
        raise ProcessingError("Video has no audio track for speech recognition")
    return AudioService().extract_wav(task_dir / "source.mp4", task_dir / "audio.wav")


def transcribe_audio(audio_path: Path, processing_profile: str = "configured") -> Transcript:
    """Transcribe an extracted WAV with the configured/profile ASR provider."""

    return resolve_asr_provider(processing_profile).transcribe(audio_path)


def correct_asr_transcript(transcript: Transcript) -> Transcript:
    """Apply the configured deterministic phrase corrections to ASR output."""

    rules = load_phrase_corrections(SETTINGS.asr_correction_dictionary_path)
    return correct_transcript(transcript, rules)


def build_animation_plan(
    transcript: Transcript,
    processing_profile: str = "configured",
    media_provider: str | None = None,
) -> AnimationPlan:
    """Build a plan without bypassing the caller's explicit validation node."""

    planner = resolve_planning_provider(processing_profile)
    plan = planner.plan(transcript)
    selected_media_provider = media_provider or SETTINGS.media_provider
    return plan.model_copy(update={"media_provider": selected_media_provider})


def plan_agent_candidate(
    tool_input: PlanningToolInput,
    processing_profile: str = "configured",
    media_provider: str | None = None,
) -> PlanningToolOutput:
    """Invoke the configured planner through the Agent's typed tool boundary."""

    planner = resolve_planning_provider(processing_profile)
    selected_media_provider = media_provider or SETTINGS.media_provider
    planner_id = (
        "mock"
        if isinstance(planner, MockAnimationPlanningProvider)
        else "rule_based"
        if isinstance(planner, TranscriptAnimationPlanningProvider)
        else "deepseek"
        if isinstance(planner, DeepSeekAnimationPlanningProvider)
        else "local_llm"
    )
    model_id = (
        planner.model
        if isinstance(
            planner,
            (LocalLlmAnimationPlanningProvider, DeepSeekAnimationPlanningProvider),
        )
        else None
    )

    def generate(value: PlanningToolInput):
        if isinstance(
            planner,
            (LocalLlmAnimationPlanningProvider, DeepSeekAnimationPlanningProvider),
        ):
            candidate = planner.plan_candidate(
                value.transcript,
                director_instruction=value.director_instruction,
                violations=[item.model_dump() for item in value.violations],
                repair_attempt=value.repair_attempt,
                evidence=[item.model_dump() for item in value.evidence],
            )
        else:
            candidate = planner.plan(value.transcript)
        if isinstance(candidate, AnimationPlan):
            candidate = candidate.model_dump()
        candidate = {**candidate, "media_provider": selected_media_provider}
        return ground_candidate_with_evidence(candidate, value.evidence)

    return invoke_planning_tool(
        tool_input,
        generate,
        planner_id=planner_id,
        model_id=model_id,
    )


def validate_plan(plan: AnimationPlan, transcript: Transcript) -> AnimationPlan:
    """Validate a planner result at the workflow-to-renderer trust boundary."""

    return validate_animation_plan(plan, transcript)


def retrieve_agent_evidence(tool_input: RetrieveEvidenceInput) -> RetrieveEvidenceOutput:
    """Search the project-local knowledge index through the typed RAG boundary."""

    service = KnowledgeBaseService(root=KNOWLEDGE_ROOT, settings=SETTINGS)
    return invoke_retrieve_evidence_tool(tool_input, service.search)


def validate_agent_plan_evidence(plan: AnimationPlan) -> AnimationPlan:
    """Re-resolve citations against the current project knowledge index."""

    return validate_evidence_citations(
        plan,
        KnowledgeBaseService(root=KNOWLEDGE_ROOT, settings=SETTINGS),
    )
