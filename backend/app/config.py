import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "storage"
RENDERER_ROOT = PROJECT_ROOT / "animation-renderer"
DATABASE_PATH = STORAGE_ROOT / "tasks.sqlite3"


@dataclass(frozen=True)
class Settings:
    max_upload_mb: int
    command_timeout_seconds: int
    task_retention_hours: int

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings() -> Settings:
    return Settings(
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "100")),
        command_timeout_seconds=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "120")),
        task_retention_hours=int(os.getenv("TASK_RETENTION_HOURS", "168")),
    )


SETTINGS = load_settings()
MAX_UPLOAD_BYTES = SETTINGS.max_upload_bytes
COMMAND_TIMEOUT_SECONDS = SETTINGS.command_timeout_seconds
