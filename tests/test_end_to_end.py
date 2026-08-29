import subprocess
import time
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import main
from backend.app.agent_workflow import AGENT_NODES, AgentCheckpointStore
from backend.app.database import get_task_events
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
        response = client.post(
            "/api/videos",
            files={"file": ("speech.mp4", source.read_bytes(), "video/mp4")},
            data={"workflow_mode": "standard"},
        )
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
        assert media_manifest[0]["asset_kind"] == "generated_infographic"
        assert media_manifest[0]["provider"] == "original_infographic"
        assert media_manifest[0]["usage_start_ms"] < media_manifest[0]["usage_end_ms"]
        assert media_manifest[0]["local_path"].startswith("media-assets/")
        face_safety = json.loads((storage / task_id / "face_safe_areas.json").read_text(encoding="utf-8"))
        assert face_safety["detector"] == "opencv-haarcascade-frontalface-default-local-cpu"
        assert face_safety["sampled_timestamps_ms"] == [0, 1000, 2000, 3000, 4000, 5000]
        assert task["plan"]["media_placements"] == [{"animation_id": "animation_002", "corner": "top-left", "scale": 1.0, "skipped": False, "reason": "safe_corner"}]
        result = storage / task_id / "result.mp4"
        assert probe_video(result).has_video is True
        quality = json.loads((storage / task_id / "quality.json").read_text(encoding="utf-8"))
        assert quality["frame_count"] > 0
        assert quality["has_audio"] is True
        metrics = client.get(f"/api/videos/{task_id}/metrics")
        assert metrics.status_code == 200
        initial_metrics = metrics.json()
        assert initial_metrics["status"] == "completed"
        assert initial_metrics["trace_id_sha256"]
        assert set(initial_metrics["attempts"][0]["stages"]) == {
            "upload_probe", "audio_extraction", "asr", "asr_correction", "planning", "media_asset_acquisition", "media_safety_analysis",
            "remotion_render", "compositing", "quality_check",
        }
        assert initial_metrics["attempts"][0]["output_quality"]["width"] == 320
        remotion_props = json.loads((storage / task_id / "remotion_props.json").read_text(encoding="utf-8"))
        assert remotion_props["mediaAssets"][0]["data_uri"].startswith("data:image/svg+xml;base64,")
        assert remotion_props["subtitleCues"][0]["words"]
        overlay_probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=pix_fmt", "-of", "json", str(storage / task_id / "animation.mov")], check=True, capture_output=True, text=True)
        assert "a" in json.loads(overlay_probe.stdout)["streams"][0]["pix_fmt"]
        download = client.get(f"/api/videos/{task_id}/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("video/mp4")

        # A real review render must accept a disabled media visual even while
        # the submitted JSON still contains its stale audit and placement.
        reviewed_plan = task["plan"]
        reviewed_plan["animations"][1]["parameters"]["enabled"] = False
        review = client.post(f"/api/videos/{task_id}/review", json={"transcript": task["transcript"], "plan": reviewed_plan})
        assert review.status_code == 202, review.text
        deadline = time.monotonic() + 120
        while True:
            reviewed_task = client.get(f"/api/videos/{task_id}").json()
            if reviewed_task["status"] in {"completed", "failed", "cancelled"} or time.monotonic() >= deadline:
                break
            time.sleep(0.25)
        assert reviewed_task["status"] == "completed"
        assert reviewed_task["plan"]["media_assets"] == []
        assert reviewed_task["plan"]["media_placements"] == []
        assert probe_video(result).has_video is True
        assert json.loads((storage / task_id / "quality.json").read_text(encoding="utf-8"))["width"] == 320
        reviewed_metrics = client.get(f"/api/videos/{task_id}/metrics").json()
        assert reviewed_metrics["attempt_count"] == 2
        assert reviewed_metrics["attempts"][1]["kind"] == "review"
        assert reviewed_metrics["attempts"][1]["status"] == "completed"
        assert "upload_probe" not in reviewed_metrics["attempts"][1]["stages"]
        events = client.get(f"/api/videos/{task_id}/events")
        assert "event: rendering" in events.text
        assert "event: review_rendering" in events.text
        assert "event: completed" in events.text


def test_agent_mock_video_processing_pipeline(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    monkeypatch.setattr(main, "STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.STORAGE_ROOT", storage)
    monkeypatch.setattr("backend.app.database.DATABASE_PATH", storage / "tasks.sqlite3")
    source = tmp_path / "agent-source.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x568:d=5:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(source),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/videos",
            files={"file": ("agent-speech.mp4", source.read_bytes(), "video/mp4")},
            data={
                "workflow_mode": "agent",
                "processing_profile": "mock",
                "media_provider": "mock",
            },
        )
        assert response.status_code == 202, response.text
        task_id = response.json()["task_id"]
        deadline = time.monotonic() + 120
        while True:
            task = client.get(f"/api/videos/{task_id}").json()
            if task["status"] in {"completed", "failed", "cancelled"} or time.monotonic() >= deadline:
                break
            time.sleep(0.25)

        assert task["status"] == "completed", task.get("error")
        assert task["workflow_mode"] == "agent"
        assert task["processing_profile"] == "mock"
        assert task["media_provider"] == "mock"
        assert probe_video(storage / task_id / "result.mp4").has_video is True
        assert json.loads((storage / task_id / "quality.json").read_text(encoding="utf-8"))["has_audio"] is True

        checkpoint = AgentCheckpointStore.for_storage_root(storage).load(task_id)
        assert checkpoint is not None
        assert checkpoint["task_id"] == task_id
        assert checkpoint["next_node"] is None
        assert checkpoint["run_status"] == "completed"
        assert checkpoint["state"]["thread_id"] == task_id
        assert checkpoint["state"]["completed_nodes"] == list(AGENT_NODES)

        node_events = [
            event
            for event in get_task_events(task_id)
            if event["type"] == "agent_node"
        ]
        assert [
            (event["payload"]["node"], event["payload"]["status"])
            for event in node_events
        ] == [item for node in AGENT_NODES for item in ((node, "started"), (node, "completed"))]
        assert all("progress" not in event["payload"] for event in node_events)

        download = client.get(f"/api/videos/{task_id}/download")
        assert download.status_code == 200
        assert download.headers["content-type"].startswith("video/mp4")

        patch_preview = client.post(
            f"/api/videos/{task_id}/plan-patches/preview",
            json={"instruction": "前三秒更抓人"},
        )
        assert patch_preview.status_code == 201, patch_preview.text
        patch = patch_preview.json()
        operation_ids = [item["operation_id"] for item in patch["patch"]["operations"]]
        assert client.post(
            f"/api/videos/{task_id}/plan-patches/{patch['patch_id']}/approve",
            json={"operation_ids": operation_ids},
        ).status_code == 200
        apply_response = client.post(
            f"/api/videos/{task_id}/plan-patches/{patch['patch_id']}/apply"
        )
        assert apply_response.status_code == 202, apply_response.text
        deadline = time.monotonic() + 120
        while True:
            patched_task = client.get(f"/api/videos/{task_id}").json()
            if patched_task["status"] in {"completed", "failed", "cancelled"} or time.monotonic() >= deadline:
                break
            time.sleep(0.25)
        assert patched_task["status"] == "completed", patched_task.get("error")
        assert patched_task["plan"]["animations"][0]["selection_reason"] == "Natural-language request: stronger opening"
        assert probe_video(storage / task_id / "result.mp4").has_video is True
