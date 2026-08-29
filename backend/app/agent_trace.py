"""Privacy-conscious task-local Agent trace persistence."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_tools import AGENT_PROMPT_VERSION, ANIMATION_PLAN_SCHEMA_VERSION

TRACE_FILENAME = "agent_trace.json"
TRACE_SCHEMA_VERSION = "agent-trace-v2"


class AgentTraceError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_path(task_dir: Path) -> Path:
    resolved = task_dir.resolve()
    if resolved.parent == resolved or not resolved.name:
        raise AgentTraceError("Agent trace requires a task directory")
    return resolved / TRACE_FILENAME


class AgentTrace:
    """Append bounded audit entries through atomic file replacement."""

    def __init__(self, task_dir: Path, task_id: str) -> None:
        self.path = _trace_path(task_dir)
        if self.path.parent.name != task_id:
            raise AgentTraceError("Agent trace task ID does not match its directory")
        self.task_id = task_id
        self._lock = threading.Lock()

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "task_id": self.task_id,
            "workflow_mode": "agent",
            "run": {
                "run_id": self.task_id,
                "kind": "video_agent_workflow",
            },
            "prompt_version": AGENT_PROMPT_VERSION,
            "plan_schema_version": ANIMATION_PLAN_SCHEMA_VERSION,
            "planner": None,
            "summary": {
                "status": "running",
                "retry_count": 0,
                "last_failure_category": None,
            },
            "entries": [],
        }

    def _upgrade(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upgrade v1 traces in memory while preserving their audit entries."""

        if payload.get("schema_version") == TRACE_SCHEMA_VERSION:
            return payload
        if payload.get("schema_version") != "agent-trace-v1":
            raise AgentTraceError("Agent trace schema is unsupported")
        payload["schema_version"] = TRACE_SCHEMA_VERSION
        payload["run"] = {
            "run_id": self.task_id,
            "kind": "video_agent_workflow",
        }
        tool_ordinals: dict[tuple[str, str], int] = {}
        for entry in payload.get("entries", []):
            node = str(entry.get("node", "unknown"))
            entry["run_id"] = self.task_id
            entry["node_run_id"] = f"{self.task_id}:{node}"
            if entry.get("event_type") in {"tool_call", "model_call"}:
                tool_name = "legacy_model" if entry.get("event_type") == "model_call" else "legacy_tool"
                key = (node, tool_name)
                tool_ordinals[key] = tool_ordinals.get(key, 0) + 1
                entry["tool_name"] = tool_name
                entry["tool_call_id"] = (
                    f"{self.task_id}:{node}:{tool_name}:{tool_ordinals[key]}"
                )
        return payload

    def read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentTraceError("Agent trace is not readable") from exc
        if not isinstance(payload, dict) or payload.get("task_id") != self.task_id:
            raise AgentTraceError("Agent trace identity is invalid")
        return self._upgrade(payload)

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)

    def append(
        self,
        event_type: str,
        *,
        node: str,
        status: str,
        duration_ms: int | None = None,
        input_summary: dict[str, Any] | None = None,
        output_summary: dict[str, Any] | None = None,
        error_category: str | None = None,
        violations: list[dict[str, Any]] | None = None,
        planner: dict[str, Any] | None = None,
        retry_count: int | None = None,
        tool_name: str | None = None,
    ) -> None:
        with self._lock:
            payload = self.read()
            if planner is not None:
                payload["planner"] = planner
            if retry_count is not None:
                payload["summary"]["retry_count"] = retry_count
            if error_category is not None:
                payload["summary"]["last_failure_category"] = error_category
            entry: dict[str, Any] = {
                "sequence": len(payload["entries"]) + 1,
                "timestamp": _utc_now(),
                "event_type": event_type,
                "node": node,
                "status": status,
                "run_id": self.task_id,
                "node_run_id": f"{self.task_id}:{node}",
            }
            if event_type in {"tool_call", "model_call"}:
                safe_tool_name = tool_name or (
                    "model" if event_type == "model_call" else "unspecified_tool"
                )
                ordinal = 1 + sum(
                    previous.get("node") == node
                    and previous.get("tool_name") == safe_tool_name
                    and previous.get("event_type") in {"tool_call", "model_call"}
                    for previous in payload["entries"]
                )
                entry["tool_name"] = safe_tool_name
                entry["tool_call_id"] = (
                    f"{self.task_id}:{node}:{safe_tool_name}:{ordinal}"
                )
            if duration_ms is not None:
                entry["duration_ms"] = max(0, duration_ms)
            if input_summary is not None:
                entry["input_summary"] = input_summary
            if output_summary is not None:
                entry["output_summary"] = output_summary
            if error_category is not None:
                entry["error_category"] = error_category
            if violations:
                entry["violations"] = violations[:50]
            payload["entries"].append(entry)
            self._write(payload)

    def finalize(self, status: str, *, retry_count: int, failure_category: str | None = None) -> None:
        with self._lock:
            payload = self.read()
            payload["summary"] = {
                "status": status,
                "retry_count": retry_count,
                "last_failure_category": failure_category,
            }
            self._write(payload)

    def set_status(
        self, status: str, *, retry_count: int, failure_category: str | None = None
    ) -> None:
        """Persist a non-terminal audit status such as awaiting approval."""

        self.finalize(
            status,
            retry_count=retry_count,
            failure_category=failure_category,
        )


def read_agent_trace(task_dir: Path, task_id: str) -> dict[str, Any] | None:
    trace = AgentTrace(task_dir, task_id)
    return None if not trace.path.is_file() else trace.read()
