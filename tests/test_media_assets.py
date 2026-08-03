import json

import pytest

from backend.app.media_assets import prepare_media_assets, renderer_media_assets
from backend.app.planning_rules import PlanningRuleError, validate_animation_plan
from backend.app.providers import TranscriptAnimationPlanningProvider
from backend.app.schemas import Transcript


def book_transcript() -> Transcript:
    return Transcript.model_validate({
        "language": "zh", "full_text": "\u4ecb\u7ecd\u300a\u5fc3\u7406\u5b66\u4e0e\u751f\u6d3b\u300b", "segments": [{
            "text": "\u4ecb\u7ecd\u300a\u5fc3\u7406\u5b66\u4e0e\u751f\u6d3b\u300b", "start_ms": 1000, "end_ms": 4000,
            "words": [{"text": "\u4ecb\u7ecd", "start_ms": 1000, "end_ms": 2000}, {"text": "\u4e66\u7c4d", "start_ms": 2000, "end_ms": 4000}],
        }],
    })


def test_rule_based_book_mention_uses_original_media_visual(tmp_path) -> None:
    transcript = book_transcript()
    raw_plan = TranscriptAnimationPlanningProvider().plan(transcript)
    visual = raw_plan.animations[0]
    assert visual.type == "media_visual"
    assert visual.parameters.title == "心理学与生活"
    assert visual.start_ms == 1000
    assert visual.end_ms == 3000

    plan = prepare_media_assets(tmp_path, raw_plan)
    assert validate_animation_plan(plan, transcript) is plan
    audit = plan.media_assets[0]
    assert audit.asset_kind == "generated_original"
    assert "commercial" in audit.license
    assert (tmp_path / audit.local_path).is_file()
    manifest = json.loads((tmp_path / "media_assets.json").read_text(encoding="utf-8"))
    assert manifest[0]["sha256"] == audit.sha256
    assert renderer_media_assets(tmp_path, plan)[0]["data_uri"].startswith("data:image/svg+xml;base64,")


def test_media_audit_rejects_changed_local_content(tmp_path) -> None:
    plan = prepare_media_assets(tmp_path, TranscriptAnimationPlanningProvider().plan(book_transcript()))
    path = tmp_path / plan.media_assets[0].local_path
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        renderer_media_assets(tmp_path, plan)


def test_rule_based_planner_normalizes_known_book_title_asr_variant() -> None:
    transcript = Transcript.model_validate({
        "language": "zh", "full_text": "\u300a\u5fc3\u7406\u5b66\u6709\u751f\u6d3b\u300b", "segments": [{
            "text": "\u300a\u5fc3\u7406\u5b66\u6709\u751f\u6d3b\u300b", "start_ms": 0, "end_ms": 2000,
            "words": [{"text": "\u4e66", "start_ms": 0, "end_ms": 2000}],
        }],
    })
    assert TranscriptAnimationPlanningProvider().plan(transcript).animations[0].parameters.title == "\u5fc3\u7406\u5b66\u4e0e\u751f\u6d3b"


def test_planning_rules_reject_duplicate_audit_metadata(tmp_path) -> None:
    raw_plan = TranscriptAnimationPlanningProvider().plan(book_transcript())
    generated = prepare_media_assets(tmp_path, raw_plan)
    invalid = generated.model_copy(update={"media_assets": generated.media_assets + generated.media_assets})
    with pytest.raises(PlanningRuleError, match="audit IDs must be unique"):
        validate_animation_plan(invalid, book_transcript())
