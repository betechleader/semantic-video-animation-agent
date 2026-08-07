import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app import storage
from backend.app.mock_services import create_mock_transcript
from backend.app.schemas import Transcript
from backend.app.providers import MockAnimationPlanningProvider, MockSpeechRecognitionProvider, TranscriptAnimationPlanningProvider


def test_storage_cleanup_only_removes_expired_uuid_task_directories(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path / "storage")
    service = storage.StorageService()
    expired_id = str(uuid4())
    recent_id = str(uuid4())
    expired = service.create_task_directory(expired_id)
    service.create_task_directory(recent_id)
    os.utime(expired, (1, 1))

    removed = service.cleanup_expired_tasks(retention_hours=1, now=datetime.now(timezone.utc))
    assert removed == [expired_id]
    assert not expired.exists()
    assert service.task_directory(recent_id).exists()


def test_mock_provider_interfaces_produce_valid_plan(tmp_path) -> None:
    transcript = MockSpeechRecognitionProvider().transcribe(tmp_path / "audio.wav")
    plan = MockAnimationPlanningProvider().plan(transcript)
    assert transcript.language == "zh"
    assert plan.animations[0].type == "keyword_pop"


def test_offline_transcript_planner_uses_real_segment_text_and_timestamps() -> None:
    transcript = create_mock_transcript()
    plan = TranscriptAnimationPlanningProvider().plan(transcript)
    assert plan.animations[0].trigger_text in transcript.segments[0].text
    assert len(plan.animations[0].trigger_text) <= 18
    assert plan.animations[0].start_ms == transcript.segments[0].start_ms
    assert plan.animations[0].end_ms <= transcript.segments[0].end_ms


def test_offline_planner_prioritizes_book_visual_over_nearby_keyword() -> None:
    transcript = Transcript.model_validate({
        "language": "zh", "full_text": "\u7b2c\u4e00\u6bb5\u300a\u5fc3\u7406\u5b66\u4e0e\u751f\u6d3b\u300b", "segments": [
            {"text": "\u7b2c\u4e00\u6bb5", "start_ms": 0, "end_ms": 3000, "words": [{"text": "\u7b2c\u4e00\u6bb5", "start_ms": 0, "end_ms": 3000}]},
            {"text": "\u4ecb\u7ecd\u300a\u5fc3\u7406\u5b66\u4e0e\u751f\u6d3b\u300b", "start_ms": 3200, "end_ms": 6000, "words": [{"text": "\u4ecb\u7ecd", "start_ms": 3200, "end_ms": 4000}, {"text": "\u4e66", "start_ms": 4000, "end_ms": 6000}]},
        ],
    })
    plan = TranscriptAnimationPlanningProvider().plan(transcript)
    assert [animation.type for animation in plan.animations] == ["media_visual"]
    assert plan.animations[0].start_ms == 3200


def test_offline_planner_finitely_merges_adjacent_split_sentence() -> None:
    transcript = Transcript.model_validate({
        "language": "zh", "full_text": "设想一年之后干什么而不是只想明天", "segments": [
            {"text": "设想一年之后干什么", "start_ms": 0, "end_ms": 1800,
             "words": [{"text": "设想一年之后干什么", "start_ms": 0, "end_ms": 1800}]},
            {"text": "而不是只想明天", "start_ms": 1800, "end_ms": 3400,
             "words": [{"text": "而不是只想明天", "start_ms": 1800, "end_ms": 3400}]},
        ],
    })
    plan = TranscriptAnimationPlanningProvider().plan(transcript)
    comparison = plan.animations[0]
    assert comparison.type == "info_graphic"
    assert comparison.parameters.items == ["设想一年之后干什么", "只想明天"]
    assert comparison.end_ms <= 3400
