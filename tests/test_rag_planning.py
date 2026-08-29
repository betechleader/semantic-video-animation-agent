import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import agent_workflow, database, main
from backend.app.agent_trace import read_agent_trace
from backend.app.agent_tools import PlanningToolInput
from backend.app.agent_workflow import AgentCheckpointStore, AgentWorkflowServices
from backend.app.config import SETTINGS
from backend.app.knowledge_base import KnowledgeBaseService, LocalHashEmbeddingProvider
from backend.app.models import TaskStatus
from backend.app.planning_rules import validate_animation_plan
from backend.app.rag_tools import (
    EvidenceValidationError,
    RetrieveEvidenceInput,
    RetrieveEvidenceOutput,
    build_evidence_queries,
    evidence_status,
    ground_candidate_with_evidence,
    invoke_retrieve_evidence_tool,
    validate_evidence_citations,
)
from backend.app.schemas import AnimationPlan, Transcript, TranscriptSegment, WordTiming
from backend.app.workflow_services import plan_agent_candidate
from tests.test_agent_workflow import (
    RecordingServices,
    _create_task,
    _metadata,
    isolated_database,
)


def _configure_database(tmp_path: Path, monkeypatch) -> Path:
    storage = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    return storage / "knowledge"


def _settings():
    return replace(
        SETTINGS,
        knowledge_max_file_mb=1,
        knowledge_chunk_chars=120,
        knowledge_chunk_overlap_chars=20,
        knowledge_embedding_provider="local_hash",
    )


def _book_transcript() -> Transcript:
    return Transcript(
        language="zh",
        full_text="阅读心理学与生活可以帮助我们理解行为",
        segments=[
            TranscriptSegment(
                text="阅读心理学与生活可以帮助我们理解行为",
                start_ms=1_000,
                end_ms=5_000,
                words=[
                    WordTiming(text="阅读心理学与生活", start_ms=1_000, end_ms=3_000),
                    WordTiming(text="可以帮助我们理解行为", start_ms=3_000, end_ms=5_000),
                ],
            )
        ],
    )


def _book_candidate() -> dict:
    return {
        "media_provider": "mock",
        "animations": [
            {
                "id": "animation_book",
                "type": "media_visual",
                "template_id": "media_visual_v1",
                "start_ms": 1_000,
                "end_ms": 3_000,
                "trigger_text": "阅读心理学与生活",
                "parameters": {
                    "asset_id": "media_book",
                    "title": "心理学与生活",
                    "theme": "book",
                    "accent_color": "#FFD400",
                    "search_query": "Psychology and Life",
                    "desired_asset_kind": "external_image",
                    "display_mode": "side_card",
                },
            }
        ],
    }


def test_typed_retrieval_cites_current_chunks_and_deletion_invalidates_plan(
    tmp_path: Path, monkeypatch
) -> None:
    root = _configure_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=_settings(),
        embedding_provider=LocalHashEmbeddingProvider(),
    )
    document = service.import_document(
        "psychology.md",
        "《心理学与生活》介绍心理学研究如何解释人的行为。".encode(),
        {"topic": "book"},
    )
    transcript = _book_transcript()
    tool_input = RetrieveEvidenceInput(queries=build_evidence_queries(transcript))
    retrieved = invoke_retrieve_evidence_tool(tool_input, service.search)

    assert retrieved.evidence
    assert retrieved.queries[0].query_sha256
    service_candidate = plan_agent_candidate(
        PlanningToolInput(
            transcript=transcript,
            repair_attempt=0,
            evidence=retrieved.evidence,
        ),
        processing_profile="real",
        media_provider="mock",
    )
    assert service_candidate.candidate is not None
    assert service_candidate.candidate["animations"][0]["evidence_ids"]
    grounded = AnimationPlan.model_validate(
        ground_candidate_with_evidence(_book_candidate(), retrieved.evidence)
    )
    validate_animation_plan(grounded, transcript)
    assert grounded.animations[0].evidence_ids == [grounded.evidence[0].chunk_id]
    assert grounded.animations[0].confidence is not None
    assert grounded.animations[0].selection_reason == "project_knowledge_support"
    assert evidence_status(grounded, service)["valid"] is True
    assert validate_evidence_citations(grounded, service) == grounded

    forged_payload = grounded.model_dump()
    forged_payload["evidence"][0]["excerpt"] = "伪造但哈希字段未变的证据摘录"
    with pytest.raises(EvidenceValidationError, match="excerpt does not match"):
        validate_evidence_citations(
            AnimationPlan.model_validate(forged_payload),
            service,
        )

    service.delete_document(document["document_id"])
    status = evidence_status(grounded, service)
    assert status["valid"] is False
    assert status["items"][0]["status"] == "missing"
    with pytest.raises(EvidenceValidationError, match="missing from the current index"):
        validate_evidence_citations(grounded, service)


def test_no_evidence_downgrades_factual_visual_and_rejects_forged_knowledge_card(
    tmp_path: Path, monkeypatch
) -> None:
    root = _configure_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(root=root, settings=_settings())
    transcript = _book_transcript()

    safe = AnimationPlan.model_validate(
        ground_candidate_with_evidence(_book_candidate(), [])
    )
    assert safe.animations[0].type == "keyword_pop"
    assert safe.animations[0].evidence_ids == []
    assert safe.animations[0].selection_reason == "fact_safe_transcript_emphasis_no_evidence"
    validate_evidence_citations(safe, service)

    forged = AnimationPlan.model_validate(
        {
            "animations": [
                {
                    "id": "animation_forged",
                    "type": "info_graphic",
                    "template_id": "knowledge_infographic_v1",
                    "start_ms": 1_000,
                    "end_ms": 3_000,
                    "trigger_text": "阅读心理学与生活",
                    "parameters": {
                        "variant": "comparison",
                        "headline": "人物关系",
                        "items": ["作者", "读者"],
                        "accent_color": "#FFD400",
                    },
                }
            ]
        }
    )
    with pytest.raises(EvidenceValidationError, match="without project evidence"):
        validate_evidence_citations(forged, service)
    forged_status = evidence_status(forged, service)
    assert forged_status["valid"] is False
    assert "without project evidence" in forged_status["violations"][0]


def test_agent_checkpoint_and_trace_record_private_retrieval_summary(
    isolated_database: Path,
) -> None:
    task_id = "agent-rag-trace"
    task_dir = _create_task(isolated_database, task_id)
    recording = RecordingServices()
    base = recording.bundle()

    def retrieve(tool_input: RetrieveEvidenceInput) -> RetrieveEvidenceOutput:
        assert tool_input.queries[0].text == "初稿"
        return invoke_retrieve_evidence_tool(
            tool_input,
            lambda _query, **_kwargs: {
                "results": [],
            },
        )

    services = AgentWorkflowServices(
        extract_audio=base.extract_audio,
        transcribe_audio=base.transcribe_audio,
        correct_asr_transcript=base.correct_asr_transcript,
        build_animation_plan=base.build_animation_plan,
        retrieve_evidence=retrieve,
        validate_plan=base.validate_plan,
        render_and_composite_video=base.render_and_composite_video,
        verify_and_write_output_quality=base.verify_and_write_output_quality,
    )
    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=services,
        checkpoint_store=AgentCheckpointStore.for_storage_root(isolated_database),
    )

    assert checkpoint["state"]["schema_version"] == 3
    assert checkpoint["state"]["evidence_queries"][0]["query_sha256"]
    trace = read_agent_trace(task_dir, task_id)
    retrieval = next(
        entry for entry in trace["entries"]
        if entry.get("tool_name") == "retrieve_evidence"
    )
    assert retrieval["output_summary"]["retrieved_count"] == 0
    encoded = json.dumps(trace, ensure_ascii=False)
    assert "初稿" not in encoded
    assert "query_sha256" in encoded


def test_evidence_api_shows_live_status_for_agent_review(
    tmp_path: Path, monkeypatch
) -> None:
    root = _configure_database(tmp_path, monkeypatch)
    service = KnowledgeBaseService(
        root=root,
        settings=_settings(),
        embedding_provider=LocalHashEmbeddingProvider(),
    )
    document = service.import_document(
        "psychology.txt",
        "心理学与生活介绍心理学研究与人的行为。".encode(),
    )
    transcript = _book_transcript()
    retrieved = invoke_retrieve_evidence_tool(
        RetrieveEvidenceInput(queries=build_evidence_queries(transcript)),
        service.search,
    )
    plan = AnimationPlan.model_validate(
        ground_candidate_with_evidence(_book_candidate(), retrieved.evidence)
    )
    task_id = "77777777-7777-4777-8777-777777777777"
    database.create_task(
        task_id,
        _metadata().model_dump(),
        "trace-rag-api",
        workflow_mode="agent",
        processing_profile="mock",
        media_provider="mock",
    )
    assert database.transition_task(
        task_id,
        TaskStatus.COMPLETED,
        "completed",
        transcript=transcript.model_dump(),
        plan=plan.model_dump(),
    )
    monkeypatch.setattr(main, "_knowledge_service", lambda: service)

    with TestClient(main.app) as client:
        current = client.get(f"/api/videos/{task_id}/evidence")
        assert current.status_code == 200
        assert current.json()["valid"] is True
        assert current.json()["items"][0]["source"] == "psychology.txt"
        service.delete_document(document["document_id"])
        stale = client.get(f"/api/videos/{task_id}/evidence")
        assert stale.status_code == 200
        assert stale.json()["valid"] is False
        assert stale.json()["items"][0]["status"] == "missing"
