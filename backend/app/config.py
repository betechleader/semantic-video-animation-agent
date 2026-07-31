from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "storage"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 60
