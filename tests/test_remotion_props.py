import json
from pathlib import Path

from backend.app.processing import remotion_render_command, write_remotion_props


def test_large_remotion_props_are_written_to_a_file_not_the_command_line(tmp_path: Path, monkeypatch) -> None:
    storage = tmp_path / "storage"
    task_dir = storage / "task"
    task_dir.mkdir(parents=True)
    monkeypatch.setattr("backend.app.video.STORAGE_ROOT", storage)
    payload = {"mediaAssets": [{"data_uri": "data:image/svg+xml;base64," + "a" * 40_000}]}

    props_file = write_remotion_props(task_dir / "remotion_props.json", payload)
    command = remotion_render_command(task_dir / "animation.mov", props_file)

    assert len(json.dumps(payload)) > 32_767
    assert json.loads(props_file.read_text(encoding="utf-8")) == payload
    assert f"--props={props_file}" in command
    assert all("a" * 1_000 not in argument for argument in command)
