import subprocess
import threading


class ProcessRegistry:
    """Tracks the active external process for each task and terminates its process tree."""

    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()

    def register(self, task_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._processes[task_id] = process

    def unregister(self, task_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            if self._processes.get(task_id) is process:
                self._processes.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            process = self._processes.get(task_id)
        if process is None or process.poll() is not None:
            return False
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        else:
            process.terminate()
        return True


process_registry = ProcessRegistry()
