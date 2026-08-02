import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app import storage
from backend.app.providers import MockAnimationPlanningProvider, MockSpeechRecognitionProvider


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


def test_mock_provider_interfaces_produce_valid_plan() -> None:
    transcript = MockSpeechRecognitionProvider().transcribe()
    plan = MockAnimationPlanningProvider().plan(transcript)
    assert transcript.language == "zh"
    assert plan.animations[0].type == "keyword_pop"
