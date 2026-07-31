import pytest
from pydantic import ValidationError

from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.schemas import AnimationPlan, KeywordPopParameters


def test_mock_asr_returns_valid_chinese_timestamped_transcript() -> None:
    transcript = create_mock_transcript()
    assert transcript.language == "zh"
    assert transcript.full_text == "结构化输出非常重要"
    assert transcript.segments[0].words[0].start_ms == 1000
    assert transcript.segments[0].words[1].end_ms == 4000


def test_mock_planner_returns_valid_keyword_pop_plan() -> None:
    plan = create_mock_plan(create_mock_transcript())
    animation = plan.animations[0]
    assert animation.type == "keyword_pop"
    assert animation.parameters.position == "top-right"
    assert animation.start_ms < animation.end_ms


def test_animation_plan_rejects_invalid_ranges_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnimationPlan.model_validate({"animations": [{
            "id": "animation_001", "type": "keyword_pop", "template_id": "keyword_pop_v1",
            "start_ms": 2000, "end_ms": 1000, "trigger_text": "词",
            "parameters": {"text": "词", "color": "#FFD400", "position": "top-right"},
        }]})
    with pytest.raises(ValidationError):
        KeywordPopParameters(text="词", color="yellow", position="top-right", extra=True)
