"""Local stdio MCP facade for the existing semantic-video services.

The MCP layer is deliberately an adapter: task creation, approval, validation,
candidate auditing, and re-rendering remain owned by the same functions used by
the FastAPI application.  No tool accepts a filesystem path or an arbitrary
download URL.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, UploadFile
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import main
from .agent_tools import DIRECTOR_INSTRUCTION_MAX_LENGTH
from .config import MAX_UPLOAD_BYTES, STORAGE_ROOT
from .database import append_task_event, get_task
from .media_providers import load_candidates
from .schemas import (
    AgentApprovalEdit,
    AnimationPlan,
    MediaCandidate,
    MediaSearchRequest,
    ReviewUpdate,
    Transcript,
)
from .storage import StorageService

MAX_BASE64_UPLOAD_CHARS = ((MAX_UPLOAD_BYTES + 2) // 3) * 4


class CreateVideoInput(BaseModel):
    """Bounded video upload with no client-controlled local path."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(default="source.mp4", min_length=5, max_length=120, pattern=r"^[^/\\]+\.mp4$")
    content_base64: str = Field(
        min_length=1,
        max_length=MAX_BASE64_UPLOAD_CHARS,
        description="Base64-encoded MP4 bytes; decoded size is limited by MAX_UPLOAD_MB.",
    )
    workflow_mode: Literal["standard", "agent"] = "standard"
    processing_profile: Literal["configured", "real", "mock"] = "configured"
    media_provider: Literal["mock", "manual", "knowledge", "wikimedia_commons", "pexels"] = "mock"
    director_instruction: str | None = Field(default=None, max_length=DIRECTOR_INSTRUCTION_MAX_LENGTH)
    approval_policy: Literal["never", "on_risk", "always"] = "never"


class TaskRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID


class AssetSearchInput(TaskRef):
    query: str = Field(min_length=1, max_length=120)
    asset_kind: Literal["external_image", "external_video"] = "external_image"


class ApprovalInput(TaskRef):
    decision: Literal["approve", "edit", "reject"] = "approve"
    plan: AnimationPlan | None = None

    @model_validator(mode="after")
    def validate_decision_payload(self) -> "ApprovalInput":
        if self.decision == "edit" and self.plan is None:
            raise ValueError("plan is required when decision is edit")
        if self.decision != "edit" and self.plan is not None:
            raise ValueError("plan is only accepted when decision is edit")
        return self


class ReplaceAssetInput(TaskRef):
    animation_id: str = Field(pattern=r"^animation_[A-Za-z0-9_-]+$")
    candidate_id: str = Field(pattern=r"^candidate_[A-Za-z0-9_-]+$")


class TaskStatusOutput(BaseModel):
    task_id: str
    status: str
    workflow_mode: str
    processing_profile: str
    media_provider: str
    approval_policy: str | None
    has_transcript: bool
    has_plan: bool
    result_resource_uri: str | None


class ActionOutput(BaseModel):
    task_id: str
    status: str
    detail: str
    result_resource_uri: str | None = None


class AssetSearchOutput(BaseModel):
    task_id: str
    query_sha256: str
    candidates: list[MediaCandidate]


READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
SEARCH_AND_CACHE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)
WRITE_ONCE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)

mcp = MCPServer(
    "semantic-video-animation-agent",
    description="Local, audited semantic-video workflow tools. Paths and raw task files are never exposed.",
    version="p9-v1",
)


def _task_id(value: UUID) -> str:
    return str(value)


def _raise_http_error(exc: HTTPException) -> None:
    detail = exc.detail if isinstance(exc.detail, str) else "The video workflow rejected this operation"
    raise ValueError(f"HTTP {exc.status_code}: {detail}") from exc


def _safe_status(task: dict[str, Any]) -> TaskStatusOutput:
    completed = task["status"] == "completed"
    return TaskStatusOutput(
        task_id=task["task_id"],
        status=task["status"],
        workflow_mode=task["workflow_mode"],
        processing_profile=task["processing_profile"],
        media_provider=task["media_provider"],
        approval_policy=task.get("approval_policy"),
        has_transcript=task.get("transcript") is not None,
        has_plan=task.get("plan") is not None,
        result_resource_uri=f"video://tasks/{task['task_id']}/result" if completed else None,
    )


def _existing_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise ValueError("Task not found")
    return task


@mcp.tool(annotations=WRITE_ONCE, structured_output=True)
async def create_video(request: CreateVideoInput) -> ActionOutput:
    """Create a standard or Agent video task from bounded base64 MP4 content."""

    try:
        content = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 must be valid base64") from exc
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Decoded video is empty or exceeds the configured upload limit")
    if len(content) < 12 or content[4:8] != b"ftyp":
        raise ValueError("Decoded content is not an MP4 file")

    upload = UploadFile(file=io.BytesIO(content), filename=request.filename)
    http_request = Request({"type": "http", "method": "POST", "path": "/mcp/create_video", "headers": []})
    http_request.state.trace_id = str(uuid4())
    try:
        created = await main.upload_video(
            http_request,
            upload,
            request.processing_profile,
            request.media_provider,
            request.workflow_mode,
            request.director_instruction,
            request.approval_policy,
        )
    except HTTPException as exc:
        _raise_http_error(exc)
    task_id = str(created["task_id"])
    append_task_event(
        task_id,
        "mcp_create_video",
        "Video task created through local MCP",
        {"workflow_mode": request.workflow_mode, "processing_profile": request.processing_profile},
    )
    return ActionOutput(task_id=task_id, status="pending", detail="Video task accepted")


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_video_status(request: TaskRef) -> TaskStatusOutput:
    """Return privacy-minimal task status without transcript, plan, or local paths."""

    return _safe_status(_existing_task(_task_id(request.task_id)))


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_agent_trace(request: TaskRef) -> dict[str, Any]:
    """Return the existing redacted Agent trace for an Agent task."""

    try:
        return main.get_video_agent_trace(_task_id(request.task_id))
    except HTTPException as exc:
        _raise_http_error(exc)


@mcp.tool(annotations=SEARCH_AND_CACHE, structured_output=True)
def search_asset(request: AssetSearchInput) -> AssetSearchOutput:
    """Search the task's configured provider and cache only validated candidates."""

    task_id = _task_id(request.task_id)
    try:
        result = main.search_video_media(
            task_id,
            MediaSearchRequest(query=request.query, asset_kind=request.asset_kind),
        )
    except HTTPException as exc:
        _raise_http_error(exc)
    append_task_event(
        task_id,
        "mcp_asset_search",
        "Asset candidates searched through local MCP",
        {
            "query_sha256": hashlib.sha256(request.query.encode("utf-8")).hexdigest(),
            "asset_kind": request.asset_kind,
            "candidate_count": len(result["candidates"]),
        },
    )
    return AssetSearchOutput(
        task_id=task_id,
        query_sha256=hashlib.sha256(request.query.encode("utf-8")).hexdigest(),
        candidates=[
            MediaCandidate.model_validate({
                field: candidate[field]
                for field in MediaCandidate.model_fields
                if field in candidate
            })
            for candidate in result["candidates"]
        ],
    )


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_pending_approval(request: TaskRef) -> dict[str, Any]:
    """Return the durable pending or decided Agent approval record."""

    try:
        return main.get_video_agent_approval(_task_id(request.task_id))
    except HTTPException as exc:
        _raise_http_error(exc)


@mcp.tool(annotations=WRITE_ONCE, structured_output=True)
def approve_plan(request: ApprovalInput) -> ActionOutput:
    """Approve, edit-and-approve, or reject one pending Agent plan atomically."""

    task_id = _task_id(request.task_id)
    try:
        if request.decision == "approve":
            result = main.approve_video_agent_plan(task_id)
        elif request.decision == "edit":
            assert request.plan is not None
            result = main.edit_video_agent_plan(task_id, AgentApprovalEdit(plan=request.plan))
        else:
            result = main.reject_video_agent_plan(task_id)
    except HTTPException as exc:
        _raise_http_error(exc)
    append_task_event(
        task_id,
        "mcp_approval_decision",
        "Agent approval decision submitted through local MCP",
        {"decision": request.decision, "decision_version": result["decision_version"]},
    )
    return ActionOutput(task_id=task_id, status=result["status"], detail="Approval decision persisted")


def _plan_with_candidate(task: dict[str, Any], animation_id: str, candidate_id: str) -> AnimationPlan:
    task_dir = StorageService(STORAGE_ROOT).task_directory(task["task_id"])
    candidates = {candidate.id: candidate for candidate in load_candidates(task_dir)}
    candidate = candidates.get(candidate_id)
    if candidate is None:
        raise ValueError("Candidate is not in this task's audited candidate manifest")

    plan = AnimationPlan.model_validate(task.get("plan"))
    animations = []
    matched = False
    for animation in plan.animations:
        if animation.id != animation_id:
            animations.append(animation)
            continue
        if animation.type != "media_visual":
            raise ValueError("Only media_visual animations can replace an asset")
        if animation.parameters.desired_asset_kind != candidate.asset_kind:
            raise ValueError("Candidate kind does not match the animation's requested asset kind")
        matched = True
        animations.append(animation.model_copy(update={
            "parameters": animation.parameters.model_copy(update={"selected_candidate_id": candidate_id})
        }))
    if not matched:
        raise ValueError("Animation not found in this task")
    return plan.model_copy(update={
        "animations": animations,
        "media_assets": [],
        "face_regions": [],
        "media_placements": [],
    })


@mcp.tool(annotations=WRITE_ONCE, structured_output=True)
def replace_asset(request: ReplaceAssetInput) -> ActionOutput:
    """Select an audited task-local candidate and start the validated re-render."""

    task_id = _task_id(request.task_id)
    task = _existing_task(task_id)
    if task["status"] != "completed":
        raise ValueError("Asset replacement is available only for completed tasks")
    plan = _plan_with_candidate(task, request.animation_id, request.candidate_id)
    try:
        result = main.save_review_and_rerender(
            task_id,
            ReviewUpdate(transcript=Transcript.model_validate(task["transcript"]), plan=plan),
        )
    except HTTPException as exc:
        _raise_http_error(exc)
    append_task_event(
        task_id,
        "mcp_asset_replaced",
        "Audited media candidate selected through local MCP",
        {"animation_id": request.animation_id, "candidate_id": request.candidate_id},
    )
    return ActionOutput(task_id=task_id, status=result["status"], detail="Asset replacement accepted for re-render")


@mcp.tool(annotations=WRITE_ONCE, structured_output=True)
def rerender_video(request: TaskRef) -> ActionOutput:
    """Re-render a completed task through the existing validated review boundary."""

    task_id = _task_id(request.task_id)
    task = _existing_task(task_id)
    if task["status"] != "completed":
        raise ValueError("Re-render is available only for completed tasks")
    try:
        result = main.save_review_and_rerender(
            task_id,
            ReviewUpdate(
                transcript=Transcript.model_validate(task["transcript"]),
                plan=AnimationPlan.model_validate(task["plan"]),
            ),
        )
    except HTTPException as exc:
        _raise_http_error(exc)
    append_task_event(task_id, "mcp_rerender_video", "Validated re-render requested through local MCP", {})
    return ActionOutput(task_id=task_id, status=result["status"], detail="Re-render accepted")


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def download_result(request: TaskRef) -> ActionOutput:
    """Return a result resource URI without exposing a local filesystem path."""

    task_id = _task_id(request.task_id)
    task = _existing_task(task_id)
    result = StorageService(STORAGE_ROOT).task_directory(task_id) / "result.mp4"
    if task["status"] != "completed" or not result.is_file():
        raise ValueError("Completed result is not available")
    return ActionOutput(
        task_id=task_id,
        status="completed",
        detail="Read the MCP result resource to receive video/mp4 bytes",
        result_resource_uri=f"video://tasks/{task_id}/result",
    )


@mcp.resource(
    "video://tasks/{task_id}",
    mime_type="application/json",
    description="Privacy-minimal status for one video task.",
)
def video_status_resource(task_id: str) -> str:
    try:
        task = _existing_task(str(UUID(task_id)))
    except (ValueError, AttributeError) as exc:
        raise ResourceNotFoundError("Video task resource not found") from exc
    return json.dumps(_safe_status(task).model_dump(), ensure_ascii=False)


@mcp.resource(
    "video://tasks/{task_id}/trace",
    mime_type="application/json",
    description="Privacy-safe Agent trace resource.",
)
def agent_trace_resource(task_id: str) -> str:
    try:
        trace = main.get_video_agent_trace(str(UUID(task_id)))
    except (ValueError, HTTPException) as exc:
        raise ResourceNotFoundError("Agent trace resource not found") from exc
    return json.dumps(trace, ensure_ascii=False)


@mcp.resource(
    "video://tasks/{task_id}/result",
    mime_type="video/mp4",
    description="Completed task result bytes; the local storage path is never returned.",
)
def video_result_resource(task_id: str) -> bytes:
    try:
        normalized = str(UUID(task_id))
        task = _existing_task(normalized)
        result = StorageService(STORAGE_ROOT).task_directory(normalized) / "result.mp4"
    except (ValueError, AttributeError) as exc:
        raise ResourceNotFoundError("Video result resource not found") from exc
    if task["status"] != "completed" or not result.is_file():
        raise ResourceNotFoundError("Video result resource not found")
    return result.read_bytes()


def run_stdio() -> None:
    """Run the local MCP server over stdio only."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_stdio()
