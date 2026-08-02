import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import database, main
from backend.app.schemas import AnimationPlan


def test_api_marks_task_failed_when_planner_breaks_grounding_rules(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    database._engine = None
    database._engine_path = None
    database._session_factory = None
    source = tmp_path / "source.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=1:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
        "-c:v", "libx264", "-c:a", "aac", str(source),
    ], capture_output=True, check=True)

    def invalid_plan(_self, _transcript):
        return AnimationPlan.model_validate({"animations": [{
            "id": "animation_invalid", "type": "keyword_pop", "template_id": "keyword_pop_v1",
            "start_ms": 0, "end_ms": 500, "trigger_text": "invalid",
            "parameters": {"text": "invalid", "color": "#FFD400", "position": "top-right"},
        }]})

    monkeypatch.setattr("backend.app.workflow.MockAnimationPlanningProvider.plan", invalid_plan)
    with TestClient(main.app) as client:
        response = client.post("/api/videos", files={"file": ("speech.mp4", source.read_bytes(), "video/mp4")})
        assert response.status_code == 202
        task_id = response.json()["task_id"]
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            task = client.get(f"/api/videos/{task_id}").json()
            if task["status"] == "failed":
                break
            time.sleep(0.1)
    assert task["status"] == "failed"
    assert "fully contained" in task["error"]
