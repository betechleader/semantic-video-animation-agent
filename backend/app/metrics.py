"""Privacy-safe, task-local execution metrics.

Metrics deliberately contain correlation and technical delivery information only.
They never contain media bytes, transcript content, local paths, face detections, or
exception messages (which can themselves include an input path or source text).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from .video import ensure_storage_path

METRICS_FILENAME = "metrics.json"
METRICS_SCHEMA_VERSION = 1
STAGE_NAMES = (
    "upload_probe",
    "audio_extraction",
    "asr",
    "asr_correction",
    "planning",
    "media_asset_acquisition",
    "media_safety_analysis",
    "remotion_render",
    "compositing",
    "quality_check",
)

T = TypeVar("T")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: float) -> int:
    return max(0, round((time.perf_counter() - started_at) * 1000))


def _metrics_path(task_dir: Path) -> Path:
    return ensure_storage_path(task_dir / METRICS_FILENAME)


def _write(path: Path, payload: dict) -> None:
    """Atomically replace the small JSON report so a reader never sees partial JSON."""
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_metrics(task_dir: Path, task_id: str) -> dict | None:
    path = _metrics_path(task_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("task_id") != task_id:
        return None
    return payload


class TaskMetrics:
    """Append phase durations to one local task report, grouped by render attempt."""

    def __init__(self, task_dir: Path, task_id: str) -> None:
        self.task_dir = ensure_storage_path(task_dir)
        self.task_id = task_id

    @property
    def path(self) -> Path:
        return _metrics_path(self.task_dir)

    def _load(self) -> dict:
        payload = read_metrics(self.task_dir, self.task_id)
        if payload is None:
            raise RuntimeError("Task metrics have not been initialized")
        return payload

    def _save(self, payload: dict) -> None:
        _write(self.path, payload)

    def _attempt(self, payload: dict, attempt_number: int) -> dict:
        for attempt in payload["attempts"]:
            if attempt["attempt"] == attempt_number:
                return attempt
        raise RuntimeError("Task metrics attempt does not exist")

    def current_or_start_attempt(self, kind: str) -> int:
        payload = self._load()
        for attempt in reversed(payload["attempts"]):
            if attempt["status"] == "running":
                return int(attempt["attempt"])
        attempt_number = len(payload["attempts"]) + 1
        payload["attempts"].append({
            "attempt": attempt_number,
            "kind": kind,
            "status": "running",
            "failure_category": None,
            "started_at": _utc_now(),
            "completed_at": None,
            "total_duration_ms": None,
            "stages": {},
            "output_quality": None,
        })
        payload["attempt_count"] = attempt_number
        payload["status"] = "running"
        payload["failure_category"] = None
        self._save(payload)
        return attempt_number

    def record_stage(self, attempt_number: int, stage: str, action: Callable[[], T]) -> T:
        if stage not in STAGE_NAMES:
            raise ValueError(f"Unsupported metrics stage: {stage}")
        started_at = time.perf_counter()
        try:
            result = action()
        except BaseException as exc:
            status = "cancelled" if exc.__class__.__name__ == "ProcessingCancelled" else "failed"
            self._finish_stage(attempt_number, stage, status, _duration_ms(started_at))
            raise
        self._finish_stage(attempt_number, stage, "completed", _duration_ms(started_at))
        return result

    def _finish_stage(self, attempt_number: int, stage: str, status: str, duration_ms: int) -> None:
        payload = self._load()
        attempt = self._attempt(payload, attempt_number)
        attempt["stages"][stage] = {"status": status, "duration_ms": duration_ms}
        if status == "failed":
            attempt["failure_category"] = stage
        self._save(payload)

    def finalize(self, attempt_number: int, status: str, *, failure_category: str | None = None, output_quality: dict | None = None) -> None:
        if status not in {"completed", "failed", "cancelled", "rejected"}:
            raise ValueError("Metrics status must be terminal")
        payload = self._load()
        attempt = self._attempt(payload, attempt_number)
        if attempt["status"] != "running":
            return
        attempt["status"] = status
        attempt["completed_at"] = _utc_now()
        attempt["total_duration_ms"] = sum(stage["duration_ms"] for stage in attempt["stages"].values())
        # A stage-specific category is more useful than a broad workflow fallback.
        attempt["failure_category"] = attempt["failure_category"] or failure_category
        if status == "failed" and attempt["failure_category"] is None:
            attempt["failure_category"] = "workflow"
        # OutputQuality is a controlled technical summary (no filenames or paths).
        attempt["output_quality"] = output_quality
        payload["status"] = status
        payload["failure_category"] = attempt["failure_category"]
        self._save(payload)


def initialize_initial_metrics(task_dir: Path, task_id: str, trace_id: str, upload_probe_duration_ms: int) -> TaskMetrics:
    """Create the report after a valid upload/probe has been persisted as a task."""
    safe_dir = ensure_storage_path(task_dir)
    path = _metrics_path(safe_dir)
    payload = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "task_id": task_id,
        # The opaque digest retains trace correlation without copying a caller-supplied
        # header into the privacy-safe artifact.
        "trace_id_sha256": hashlib.sha256(trace_id.encode("utf-8")).hexdigest(),
        "status": "running",
        "failure_category": None,
        "attempt_count": 1,
        "privacy": {
            "local_only": True,
            "excluded_data": [
                "video_frames", "audio", "transcript_text", "absolute_paths",
                "identity_information", "face_coordinates", "exception_messages",
            ],
        },
        "attempts": [{
            "attempt": 1,
            "kind": "initial",
            "status": "running",
            "failure_category": None,
            "started_at": _utc_now(),
            "completed_at": None,
            "total_duration_ms": None,
            "stages": {"upload_probe": {"status": "completed", "duration_ms": max(0, upload_probe_duration_ms)}},
            "output_quality": None,
        }],
    }
    _write(path, payload)
    return TaskMetrics(safe_dir, task_id)
