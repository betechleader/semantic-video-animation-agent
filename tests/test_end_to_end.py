import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.video import probe_video


def test_full_video_processing_pipeline(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=2:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], check=True, capture_output=True)

    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        response = client.post("/api/videos", files={"file": ("speech.mp4", source.read_bytes(), "video/mp4")})
        assert response.status_code == 201, response.text
        task_id = response.json()["task_id"]
        task = client.get(f"/api/videos/{task_id}").json()
        assert task["status"] == "completed"
        assert task["transcript"]["language"] == "zh"
        assert task["plan"]["animations"][0]["type"] == "keyword_pop"
        result = storage / task_id / "result.mp4"
        assert probe_video(result).has_video is True
        download = client.get(f"/api/videos/{task_id}/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("video/mp4")
