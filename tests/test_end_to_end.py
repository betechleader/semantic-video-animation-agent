import subprocess
import time
import json
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
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=5:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], check=True, capture_output=True)

    with TestClient(main.app) as client:
        assert client.get("/").status_code == 200
        response = client.post("/api/videos", files={"file": ("speech.mp4", source.read_bytes(), "video/mp4")})
        assert response.status_code == 202, response.text
        task_id = response.json()["task_id"]
        deadline = time.monotonic() + 120
        while True:
            task = client.get(f"/api/videos/{task_id}").json()
            if task["status"] in {"completed", "failed", "cancelled"} or time.monotonic() >= deadline:
                break
            time.sleep(0.25)
        assert task["status"] == "completed"
        assert task["transcript"]["language"] == "zh"
        assert [animation["type"] for animation in task["plan"]["animations"]] == ["keyword_pop", "media_visual"]
        media_manifest = json.loads((storage / task_id / "media_assets.json").read_text(encoding="utf-8"))
        assert media_manifest[0]["asset_kind"] == "generated_original"
        assert media_manifest[0]["local_path"].startswith("media-assets/")
        result = storage / task_id / "result.mp4"
        assert probe_video(result).has_video is True
        quality = json.loads((storage / task_id / "quality.json").read_text(encoding="utf-8"))
        assert quality["frame_count"] > 0
        assert quality["has_audio"] is True
        overlay_probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt", "-of", "json", str(storage / task_id / "animation.mov")], check=True, capture_output=True, text=True)
        assert "a" in json.loads(overlay_probe.stdout)["streams"][0]["pix_fmt"]
        download = client.get(f"/api/videos/{task_id}/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("video/mp4")
        review = client.post(f"/api/videos/{task_id}/review", json={"transcript": task["transcript"], "plan": task["plan"]})
        assert review.status_code == 202, review.text
        deadline = time.monotonic() + 120
        while True:
            reviewed_task = client.get(f"/api/videos/{task_id}").json()
            if reviewed_task["status"] in {"completed", "failed", "cancelled"} or time.monotonic() >= deadline:
                break
            time.sleep(0.25)
        assert reviewed_task["status"] == "completed"
        assert probe_video(result).has_video is True
        assert json.loads((storage / task_id / "quality.json").read_text(encoding="utf-8"))["width"] == 320
        events = client.get(f"/api/videos/{task_id}/events")
        assert "event: rendering" in events.text
        assert "event: review_rendering" in events.text
        assert "event: completed" in events.text
