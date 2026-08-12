from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import agent_workflow, database, main, video
from backend.app.agent_workflow import (
    AGENT_NODES,
    AgentCheckpointStore,
    AgentWorkflowServices,
)
from backend.app.schemas import Animation, AnimationPlan, Transcript, TranscriptSegment, VideoMetadata, WordTiming


def _metadata() -> VideoMetadata:
    return VideoMetadata(
        duration_seconds=4.0,
        width=320,
        height=568,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        has_video=True,
        has_audio=True,
    )


def _asr_transcript() -> Transcript:
    return Transcript(
        language="zh",
        full_text="初稿",
        segments=[
            TranscriptSegment(
                text="初稿",
                start_ms=500,
                end_ms=2_500,
                words=[WordTiming(text="初稿", start_ms=500, end_ms=2_500)],
            )
        ],
    )


def _plan() -> AnimationPlan:
    return AnimationPlan(
        media_provider="mock",
        animations=[
            Animation(
                id="animation_agent_test",
                type="keyword_pop",
                template_id="keyword_pop_v1",
                start_ms=500,
                end_ms=2_500,
                trigger_text="已校正",
                parameters={
                    "text": "已校正",
                    "color": "#FFD400",
                    "position": "top-right",
                },
            )
        ],
    )


class RecordingServices:
    """Small, deterministic stand-in for every expensive Agent dependency."""

    def __init__(self, *, block_extract: bool = False) -> None:
        self.calls: list[str] = []
        self.extract_entered = threading.Event()
        self.allow_extract = threading.Event()
        if not block_extract:
            self.allow_extract.set()

    def bundle(self) -> AgentWorkflowServices:
        return AgentWorkflowServices(
            extract_audio=self.extract_audio,
            transcribe_audio=self.transcribe_audio,
            correct_asr_transcript=self.correct_transcript,
            build_animation_plan=self.build_plan,
            validate_plan=self.validate_plan,
            render_and_composite_video=self.render_video,
            verify_and_write_output_quality=self.verify_quality,
        )

    def extract_audio(self, task_dir: Path, metadata: VideoMetadata) -> Path:
        self.calls.append("audio_asr.extract")
        assert metadata == _metadata()
        self.extract_entered.set()
        assert self.allow_extract.wait(timeout=5), "test did not release blocked ASR node"
        return task_dir / "audio.wav"

    def transcribe_audio(self, audio_path: Path, processing_profile: str) -> Transcript:
        self.calls.append("audio_asr.transcribe")
        assert audio_path.name == "audio.wav"
        assert processing_profile == "mock"
        return _asr_transcript()

    def correct_transcript(self, transcript: Transcript) -> Transcript:
        self.calls.append("correction")
        assert transcript.full_text == "初稿"
        return transcript.model_copy(update={"full_text": "已校正"})

    def build_plan(
        self,
        transcript: Transcript,
        processing_profile: str,
        media_provider: str | None,
    ) -> AnimationPlan:
        self.calls.append("planning")
        assert transcript.full_text == "已校正"
        assert processing_profile == "mock"
        assert media_provider == "mock"
        return _plan()

    def validate_plan(self, plan: AnimationPlan, transcript: Transcript) -> AnimationPlan:
        self.calls.append("validation")
        assert transcript.full_text == "已校正"
        assert plan.animations[0].trigger_text == "已校正"
        return plan

    def render_video(
        self,
        task_dir: Path,
        metadata: VideoMetadata,
        transcript: Transcript,
        plan: AnimationPlan,
        task_id: str | None,
        _metrics,
    ) -> tuple[dict, dict]:
        self.calls.append("render")
        assert task_id == task_dir.name
        assert metadata == _metadata()
        (task_dir / "result.mp4").write_bytes(b"offline-agent-result")
        return transcript.model_dump(), plan.model_dump()

    def verify_quality(self, task_dir: Path, metadata: VideoMetadata, _metrics) -> dict:
        self.calls.append("quality")
        assert (task_dir / "result.mp4").is_file()
        assert metadata == _metadata()
        return {"passed": True, "provider": "recording-fake"}


@pytest.fixture()
def isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage_root = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage_root)
    monkeypatch.setattr(database, "DATABASE_PATH", storage_root / "tasks.sqlite3")
    monkeypatch.setattr(video, "STORAGE_ROOT", storage_root)
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    database.initialize_database()
    yield storage_root
    if database._engine is not None:
        database._engine.dispose()


def _create_task(
    storage_root: Path,
    task_id: str,
    *,
    workflow_mode: str = "agent",
    approval_policy: str = "never",
) -> Path:
    task_dir = storage_root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "source.mp4").write_bytes(b"offline-source")
    database.create_task(
        task_id,
        _metadata().model_dump(),
        trace_id=f"trace-{task_id}",
        workflow_mode=workflow_mode,
        processing_profile="mock",
        media_provider="mock",
        approval_policy=approval_policy,
    )
    return task_dir


def _wait_for_status(task_id: str, expected: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = database.get_task(task_id)
        if task is not None and task["status"] == expected:
            return task
        time.sleep(0.01)
    pytest.fail(f"task {task_id} did not reach {expected}: {database.get_task(task_id)}")


def test_agent_runs_all_nodes_in_order_and_persists_real_outputs(isolated_database: Path) -> None:
    task_id = "agent-all-nodes"
    task_dir = _create_task(isolated_database, task_id)
    recording = RecordingServices()
    store = AgentCheckpointStore.for_storage_root(isolated_database)

    checkpoint = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=recording.bundle(),
        checkpoint_store=store,
    )

    assert recording.calls == [
        "audio_asr.extract",
        "audio_asr.transcribe",
        "correction",
        "planning",
        "validation",
        "render",
        "quality",
    ]
    assert checkpoint["run_status"] == "completed"
    assert checkpoint["next_node"] is None
    assert checkpoint["state"]["thread_id"] == task_id
    assert checkpoint["state"]["completed_nodes"] == list(AGENT_NODES)
    assert checkpoint["state"]["transcript"]["full_text"] == "已校正"
    assert checkpoint["state"]["plan"]["animations"][0]["trigger_text"] == "已校正"
    assert checkpoint["state"]["quality"] == {"passed": True, "provider": "recording-fake"}
    assert store.path == (isolated_database / "agent_checkpoints.sqlite3").resolve()
    assert store.path.is_file()

    task = database.get_task(task_id)
    assert task is not None
    assert task["status"] == "completed"
    assert task["transcript"] == checkpoint["state"]["transcript"]
    assert task["plan"] == checkpoint["state"]["plan"]

    node_events = [event for event in database.get_task_events(task_id) if event["type"] == "agent_node"]
    assert [(event["payload"]["node"], event["payload"]["status"]) for event in node_events] == [
        pair for node in AGENT_NODES for pair in ((node, "started"), (node, "completed"))
    ]
    for event in node_events:
        assert set(event["payload"]) == {"thread_id", "node", "status", "checkpoint_version"}
        assert event["payload"]["thread_id"] == task_id
        assert event["payload"]["node"] in AGENT_NODES
        assert event["payload"]["status"] in {"started", "completed"}
        assert "progress" not in event["message"].lower()


def test_restart_resumes_after_validation_without_repeating_asr_or_planning(isolated_database: Path) -> None:
    task_id = "agent-resume"
    task_dir = _create_task(isolated_database, task_id)
    recording = RecordingServices()
    first_store = AgentCheckpointStore.for_storage_root(isolated_database)

    interrupted = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=recording.bundle(),
        checkpoint_store=first_store,
        interrupt_after="validation",
    )

    assert interrupted["run_status"] == "interrupted"
    assert interrupted["next_node"] == "render"
    assert interrupted["state"]["completed_nodes"] == list(AGENT_NODES[:5])
    before_restart = list(recording.calls)
    assert before_restart == [
        "audio_asr.extract",
        "audio_asr.transcribe",
        "correction",
        "planning",
        "validation",
    ]

    # A new store instance represents reopening the durable SQLite checkpoint
    # after the original API process has stopped.
    reopened_store = AgentCheckpointStore(first_store.path)
    completed = agent_workflow.run_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=recording.bundle(),
        checkpoint_store=reopened_store,
    )

    assert completed["run_status"] == "completed"
    assert completed["state"]["completed_nodes"] == list(AGENT_NODES)
    assert recording.calls == before_restart + ["render", "quality"]
    assert recording.calls.count("audio_asr.transcribe") == 1
    assert recording.calls.count("planning") == 1

    node_events = [event for event in database.get_task_events(task_id) if event["type"] == "agent_node"]
    completed_events = [event for event in node_events if event["payload"]["status"] == "completed"]
    assert [event["payload"]["node"] for event in completed_events] == list(AGENT_NODES)
    resumed_events = [event for event in node_events if event["payload"]["status"] == "resumed"]
    assert len(resumed_events) == 1
    assert resumed_events[0]["payload"]["node"] == "render"


def test_duplicate_start_returns_one_live_runner(isolated_database: Path) -> None:
    task_id = "agent-duplicate-start"
    task_dir = _create_task(isolated_database, task_id)
    recording = RecordingServices(block_extract=True)
    store = AgentCheckpointStore.for_storage_root(isolated_database)

    first = agent_workflow.start_agent_task(
        task_id,
        task_dir,
        _metadata(),
        f"trace-{task_id}",
        "mock",
        "mock",
        services=recording.bundle(),
        checkpoint_store=store,
    )
    try:
        assert recording.extract_entered.wait(timeout=5)
        duplicate = agent_workflow.start_agent_task(
            task_id,
            task_dir,
            _metadata(),
            f"trace-{task_id}",
            "mock",
            "mock",
            services=recording.bundle(),
            checkpoint_store=store,
        )
        assert duplicate is first
    finally:
        recording.allow_extract.set()

    first.join(timeout=5)
    assert not first.is_alive()
    assert database.get_task(task_id)["status"] == "completed"
    assert recording.calls.count("audio_asr.extract") == 1
    assert recording.calls.count("render") == 1
    assert agent_workflow.get_active_agent_thread(task_id) is None


def test_startup_recovery_only_runs_agent_tasks_and_converges_cancellation(isolated_database: Path) -> None:
    standard_id = "standard-pending"
    runnable_id = "agent-recoverable"
    cancelled_id = "agent-cancel-requested"
    _create_task(isolated_database, standard_id, workflow_mode="standard")
    _create_task(isolated_database, runnable_id)
    _create_task(isolated_database, cancelled_id)
    assert database.request_cancellation(cancelled_id)
    recording = RecordingServices()
    store = AgentCheckpointStore.for_storage_root(isolated_database)

    started = agent_workflow.recover_agent_tasks(
        storage_root=isolated_database,
        services=recording.bundle(),
        checkpoint_store=store,
    )

    assert set(started) == {runnable_id, cancelled_id}
    _wait_for_status(runnable_id, "completed")
    cancelled = _wait_for_status(cancelled_id, "cancelled")
    assert cancelled["cancel_requested"] is True
    assert database.get_task(standard_id)["status"] == "pending"
    assert recording.calls.count("audio_asr.extract") == 1
    assert recording.calls.count("planning") == 1
    assert recording.calls.count("render") == 1

    cancelled_checkpoint = store.load(cancelled_id)
    assert cancelled_checkpoint is not None
    assert cancelled_checkpoint["run_status"] == "cancelled"
    assert cancelled_checkpoint["next_node"] == "upload_probe"
    cancelled_node_events = [
        event for event in database.get_task_events(cancelled_id) if event["type"] == "agent_node"
    ]
    assert [(event["payload"]["node"], event["payload"]["status"]) for event in cancelled_node_events] == [
        ("upload_probe", "failed")
    ]
    assert cancelled_node_events[0]["payload"]["error_category"] == "cancelled"


def test_startup_recovery_marks_a_corrupt_task_failed_and_continues(isolated_database: Path) -> None:
    corrupt_id = "../outside-storage"
    runnable_id = "agent-after-corrupt"
    database.create_task(
        corrupt_id,
        _metadata().model_dump(),
        trace_id="trace-corrupt",
        workflow_mode="agent",
        processing_profile="mock",
        media_provider="mock",
    )
    _create_task(isolated_database, runnable_id)
    recording = RecordingServices()
    store = AgentCheckpointStore.for_storage_root(isolated_database)

    started = agent_workflow.recover_agent_tasks(
        storage_root=isolated_database,
        services=recording.bundle(),
        checkpoint_store=store,
    )

    assert started == [runnable_id]
    corrupt = _wait_for_status(corrupt_id, "failed")
    assert corrupt["error"] == "Agent workflow persisted state could not be recovered"
    assert _wait_for_status(runnable_id, "completed")["status"] == "completed"
    recovery_events = [
        event
        for event in database.get_task_events(corrupt_id)
        if event["type"] == "agent_recovery_failed"
    ]
    assert len(recovery_events) == 1
    assert recovery_events[0]["payload"] == {
        "thread_id": corrupt_id,
        "error_category": "AgentWorkflowError",
    }


def test_agent_mock_upload_completes_offline_and_streams_node_events(
    isolated_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = RecordingServices()
    store = AgentCheckpointStore.for_storage_root(isolated_database)
    real_start = agent_workflow.start_agent_task

    monkeypatch.setattr(main, "STORAGE_ROOT", isolated_database)
    monkeypatch.setattr(main, "initialize_initial_metrics", lambda *_args: None)
    monkeypatch.setattr(main, "probe_video", lambda _source: _metadata())

    def dispatch_with_offline_services(*args):
        return real_start(*args, services=recording.bundle(), checkpoint_store=store)

    monkeypatch.setattr(main, "start_agent_task", dispatch_with_offline_services)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/videos",
            files={"file": ("speech.mp4", b"fake-mp4", "video/mp4")},
            data={"workflow_mode": "agent", "processing_profile": "mock", "media_provider": "mock"},
        )
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["workflow_mode"] == "agent"
        task_id = body["task_id"]

        task = _wait_for_status(task_id, "completed")
        assert task["workflow_mode"] == "agent"
        assert task["processing_profile"] == "mock"
        assert task["transcript"]["full_text"] == "已校正"

        events_response = client.get(f"/api/videos/{task_id}/events")
        assert events_response.status_code == 200
        assert events_response.headers["content-type"].startswith("text/event-stream")
        assert events_response.text.count("event: agent_node") == len(AGENT_NODES) * 2
        assert '"node": "audio_asr"' in events_response.text
        assert '"status": "completed"' in events_response.text
        assert '"progress"' not in events_response.text

        download = client.get(f"/api/videos/{task_id}/download")
        assert download.status_code == 200
        assert download.content == b"offline-agent-result"
