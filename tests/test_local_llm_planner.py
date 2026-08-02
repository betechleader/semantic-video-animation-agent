import json

import pytest

from backend.app.mock_services import create_mock_transcript
from backend.app.providers import LocalLlmAnimationPlanningProvider


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self.content}}]}


def valid_plan() -> str:
    return json.dumps({"animations": [{"id": "animation_keyword", "type": "keyword_pop", "template_id": "keyword_pop_v1", "start_ms": 1000, "end_ms": 2500, "trigger_text": "结构化输出", "parameters": {"text": "结构化输出", "color": "#FFD400", "position": "top-right"}}], "semantic_segments": [{"id": "semantic_001", "text": "结构化输出", "start_ms": 1000, "end_ms": 2500, "intent": "emphasis", "keywords": ["结构化输出"]}]})


def test_local_llm_planner_calls_loopback_server_and_validates_response(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, json, timeout):
        captured.update(url=url, payload=json, timeout=timeout)
        return FakeResponse("```json\n" + valid_plan() + "\n```")

    monkeypatch.setattr("backend.app.providers.requests.post", fake_post)
    plan = LocalLlmAnimationPlanningProvider("qwen", "http://127.0.0.1:11434/v1", 12).plan(create_mock_transcript())
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["timeout"] == 12
    assert "Transcript JSON" in captured["payload"]["messages"][0]["content"]
    assert plan.semantic_segments[0].intent == "emphasis"


def test_local_llm_planner_rejects_nonlocal_endpoint() -> None:
    with pytest.raises(ValueError, match="loopback"):
        LocalLlmAnimationPlanningProvider("qwen", "https://example.com/v1")


def test_local_llm_planner_rejects_invalid_structured_output(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.providers.requests.post", lambda *args, **kwargs: FakeResponse('{"animations": []}'))
    with pytest.raises(RuntimeError, match="invalid animation plan"):
        LocalLlmAnimationPlanningProvider("qwen", "http://localhost:11434/v1").plan(create_mock_transcript())
