from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app import database, execution, main
from backend.app.models import ExecutionJob, TaskStatus


@pytest.fixture()
def execution_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    storage = tmp_path / "storage"
    monkeypatch.setattr(database, "STORAGE_ROOT", storage)
    monkeypatch.setattr(database, "DATABASE_PATH", storage / "tasks.sqlite3")
    if database._engine is not None:
        database._engine.dispose()
    monkeypatch.setattr(database, "_engine", None)
    monkeypatch.setattr(database, "_engine_path", None)
    monkeypatch.setattr(database, "_session_factory", None)
    database.initialize_database()
    return storage


def _create_task(task_id: str, workflow_mode: str = "standard") -> None:
    database.create_task(
        task_id,
        {
            "duration_seconds": 1.0,
            "width": 320,
            "height": 568,
            "frame_rate": 30.0,
            "video_codec": "h264",
            "audio_codec": "aac",
            "has_video": True,
            "has_audio": True,
        },
        workflow_mode=workflow_mode,
    )


def test_enqueue_is_idempotent_and_concurrent_claim_has_one_winner(
    execution_database: Path,
) -> None:
    _create_task("durable-claim")
    first = execution.enqueue_job("durable-claim", "standard", "initial")
    replay = execution.enqueue_job("durable-claim", "standard", "initial")
    assert replay["job_id"] == first["job_id"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(
            pool.map(
                lambda worker: execution.claim_next_job(worker, 30),
                ["worker-a", "worker-b"],
            )
        )
    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0]["attempt_count"] == 1


def test_expired_lease_is_reclaimed_from_latest_durable_state(
    execution_database: Path,
) -> None:
    _create_task("durable-recovery", workflow_mode="agent")
    execution.enqueue_job("durable-recovery", "agent", "initial", max_attempts=3)
    first = execution.claim_next_job("crashed-worker", 30)
    assert first is not None
    with next(database.get_session()) as session:
        row = session.get(ExecutionJob, first["job_id"])
        assert row is not None
        row.lease_expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(seconds=1)
        session.commit()

    resumed = execution.claim_next_job("replacement-worker", 30)
    assert resumed is not None
    assert resumed["job_id"] == first["job_id"]
    assert resumed["attempt_count"] == 2
    assert resumed["lease_owner"] == "replacement-worker"


def test_expired_lease_stops_after_configured_attempt_limit(
    execution_database: Path,
) -> None:
    _create_task("durable-exhausted")
    execution.enqueue_job("durable-exhausted", "standard", "initial", max_attempts=1)
    claimed = execution.claim_next_job("crashed-worker", 30)
    assert claimed is not None
    with next(database.get_session()) as session:
        row = session.get(ExecutionJob, claimed["job_id"])
        assert row is not None
        row.lease_expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(seconds=1)
        session.commit()

    assert execution.claim_next_job("replacement-worker", 30) is None
    assert database.get_task("durable-exhausted")["status"] == "failed"


def test_worker_heartbeat_job_completion_and_private_metrics(
    execution_database: Path, monkeypatch
) -> None:
    _create_task("durable-complete")
    execution.enqueue_job("durable-complete", "standard", "initial")

    def complete(job: dict, _storage: Path) -> None:
        assert job["task_id"] == "durable-complete"
        database.transition_task(job["task_id"], TaskStatus.COMPLETED, "done")

    monkeypatch.setattr(execution, "execute_job", complete)
    worker = execution.PersistentWorker("test-worker", storage_root=execution_database)
    assert worker.run_once()
    assert execution.active_worker_count() == 1
    snapshot = execution.execution_metrics()
    assert snapshot["tasks"]["completed"] == 1
    assert snapshot["jobs"]["succeeded"] == 1
    assert "durable-complete" not in str(snapshot)


def test_recovery_queues_standard_agent_and_review_without_duplicate_active_jobs(
    execution_database: Path,
) -> None:
    _create_task("recover-standard")
    _create_task("recover-agent", workflow_mode="agent")
    _create_task("recover-review")
    assert database.transition_task(
        "recover-review",
        TaskStatus.COMPLETED,
        "ready",
        transcript={"language": "zh", "full_text": "", "segments": []},
        plan={"animations": []},
    )
    assert database.start_review_render(
        "recover-review",
        {"language": "zh", "full_text": "", "segments": []},
        {"animations": []},
    )

    assert set(execution.recover_execution_jobs()) == {
        "recover-standard",
        "recover-agent",
        "recover-review",
    }
    assert execution.recover_execution_jobs() == []
    with next(database.get_session()) as session:
        jobs = session.scalars(
            select(ExecutionJob).order_by(ExecutionJob.task_id)
        ).all()
    assert [(job.task_id, job.kind) for job in jobs] == [
        ("recover-agent", "agent"),
        ("recover-review", "review"),
        ("recover-standard", "standard"),
    ]


def test_readiness_requires_worker_only_in_persistent_mode(
    execution_database: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        main, "SETTINGS", replace(main.SETTINGS, execution_mode="worker")
    )
    unavailable = main.health_ready()
    assert unavailable.status_code == 503
    execution.update_worker_heartbeat("ready-worker")
    available = main.health_ready()
    assert available.status_code == 200
    metrics = main.prometheus_metrics()
    assert "semantic_video_active_workers 1" in metrics
    assert "ready-worker" not in metrics
