import subprocess
from pathlib import Path

import pytest

from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.quality import OutputQuality, QualityValidationError, validate_animation_safe_areas, verify_output_quality, verify_overlay_has_alpha
from backend.app.schemas import VideoMetadata


def source_metadata() -> VideoMetadata:
    return VideoMetadata(duration_seconds=5, width=320, height=568, frame_rate=30, video_codec="h264", audio_codec="aac", has_video=True, has_audio=True)


def test_safe_area_accepts_default_plan_and_rejects_overwide_keyword() -> None:
    plan = create_mock_plan(create_mock_transcript())
    validate_animation_safe_areas(plan, 320, 568)
    plan.animations[0].parameters.text = "a" * 80
    with pytest.raises(QualityValidationError, match="safe area"):
        validate_animation_safe_areas(plan, 320, 568)


def test_output_quality_rejects_metadata_mismatches(tmp_path: Path, monkeypatch) -> None:
    result = tmp_path / "result.mp4"
    result.touch()
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", tmp_path)
    monkeypatch.setattr("backend.app.quality._run", lambda _command: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr("backend.app.quality._probe_output", lambda _path: OutputQuality(5, 320, 568, 30, 150, False))
    with pytest.raises(QualityValidationError, match="audio"):
        verify_output_quality(result, source_metadata())
    monkeypatch.setattr("backend.app.quality._probe_output", lambda _path: OutputQuality(5, 640, 568, 30, 150, True))
    with pytest.raises(QualityValidationError, match="dimensions"):
        verify_output_quality(result, source_metadata())


def test_overlay_requires_alpha_channel(tmp_path: Path, monkeypatch) -> None:
    overlay = tmp_path / "animation.mov"
    overlay.touch()
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        "backend.app.quality._run",
        lambda _command: subprocess.CompletedProcess([], 0, '{"streams": [{"pix_fmt": "yuv422p12le"}]}', ""),
    )
    with pytest.raises(QualityValidationError, match="alpha"):
        verify_overlay_has_alpha(overlay)
