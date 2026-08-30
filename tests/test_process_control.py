import pytest

from backend.app import process_control, processing


class RunningProcess:
    pid = 1234

    def poll(self):
        return None


def test_cancellation_terminates_windows_process_tree(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(process_control.subprocess, "CREATE_NEW_PROCESS_GROUP", 1, raising=False)
    monkeypatch.setattr(process_control.subprocess, "run", lambda command, **_kwargs: commands.append(command))
    registry = process_control.ProcessRegistry()
    process = RunningProcess()
    registry.register("task-1", process)  # type: ignore[arg-type]

    assert registry.cancel("task-1")
    assert commands == [["taskkill", "/PID", "1234", "/T", "/F"]]


def test_external_command_observes_persistent_cancellation_while_running(monkeypatch) -> None:
    class FakeProcess:
        pid = 4321
        returncode = 0

        def poll(self):
            return None

        def communicate(self, timeout=None):
            return "", ""

    cancelled: list[str] = []
    monkeypatch.setattr(processing.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())
    monkeypatch.setattr(processing, "is_cancellation_requested", lambda _task_id: True)
    monkeypatch.setattr(processing.process_registry, "cancel", lambda task_id: cancelled.append(task_id) or True)

    with pytest.raises(processing.ProcessingCancelled):
        processing._run(["fake-command"], task_id="persistent-task")
    assert cancelled == ["persistent-task"]
