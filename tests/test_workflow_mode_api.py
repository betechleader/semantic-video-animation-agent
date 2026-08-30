from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app import database, main
from backend.app.models import ExecutionJob, VideoTask
from backend.app.schemas import VideoMetadata


@pytest.fixture()
def workflow_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    monkeypatch.setattr(
        main,
        "probe_video",
        lambda _path: VideoMetadata(
            duration_seconds=1.0,
            width=320,
            height=568,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            has_video=True,
            has_audio=True,
        ),
    )
    monkeypatch.setattr(main, "initialize_initial_metrics", lambda *_args: None)
    standard_calls: list[tuple] = []
    agent_calls: list[tuple] = []
    monkeypatch.setattr(main, "start_task", lambda *args: standard_calls.append(args))
    monkeypatch.setattr(
        main,
        "start_agent_task",
        lambda *args, **kwargs: agent_calls.append(
            args + ((kwargs["director_instruction"],) if "director_instruction" in kwargs else ())
        ),
    )
    database.initialize_database()
    yield TestClient(main.app), storage, standard_calls, agent_calls


def upload(client: TestClient, data: dict[str, str] | None = None):
    return client.post(
        "/api/videos",
        files={"file": ("speech.mp4", b"fake-mp4", "video/mp4")},
        data=data or {},
    )


def test_upload_defaults_to_standard_and_preserves_start_task_signature(workflow_client) -> None:
    client, _storage, standard_calls, agent_calls = workflow_client

    response = upload(client)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["workflow_mode"] == "standard"
    assert len(standard_calls) == 1
    assert agent_calls == []
    call = standard_calls[0]
    assert len(call) == 6
    assert call[0] == body["task_id"]
    assert call[1].name == body["task_id"]
    assert call[2].model_dump() == body["metadata"]
    assert call[3] == body["trace_id"]
    assert call[4:] == ("configured", "mock")
    task = database.get_task(body["task_id"])
    assert task is not None
    assert task["workflow_mode"] == "standard"
    assert task["processing_profile"] == "configured"
    assert task["media_provider"] == "mock"
    assert task["approval_policy"] is None


def test_upload_dispatches_agent_and_forwards_existing_processing_choices(workflow_client) -> None:
    client, _storage, standard_calls, agent_calls = workflow_client

    response = upload(
        client,
        {
            "workflow_mode": "agent",
            "processing_profile": "real",
            "media_provider": "knowledge",
            "approval_policy": "on_risk",
        },
    )

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["workflow_mode"] == "agent"
    assert standard_calls == []
    assert len(agent_calls) == 1
    call = agent_calls[0]
    assert len(call) == 6
    assert call[0] == body["task_id"]
    assert call[1].name == body["task_id"]
    assert call[2].model_dump() == body["metadata"]
    assert call[3] == body["trace_id"]
    assert call[4:] == ("real", "knowledge")
    task = database.get_task(body["task_id"])
    assert task is not None
    assert task["workflow_mode"] == "agent"
    assert task["processing_profile"] == "real"
    assert task["media_provider"] == "knowledge"
    assert task["approval_policy"] == "on_risk"


def test_approval_policy_is_agent_only_and_validated_before_creating_task(workflow_client) -> None:
    client, storage, standard_calls, agent_calls = workflow_client

    standard = upload(client, {"workflow_mode": "standard", "approval_policy": "unknown"})
    assert standard.status_code == 202
    assert database.get_task(standard.json()["task_id"])["approval_policy"] is None
    assert len(standard_calls) == 1

    before = {path.name for path in storage.iterdir() if path.is_dir()}
    invalid_agent = upload(client, {"workflow_mode": "agent", "approval_policy": "unknown"})
    assert invalid_agent.status_code == 422
    assert {path.name for path in storage.iterdir() if path.is_dir()} == before
    assert agent_calls == []


def test_invalid_workflow_mode_returns_422_without_task_directory_or_row(workflow_client) -> None:
    client, storage, standard_calls, agent_calls = workflow_client
    before_directories = {path.name for path in storage.iterdir() if path.is_dir()}
    with next(database.get_session()) as session:
        before_rows = session.scalar(select(func.count()).select_from(VideoTask))

    response = upload(client, {"workflow_mode": "unknown"})

    assert response.status_code == 422
    assert response.json()["detail"] == "workflow_mode must be standard or agent"
    assert standard_calls == []
    assert agent_calls == []
    assert {path.name for path in storage.iterdir() if path.is_dir()} == before_directories
    with next(database.get_session()) as session:
        after_rows = session.scalar(select(func.count()).select_from(VideoTask))
    assert after_rows == before_rows


def test_director_instruction_is_agent_only_bounded_and_persisted(workflow_client) -> None:
    client, storage, standard_calls, agent_calls = workflow_client

    agent = upload(
        client,
        {"workflow_mode": "agent", "director_instruction": "  前三秒更抓人  "},
    )
    assert agent.status_code == 202
    agent_task = database.get_task(agent.json()["task_id"])
    assert agent_task["director_instruction"] == "前三秒更抓人"
    assert agent_calls[0][-1] == "前三秒更抓人"

    standard = upload(
        client,
        {"workflow_mode": "standard", "director_instruction": "不得进入标准模式"},
    )
    assert standard.status_code == 202
    standard_task = database.get_task(standard.json()["task_id"])
    assert standard_task["director_instruction"] is None
    assert len(standard_calls[-1]) == 6

    before = {path.name for path in storage.iterdir() if path.is_dir()}
    too_long = upload(
        client,
        {"workflow_mode": "agent", "director_instruction": "导" * 2001},
    )
    assert too_long.status_code == 422
    assert "at most 2000" in too_long.json()["detail"]
    assert {path.name for path in storage.iterdir() if path.is_dir()} == before


def test_worker_mode_persists_dispatch_without_starting_in_process_thread(workflow_client, monkeypatch) -> None:
    client, _storage, standard_calls, agent_calls = workflow_client
    monkeypatch.setattr(main, "SETTINGS", replace(main.SETTINGS, execution_mode="worker"))

    response = upload(client, {"workflow_mode": "agent", "processing_profile": "mock"})

    assert response.status_code == 202
    assert standard_calls == []
    assert agent_calls == []
    with next(database.get_session()) as session:
        job = session.scalar(select(ExecutionJob).where(ExecutionJob.task_id == response.json()["task_id"]))
    assert job is not None
    assert job.kind == "agent"
    assert job.status == "queued"
