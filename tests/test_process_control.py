from backend.app import process_control


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
