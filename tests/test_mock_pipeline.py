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


def test_mock_planner_produces_keyword_and_media_templates() -> None:
    plan = create_mock_plan(create_mock_transcript())
    keyword_pop, media_visual = plan.animations
    assert keyword_pop.type == "keyword_pop"
    assert keyword_pop.parameters.position == "top-right"
    assert keyword_pop.start_ms < keyword_pop.end_ms
    assert media_visual.type == "media_visual"
    assert media_visual.template_id == "media_visual_v1"


def test_animation_plan_rejects_invalid_ranges_unknown_fields_and_template_mismatches() -> None:
    with pytest.raises(ValidationError):
        AnimationPlan.model_validate({"animations": [{
            "id": "animation_001", "type": "keyword_pop", "template_id": "keyword_pop_v1",
            "start_ms": 2000, "end_ms": 1000, "trigger_text": "词",
            "parameters": {"text": "词", "color": "#FFD400", "position": "top-right"},
        }]})
    with pytest.raises(ValidationError):
        KeywordPopParameters(text="词", color="yellow", position="top-right", extra=True)
    with pytest.raises(ValidationError, match="quote_card requires"):
        AnimationPlan.model_validate({"animations": [{
            "id": "animation_002", "type": "quote_card", "template_id": "keyword_pop_v1",
            "start_ms": 1000, "end_ms": 2000, "trigger_text": "词",
            "parameters": {"headline": "词", "body": "正文", "accent_color": "#6EE7B7"},
        }]})
