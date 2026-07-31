from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORAGE_ROOT = PROJECT_ROOT / "storage"
RENDERER_ROOT = PROJECT_ROOT / "animation-renderer"
DATABASE_PATH = STORAGE_ROOT / "tasks.sqlite3"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 120
