import asyncio
import base64
import sys
from pathlib import Path
from uuid import uuid4

from mcp import Client, StdioServerParameters

from backend.app import database, main, mcp_server
from backend.app.media_providers import save_candidates
from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.models import TaskStatus
from backend.app.schemas import MediaCandidate, VideoMetadata


def configure_mcp_database(tmp_path: Path, monkeypatch) -> Path:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr(mcp_server, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    database._engine = None
    database._engine_path = None
    database._session_factory = None
    return storage


def completed_task(storage: Path, *, workflow_mode: str = "standard") -> tuple[str, dict, dict]:
    task_id = str(uuid4())
    task_dir = storage / task_id
    task_dir.mkdir(parents=True)
    transcript = create_mock_transcript().model_dump()
    plan = create_mock_plan(create_mock_transcript()).model_dump()
    metadata = {
        "duration_seconds": 5,
        "width": 320,
        "height": 568,
        "frame_rate": 30,
        "video_codec": "h264",
        "audio_codec": "aac",
        "has_video": True,
        "has_audio": True,
    }
    database.create_task(task_id, metadata, "trace", workflow_mode=workflow_mode)
    database.transition_task(
        task_id,
        TaskStatus.COMPLETED,
        "Done",
        transcript=transcript,
        plan=plan,
    )
    return task_id, transcript, plan


def run(coro):
    return asyncio.run(coro)


def test_mcp_client_discovers_typed_tools_and_resource_templates(tmp_path: Path, monkeypatch) -> None:
    configure_mcp_database(tmp_path, monkeypatch)

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            tools = await client.list_tools()
            by_name = {tool.name: tool for tool in tools.tools}
            assert set(by_name) == {
                "create_video",
                "get_video_status",
                "get_agent_trace",
                "search_asset",
                "get_pending_approval",
                "approve_plan",
                "replace_asset",
                "rerender_video",
                "download_result",
            }
            assert by_name["get_video_status"].annotations.read_only_hint is True
            assert by_name["approve_plan"].annotations.read_only_hint is False
            assert by_name["replace_asset"].annotations.idempotent_hint is False
            schema_text = str(by_name["create_video"].input_schema)
            assert "content_base64" in schema_text
            assert "workflow_mode" in schema_text

            templates = await client.list_resource_templates()
            uris = {str(item.uri_template) for item in templates.resource_templates}
            assert "video://tasks/{task_id}" in uris
            assert "video://tasks/{task_id}/trace" in uris
            assert "video://tasks/{task_id}/result" in uris

    run(scenario())


def test_mcp_stdio_entrypoint_negotiates_with_official_client() -> None:
    project_root = Path(__file__).resolve().parents[1]

    async def scenario() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "backend.app.mcp_server"],
            cwd=project_root,
        )
        async with Client(parameters, raise_exceptions=True) as client:
            tools = await client.list_tools()
            assert "create_video" in {tool.name for tool in tools.tools}
            assert client.server_info.name == "semantic-video-animation-agent"

    run(scenario())


def test_mcp_create_status_validation_and_no_path_input(tmp_path: Path, monkeypatch) -> None:
    storage = configure_mcp_database(tmp_path, monkeypatch)
    monkeypatch.setattr(main, "start_task", lambda *_args: None)
    monkeypatch.setattr(
        main,
        "probe_video",
        lambda _path: VideoMetadata(
            duration_seconds=2,
            width=320,
            height=568,
            frame_rate=30,
            video_codec="h264",
            audio_codec="aac",
            has_video=True,
            has_audio=True,
        ),
    )
    mp4 = b"\x00\x00\x00\x18ftypmp42" + b"safe-test-content"

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            created = await client.call_tool(
                "create_video",
                {"request": {"filename": "speech.mp4", "content_base64": base64.b64encode(mp4).decode("ascii"), "processing_profile": "mock"}},
            )
            assert created.is_error is False
            task_id = created.structured_content["task_id"]
            assert (storage / task_id / "source.mp4").read_bytes() == mp4
            assert "path" not in created.structured_content

            status = await client.call_tool("get_video_status", {"request": {"task_id": task_id}})
            assert status.is_error is False
            assert status.structured_content["workflow_mode"] == "standard"
            assert "transcript" not in status.structured_content
            assert "plan" not in status.structured_content

            invalid = await client.call_tool("get_video_status", {"request": {"task_id": "../../escape"}})
            assert invalid.is_error is True

    run(scenario())


def test_mcp_approval_is_atomic_and_cannot_bypass_pending_boundary(tmp_path: Path, monkeypatch) -> None:
    storage = configure_mcp_database(tmp_path, monkeypatch)
    task_id, transcript, plan = completed_task(storage, workflow_mode="agent")
    # Move the fixture back to the real durable approval boundary.
    with next(database.get_session()) as session:
        task = session.get(database.VideoTask, task_id)
        task.status = TaskStatus.AWAITING_APPROVAL
        session.commit()
    database.create_pending_approval(task_id, "always", [{"code": "policy_always"}], plan, [])
    monkeypatch.setattr(main, "_resume_after_approval", lambda _task_id: None)

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            pending = await client.call_tool("get_pending_approval", {"request": {"task_id": task_id}})
            assert pending.is_error is False
            assert pending.structured_content["status"] == "pending"
            first = await client.call_tool("approve_plan", {"request": {"task_id": task_id, "decision": "approve"}})
            assert first.is_error is False
            assert first.structured_content["status"] == "approved"
            second = await client.call_tool("approve_plan", {"request": {"task_id": task_id, "decision": "approve"}})
            assert second.is_error is True
            assert database.get_agent_approval(task_id)["decision_version"] == 1

            completed_id, _, _ = completed_task(storage, workflow_mode="agent")
            bypass = await client.call_tool("approve_plan", {"request": {"task_id": completed_id, "decision": "approve"}})
            assert bypass.is_error is True

    run(scenario())


def test_mcp_search_is_audited_and_rerender_reuses_existing_boundary(tmp_path: Path, monkeypatch) -> None:
    storage = configure_mcp_database(tmp_path, monkeypatch)
    task_id, _, _ = completed_task(storage)
    candidate = MediaCandidate(
        id="candidate_search_result",
        provider="wikimedia_commons",
        query="learning",
        asset_kind="external_image",
        source_url="https://upload.wikimedia.org/test.jpg",
        source_page_url="https://commons.wikimedia.org/wiki/File:Test.jpg",
        title="Learning illustration",
        author_or_provider="Wikimedia contributor",
        license="CC BY test fixture",
        mime_type="image/jpeg",
    )

    class FakeProvider:
        def search(self, query, asset_kind):
            assert query == "learning"
            assert asset_kind == "external_image"
            return [candidate]

    monkeypatch.setattr(main, "get_media_provider_by_name", lambda *_args: FakeProvider())
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            searched = await client.call_tool(
                "search_asset",
                {"request": {"task_id": task_id, "query": "learning", "asset_kind": "external_image"}},
            )
            assert searched.is_error is False
            assert searched.structured_content["candidates"][0]["id"] == candidate.id
            assert searched.structured_content["query_sha256"] != "learning"
            search_event = next(
                event for event in database.get_task_events(task_id) if event["type"] == "mcp_asset_search"
            )
            assert "learning" not in str(search_event["payload"])

            rerendered = await client.call_tool("rerender_video", {"request": {"task_id": task_id}})
            assert rerendered.is_error is False
            assert rerendered.structured_content["status"] == "rendering"
            assert len(calls) == 1

    run(scenario())


def test_mcp_replace_requires_audited_candidate_and_uses_review_validation(tmp_path: Path, monkeypatch) -> None:
    storage = configure_mcp_database(tmp_path, monkeypatch)
    task_id, _, _ = completed_task(storage)
    task_dir = storage / task_id
    candidate = MediaCandidate(
        id="candidate_audited",
        provider="mock",
        query="learning",
        asset_kind="external_image",
        source_url="https://example.test/audited.jpg",
        title="Audited learning visual",
        author_or_provider="test",
        license="test-only",
        mime_type="image/jpeg",
    )
    save_candidates(task_dir, [candidate])
    calls = []
    monkeypatch.setattr(main, "start_review_task", lambda *args: calls.append(args))

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            missing = await client.call_tool(
                "replace_asset",
                {"request": {"task_id": task_id, "animation_id": "animation_002", "candidate_id": "candidate_missing"}},
            )
            assert missing.is_error is True
            assert database.get_task(task_id)["status"] == "completed"

            replaced = await client.call_tool(
                "replace_asset",
                {"request": {"task_id": task_id, "animation_id": "animation_002", "candidate_id": candidate.id}},
            )
            assert replaced.is_error is False
            assert replaced.structured_content["status"] == "rendering"
            assert len(calls) == 1
            assert calls[0][4].animations[1].parameters.selected_candidate_id == candidate.id
            assert calls[0][4].media_assets == []
            assert "mcp_asset_replaced" in {event["type"] for event in database.get_task_events(task_id)}

    run(scenario())


def test_mcp_result_resource_returns_bytes_without_local_path(tmp_path: Path, monkeypatch) -> None:
    storage = configure_mcp_database(tmp_path, monkeypatch)
    task_id, _, _ = completed_task(storage)
    result_bytes = b"\x00\x00\x00\x18ftypmp42result"
    (storage / task_id / "result.mp4").write_bytes(result_bytes)

    async def scenario() -> None:
        async with Client(mcp_server.mcp, raise_exceptions=True) as client:
            download = await client.call_tool("download_result", {"request": {"task_id": task_id}})
            assert download.is_error is False
            assert download.structured_content["result_resource_uri"] == f"video://tasks/{task_id}/result"
            assert str(storage) not in str(download.structured_content)

            resource = await client.read_resource(f"video://tasks/{task_id}/result")
            assert len(resource.contents) == 1
            assert base64.b64decode(resource.contents[0].blob) == result_bytes

    run(scenario())
