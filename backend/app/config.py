import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "storage"
RENDERER_ROOT = PROJECT_ROOT / "animation-renderer"
MODEL_ROOT = PROJECT_ROOT / "storage" / "models"
DATABASE_PATH = STORAGE_ROOT / "tasks.sqlite3"
ASR_CORRECTION_DICTIONARY_PATH = PROJECT_ROOT / "config" / "asr_corrections.json"
KNOWLEDGE_ASSET_ROOT = PROJECT_ROOT / "assets" / "knowledge"


@dataclass(frozen=True)
class Settings:
    max_upload_mb: int
    command_timeout_seconds: int
    task_retention_hours: int
    asr_provider: str
    asr_model: str
    asr_local_files_only: bool
    asr_correction_dictionary_path: Path
    planner_provider: str
    planner_model: str
    planner_base_url: str
    planner_timeout_seconds: int
    media_provider: str
    media_search_timeout_seconds: int
    media_max_download_mb: int
    pexels_api_key: str | None

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings() -> Settings:
    return Settings(
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "100")),
        command_timeout_seconds=int(os.getenv("COMMAND_TIMEOUT_SECONDS", "120")),
        task_retention_hours=int(os.getenv("TASK_RETENTION_HOURS", "168")),
        asr_provider=os.getenv("ASR_PROVIDER", "mock"),
        asr_model=os.getenv("ASR_MODEL", "small"),
        asr_local_files_only=os.getenv("ASR_LOCAL_FILES_ONLY", "true").lower() == "true",
        asr_correction_dictionary_path=Path(os.getenv("ASR_CORRECTION_DICTIONARY", str(ASR_CORRECTION_DICTIONARY_PATH))),
        planner_provider=os.getenv("PLANNER_PROVIDER", "mock"),
        planner_model=os.getenv("PLANNER_MODEL", "qwen2.5:7b-instruct"),
        planner_base_url=os.getenv("PLANNER_BASE_URL", "http://127.0.0.1:11434/v1"),
        planner_timeout_seconds=int(os.getenv("PLANNER_TIMEOUT_SECONDS", "60")),
        media_provider=os.getenv("MEDIA_PROVIDER", "mock").lower(),
        media_search_timeout_seconds=int(os.getenv("MEDIA_SEARCH_TIMEOUT_SECONDS", "20")),
        media_max_download_mb=int(os.getenv("MEDIA_MAX_DOWNLOAD_MB", "20")),
        pexels_api_key=os.getenv("PEXELS_API_KEY") or None,
    )


SETTINGS = load_settings()
MAX_UPLOAD_BYTES = SETTINGS.max_upload_bytes
COMMAND_TIMEOUT_SECONDS = SETTINGS.command_timeout_seconds
