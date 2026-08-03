import json

from backend.app.face_safety import analyse_face_safe_areas, choose_media_placements
from backend.app.mock_services import create_mock_plan, create_mock_transcript
from backend.app.schemas import FaceRegion, VideoMetadata


def metadata() -> VideoMetadata:
    return VideoMetadata(duration_seconds=5, width=320, height=568, frame_rate=30, video_codec="h264", audio_codec="aac", has_video=True, has_audio=True)


def test_media_visual_moves_to_the_other_safe_top_corner_when_a_face_blocks_default() -> None:
    plan = create_mock_plan(create_mock_transcript()).model_copy(update={
        "face_regions": [FaceRegion(timestamp_ms=3_000, x=8, y=8, width=70, height=90)],
    })
    placement = choose_media_placements(plan, metadata())[0]
    assert placement.animation_id == "animation_002"
    assert placement.corner == "top-right"
    assert placement.scale == 1
    assert placement.skipped is False


def test_media_visual_skips_when_face_and_subtitle_safe_zone_leave_no_corner() -> None:
    plan = create_mock_plan(create_mock_transcript()).model_copy(update={
        "face_regions": [FaceRegion(timestamp_ms=3_000, x=0, y=0, width=320, height=568)],
    })
    placement = choose_media_placements(plan, metadata())[0]
    assert placement.skipped is True
    assert placement.corner is None
    assert placement.scale == 0
    assert placement.reason == "no_safe_area"


def test_analysis_writes_only_local_coordinate_report_and_derived_placement(tmp_path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    task_dir = storage / "task"
    task_dir.mkdir(parents=True)
    (task_dir / "source.mp4").touch()
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.face_safety.detect_face_regions", lambda _source, _metadata: [
        FaceRegion(timestamp_ms=3_000, x=8, y=8, width=70, height=90),
    ])
    analysed = analyse_face_safe_areas(task_dir, metadata(), create_mock_plan(create_mock_transcript()))
    assert analysed.media_placements[0].corner == "top-right"
    report = json.loads((task_dir / "face_safe_areas.json").read_text(encoding="utf-8"))
    assert report["detector"].endswith("local-cpu")
    assert report["face_regions"] == [{"timestamp_ms": 3000, "x": 8, "y": 8, "width": 70, "height": 90}]
    assert report["protected_subject_regions"][0]["height"] > report["face_regions"][0]["height"]
