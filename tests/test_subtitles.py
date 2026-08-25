from pathlib import Path

from backend.app.mock_services import create_mock_transcript
from backend.app.mock_services import create_mock_plan
from backend.app.providers import TranscriptAnimationPlanningProvider
from backend.app.schemas import Transcript
from backend.app.subtitles import build_dynamic_subtitle_cues, generate_ass, resolve_local_font, validate_subtitle_layout, write_ass


def test_ass_contains_video_resolution_and_timestamped_dialogue(tmp_path: Path) -> None:
    ass = generate_ass(create_mock_transcript(), 320, 568)
    assert "PlayResX: 320" in ass
    assert "PlayResY: 568" in ass
    assert "Dialogue: 0,0:00:01.00,0:00:04.00" in ass
    destination = write_ass(create_mock_transcript(), tmp_path / "subtitles.ass", 320, 568)
    assert destination.read_text(encoding="utf-8-sig").startswith("[Script Info]")


def test_subtitle_layout_is_bounded() -> None:
    transcript = create_mock_transcript()
    assert validate_subtitle_layout(transcript, 320, 568) == []


def test_font_resolution_is_local_only(tmp_path: Path) -> None:
    font = tmp_path / "msyh.ttf"
    font.write_bytes(b"font")
    assert resolve_local_font(font_dirs=[tmp_path]) == font


def test_noto_alias_matches_installed_style_name(tmp_path: Path) -> None:
    font = tmp_path / "NotoSansSC-VF.ttf"
    font.write_bytes(b"font")
    assert resolve_local_font("Noto Sans CJK SC", font_dirs=[tmp_path]) == font


def test_dynamic_cues_keep_transcript_words_and_mark_planner_emphasis() -> None:
    transcript = create_mock_transcript()
    cues = build_dynamic_subtitle_cues(transcript, create_mock_plan(transcript))
    assert cues[0]["start_ms"] == transcript.segments[0].words[0].start_ms
    assert "".join(word["text"] for word in cues[0]["words"]) in transcript.full_text
    assert any(word["emphasized"] for cue in cues for word in cue["words"])


def test_dynamic_cue_keeps_short_complete_phrase_in_one_caption_window() -> None:
    text = "对于自媒体博主来说"
    transcript = Transcript.model_validate({
        "language": "zh", "full_text": text, "segments": [{
            "text": text, "start_ms": 0, "end_ms": 2500,
            "words": [
                {"text": character, "start_ms": index * 250, "end_ms": 2500 if index == len(text) - 1 else (index + 1) * 250}
                for index, character in enumerate(text)
            ],
        }],
    })
    plan = TranscriptAnimationPlanningProvider().plan(Transcript.model_validate({
        "language": "zh", "full_text": "创新性很重要", "segments": [{
            "text": "创新性很重要", "start_ms": 0, "end_ms": 2500,
            "words": [{"text": "创新性很重要", "start_ms": 0, "end_ms": 2500}],
        }],
    }))

    cues = build_dynamic_subtitle_cues(transcript, plan)

    assert len(cues) == 1
    assert "".join(word["text"] for word in cues[0]["words"]) == text
    assert cues[0]["start_ms"] == 0
    assert cues[0]["end_ms"] == 2500
