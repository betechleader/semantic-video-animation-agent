import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from .config import STORAGE_ROOT


class StorageService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or STORAGE_ROOT

    def _safe_path(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValueError("Path must be inside storage") from exc
        return resolved

    def task_directory(self, task_id: str) -> Path:
        UUID(task_id)
        return self._safe_path(self.root / task_id)

    def create_task_directory(self, task_id: str) -> Path:
        directory = self.task_directory(task_id)
        directory.mkdir(parents=True, exist_ok=False)
        return directory

    def remove_task_directory(self, task_id: str) -> None:
        directory = self.task_directory(task_id)
        if directory.exists():
            shutil.rmtree(directory)

    def cleanup_expired_tasks(self, retention_hours: int, now: datetime | None = None) -> list[str]:
        threshold = (now or datetime.now(timezone.utc)) - timedelta(hours=retention_hours)
        removed: list[str] = []
        for directory in self.root.iterdir() if self.root.exists() else []:
            if not directory.is_dir():
                continue
            try:
                UUID(directory.name)
            except ValueError:
                continue
            modified = datetime.fromtimestamp(directory.stat().st_mtime, tz=timezone.utc)
            if modified < threshold:
                self.remove_task_directory(directory.name)
                removed.append(directory.name)
        return removed
