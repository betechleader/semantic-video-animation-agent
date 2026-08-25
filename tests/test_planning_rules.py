import pytest

from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.planning_rules import PlanningRuleError, validate_animation_plan
from backend.app.schemas import AnimationPlan


def plan_with(animations: list[dict], semantic_segments: list[dict] | None = None) -> AnimationPlan:
    return AnimationPlan.model_validate({"animations": animations, "semantic_segments": semantic_segments or []})


def keyword(identifier: str, start_ms: int, end_ms: int) -> dict:
    return {
        "id": identifier, "type": "keyword_pop", "template_id": "keyword_pop_v1",
        "start_ms": start_ms, "end_ms": end_ms, "trigger_text": "结构化输出",
        "parameters": {"text": "结构化输出", "color": "#FFD400", "position": "top-right"},
    }


def test_mock_plan_is_grounded_and_uses_the_shared_rules() -> None:
    transcript = create_mock_transcript()
    plan = create_mock_plan(transcript)
    assert validate_animation_plan(plan, transcript) is plan


@pytest.mark.parametrize(
    ("animations", "message"),
    [
        ([keyword("animation_outside", 900, 1300)], "fully contained"),
        ([keyword("animation_short", 1000, 1200)], "duration"),
        ([keyword("animation_001", 1000, 1800), keyword("animation_002", 1500, 2300)], "cannot overlap"),
        ([keyword("animation_001", 1000, 1300), keyword("animation_002", 1500, 1800), keyword("animation_003", 2000, 2300)], "density"),
    ],
)
def test_rules_reject_ungrounded_dense_or_conflicting_animations(animations: list[dict], message: str) -> None:
    with pytest.raises(PlanningRuleError, match=message):
        validate_animation_plan(plan_with(animations), create_mock_transcript())


def test_rules_reject_duplicate_ids_and_ungrounded_semantic_segments() -> None:
    with pytest.raises(PlanningRuleError, match="unique"):
        validate_animation_plan(plan_with([keyword("animation_same", 1000, 1500), keyword("animation_same", 2500, 3000)]), create_mock_transcript())
    with pytest.raises(PlanningRuleError, match="semantic_001"):
        validate_animation_plan(
            plan_with([keyword("animation_001", 1000, 1500)], [{
                "id": "semantic_001", "text": "结构化输出", "start_ms": 900, "end_ms": 1500,
                "intent": "emphasis", "keywords": ["结构化输出"],
            }]),
            create_mock_transcript(),
        )
