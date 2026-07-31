import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.schemas import VideoMetadata
from backend.app.video import VideoProbeError, parse_ffprobe_payload


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "STORAGE_ROOT", tmp_path / "storage")
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", tmp_path / "storage")
    return TestClient(main.app)


@pytest.fixture()
def sample_mp4(tmp_path: Path) -> Path:
    output = tmp_path / "sample.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", str(output),
    ], check=True, capture_output=True)
    return output


def test_parse_ffprobe_payload() -> None:
    metadata = parse_ffprobe_payload({"format": {"duration": "2.0"}, "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 568, "avg_frame_rate": "30/1"},
        {"codec_type": "audio", "codec_name": "aac"},
    ]})
    assert metadata == VideoMetadata(duration_seconds=2.0, width=320, height=568, frame_rate=30.0, video_codec="h264", audio_codec="aac", has_video=True, has_audio=True)


def test_rejects_missing_video_stream() -> None:
    with pytest.raises(VideoProbeError, match="video stream"):
        parse_ffprobe_payload({"format": {"duration": "2"}, "streams": []})


def test_upload_mp4_and_probe(client: TestClient, sample_mp4: Path) -> None:
    response = client.post("/api/videos", files={"file": ("speech.mp4", sample_mp4.read_bytes(), "video/mp4")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["metadata"]["width"] == 320
    assert (main.STORAGE_ROOT / body["task_id"] / "source.mp4").is_file()


def test_upload_rejects_non_mp4(client: TestClient) -> None:
    response = client.post("/api/videos", files={"file": ("speech.txt", b"not-video", "text/plain")})
    assert response.status_code == 400
