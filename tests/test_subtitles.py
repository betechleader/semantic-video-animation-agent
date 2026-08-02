from pathlib import Path

from backend.app.mock_services import create_mock_transcript
from backend.app.subtitles import generate_ass, resolve_local_font, validate_subtitle_layout, write_ass


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
