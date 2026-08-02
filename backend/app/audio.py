import subprocess
from pathlib import Path

from .config import COMMAND_TIMEOUT_SECONDS
from .video import ensure_storage_path


class AudioExtractionError(RuntimeError):
    pass


class AudioService:
    def extract_wav(self, source: Path, destination: Path) -> Path:
        source = ensure_storage_path(source)
        destination = ensure_storage_path(destination)
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", str(destination),
            ], capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AudioExtractionError(f"Audio extraction failed: {exc}") from exc
        if result.returncode != 0 or not destination.is_file():
            raise AudioExtractionError(result.stderr.strip() or "Video has no usable audio track")
        return destination
