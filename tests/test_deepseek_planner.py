from __future__ import annotations

import json
import logging
import traceback
from dataclasses import replace
from pathlib import Path

import pytest
import requests

from backend.app import workflow_services
from backend.app.agent_tools import PlanningToolInput, invoke_planning_tool
from backend.app.agent_trace import AgentTrace
from backend.app.config import load_settings
from backend.app.mock_services import create_mock_transcript
from backend.app.providers import (
    DEEPSEEK_CHAT_COMPLETIONS_ENDPOINT,
    DeepSeekAnimationPlanningProvider,
    LocalLlmAnimationPlanningProvider,
    MockAnimationPlanningProvider,
    TranscriptAnimationPlanningProvider,
)


class FakeResponse:
    def __init__(self, content: object) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self.content}}]}


class HttpFailureResponse:
    def __init__(self, status_code: int, unsafe_message: str) -> None:
        self.status_code = status_code
        self.unsafe_message = unsafe_message

    def raise_for_status(self) -> None:
        raise requests.HTTPError(self.unsafe_message)


def valid_plan() -> str:
    return json.dumps(
        {
            "animations": [
                {
                    "id": "animation_keyword",
                    "type": "keyword_pop",
                    "template_id": "keyword_pop_v1",
                    "start_ms": 1000,
                    "end_ms": 2500,
                    "trigger_text": "结构化输出",
                    "parameters": {
                        "text": "结构化输出",
                        "color": "#FFD400",
                        "position": "top-right",
                    },
                }
            ],
            "semantic_segments": [
                {
                    "id": "semantic_001",
                    "text": "结构化输出",
                    "start_ms": 1000,
                    "end_ms": 2500,
                    "intent": "emphasis",
                    "keywords": ["结构化输出"],
                }
            ],
        },
        ensure_ascii=False,
    )


def test_deepseek_planner_is_fully_offline_mocked_and_uses_only_official_endpoint(
    monkeypatch,
) -> None:
    secret = "deepseek-test-secret-never-print"
    captured: dict = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("PLANNER_API_KEY", "must-not-be-used-either")

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse("```json\n" + valid_plan() + "\n```")

    monkeypatch.setattr("backend.app.providers.requests.post", fake_post)
    provider = DeepSeekAnimationPlanningProvider("deepseek-v4-flash", 17)
    plan = provider.plan(create_mock_transcript())

    assert captured["url"] == DEEPSEEK_CHAT_COMPLETIONS_ENDPOINT
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == f"Bearer {secret}"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["timeout"] == 17
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert secret not in json.dumps(captured["payload"], ensure_ascii=False)
    assert secret not in repr(provider)
    assert secret not in repr(provider.__dict__)
    assert secret not in repr(load_settings())
    assert plan.animations[0].trigger_text == "结构化输出"


def test_deepseek_requires_its_named_environment_key_without_network(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-key")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("network call must not occur without DEEPSEEK_API_KEY")

    monkeypatch.setattr("backend.app.providers.requests.post", fail_if_called)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY is required"):
        DeepSeekAnimationPlanningProvider().plan_candidate(create_mock_transcript())


def test_deepseek_secret_is_absent_from_exception_log_tool_output_and_agent_trace(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    secret = "deepseek-sensitive-value-for-redaction-test"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    def fake_post(*args, **kwargs):
        raise requests.RequestException(f"upstream failure accidentally included {secret}")

    monkeypatch.setattr("backend.app.providers.requests.post", fake_post)
    provider = DeepSeekAnimationPlanningProvider()

    caplog.set_level(logging.DEBUG)
    with pytest.raises(RuntimeError) as captured:
        provider.plan_candidate(create_mock_transcript())
    rendered_exception = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert str(captured.value) == "DeepSeek planning request failed (request_error)"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert secret not in repr(captured.value)
    assert secret not in rendered_exception
    assert secret not in caplog.text

    tool_output = invoke_planning_tool(
        PlanningToolInput(transcript=create_mock_transcript(), repair_attempt=0),
        lambda value: provider.plan_candidate(value.transcript),
        planner_id="deepseek",
        model_id="deepseek-v4-flash",
    )
    encoded_tool_output = tool_output.model_dump_json()
    assert tool_output.violations[0].message == "planner call failed (RuntimeError)"
    assert secret not in encoded_tool_output

    task_id = "deepseek-safe-trace"
    task_dir = tmp_path / task_id
    trace = AgentTrace(task_dir, task_id)
    trace.append(
        "tool_call",
        node="planning",
        status="failed",
        error_category="planner_error",
        violations=[item.model_dump() for item in tool_output.violations],
        planner={"planner_id": "deepseek", "model_id": "deepseek-v4-flash"},
    )
    assert secret not in trace.path.read_text(encoding="utf-8")


def test_deepseek_http_failure_keeps_only_safe_status_category(monkeypatch) -> None:
    secret = "deepseek-http-secret"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    monkeypatch.setattr(
        "backend.app.providers.requests.post",
        lambda *args, **kwargs: HttpFailureResponse(
            401,
            f"unsafe response and authorization data: {secret}",
        ),
    )

    with pytest.raises(RuntimeError) as captured:
        DeepSeekAnimationPlanningProvider().plan_candidate(create_mock_transcript())
    rendered = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert str(captured.value) == "DeepSeek planning request failed (http_401)"
    assert captured.value.__context__ is None
    assert secret not in rendered


def test_deepseek_client_failure_keeps_only_safe_exception_type(monkeypatch) -> None:
    secret = "deepseek-client-secret"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    def fake_post(*args, **kwargs):
        raise UnicodeEncodeError("latin-1", secret, 0, 1, secret)

    monkeypatch.setattr("backend.app.providers.requests.post", fake_post)
    with pytest.raises(RuntimeError) as captured:
        DeepSeekAnimationPlanningProvider().plan_candidate(create_mock_transcript())
    rendered = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert str(captured.value) == (
        "DeepSeek planning request failed (client_unicodeencodeerror)"
    )
    assert captured.value.__context__ is None
    assert secret not in rendered


def test_deepseek_invalid_untrusted_response_is_safely_summarized(
    monkeypatch,
) -> None:
    secret = "deepseek-response-secret"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "request-key")
    monkeypatch.setattr(
        "backend.app.providers.requests.post",
        lambda *args, **kwargs: FakeResponse(secret),
    )

    with pytest.raises(RuntimeError) as captured:
        DeepSeekAnimationPlanningProvider().plan_candidate(create_mock_transcript())
    rendered = "".join(
        traceback.format_exception(
            type(captured.value), captured.value, captured.value.__traceback__
        )
    )
    assert str(captured.value) == "DeepSeek returned invalid JSON"
    assert captured.value.__context__ is None
    assert secret not in rendered


def test_provider_resolution_adds_deepseek_without_changing_existing_profiles(
    monkeypatch,
) -> None:
    settings = replace(
        workflow_services.SETTINGS,
        planner_provider="deepseek",
        deepseek_model="deepseek-v4-flash",
    )
    monkeypatch.setattr(workflow_services, "SETTINGS", settings)

    configured = workflow_services.resolve_planning_provider("configured")
    assert isinstance(configured, DeepSeekAnimationPlanningProvider)
    assert configured.model == "deepseek-v4-flash"
    assert isinstance(
        workflow_services.resolve_planning_provider("mock"),
        MockAnimationPlanningProvider,
    )
    assert isinstance(
        workflow_services.resolve_planning_provider("real"),
        TranscriptAnimationPlanningProvider,
    )

    local_settings = replace(settings, planner_provider="local_llm")
    monkeypatch.setattr(workflow_services, "SETTINGS", local_settings)
    assert isinstance(
        workflow_services.resolve_planning_provider("configured"),
        LocalLlmAnimationPlanningProvider,
    )


def test_agent_deepseek_planning_keeps_repair_protocol_and_safe_identifiers(
    monkeypatch,
) -> None:
    secret = "deepseek-agent-secret"
    captured: dict = {}
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)
    settings = replace(
        workflow_services.SETTINGS,
        planner_provider="deepseek",
        deepseek_model="deepseek-v4-flash",
    )
    monkeypatch.setattr(workflow_services, "SETTINGS", settings)

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        return FakeResponse(valid_plan())

    monkeypatch.setattr("backend.app.providers.requests.post", fake_post)
    result = workflow_services.plan_agent_candidate(
        PlanningToolInput(
            transcript=create_mock_transcript(),
            director_instruction="前三秒更抓人",
            repair_attempt=1,
            violations=[
                {
                    "code": "planning_rule",
                    "path": [],
                    "message": "duration is invalid",
                }
            ],
        ),
        processing_profile="configured",
        media_provider="mock",
    )

    prompt = captured["payload"]["messages"][0]["content"]
    assert result.planner_id == "deepseek"
    assert result.model_id == "deepseek-v4-flash"
    assert result.candidate is not None
    assert result.candidate["media_provider"] == "mock"
    assert "前三秒更抓人" in prompt
    assert '"code": "planning_rule"' in prompt
    assert "Repair attempt 1" in prompt
    assert secret not in result.model_dump_json()
