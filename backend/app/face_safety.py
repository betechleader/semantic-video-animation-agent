"""Local CPU face-safe placement for topic visuals.

Only OpenCV's bundled Haar cascade is used.  It produces transient bounding boxes,
not identities or embeddings, and no frame or detection leaves the task machine.
"""

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from .schemas import AnimationPlan, FaceRegion, MediaPlacement, VideoMetadata
from .subtitles import _layout_for
from .video import ensure_storage_path


_SAMPLE_INTERVAL_MS = 1_000
_MAX_SAMPLES = 120
_FACE_PADDING_RATIO = 0.05
_CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")
_SCALES = (1.0, 0.8, 0.64, 0.5)


class FaceSafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class _Rect:
    x: int
    y: int
    width: int
    height: int

    def intersects(self, other: "_Rect") -> bool:
        return self.x < other.x + other.width and self.x + self.width > other.x and self.y < other.y + other.height and self.y + self.height > other.y


def _sample_timestamps(duration_seconds: float) -> list[int]:
    duration_ms = max(0, round(duration_seconds * 1_000))
    interval = max(_SAMPLE_INTERVAL_MS, math.ceil(max(1, duration_ms) / _MAX_SAMPLES))
    timestamps = list(range(0, duration_ms + 1, interval))
    if not timestamps or timestamps[-1] != duration_ms:
        timestamps.append(duration_ms)
    return timestamps


def detect_face_regions(source: Path, metadata: VideoMetadata) -> list[FaceRegion]:
    """Sample source frames and return face boxes in original-video coordinates."""
    source = ensure_storage_path(source)
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - requirements make this an installation error
        raise FaceSafetyError("opencv-python-headless is required for local CPU face detection") from exc

    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    classifier = cv2.CascadeClassifier(str(cascade_path))
    if classifier.empty():
        raise FaceSafetyError("OpenCV local face cascade could not be loaded")
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise FaceSafetyError("OpenCV could not open the local source video for face detection")
    regions: list[FaceRegion] = []
    try:
        minimum = max(24, round(min(metadata.width, metadata.height) * 0.055))
        for timestamp_ms in _sample_timestamps(metadata.duration_seconds):
            capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            frame_height, frame_width = frame.shape[:2]
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = classifier.detectMultiScale(
                grayscale, scaleFactor=1.1, minNeighbors=5,
                minSize=(minimum, minimum),
            )
            scale_x = metadata.width / frame_width
            scale_y = metadata.height / frame_height
            for x, y, width, height in faces:
                regions.append(FaceRegion(
                    timestamp_ms=timestamp_ms,
                    x=max(0, round(x * scale_x)), y=max(0, round(y * scale_y)),
                    width=max(1, round(width * scale_x)), height=max(1, round(height * scale_y)),
                ))
    finally:
        capture.release()
    return regions


def _media_size(width: int) -> tuple[int, int]:
    size = max(112, min(300, round(width * 0.34)))
    return size, round(size * 1.28)


def _corner_rect(corner: str, scale: float, width: int, height: int) -> _Rect:
    base_width, base_height = _media_size(width)
    media_width, media_height = round(base_width * scale), round(base_height * scale)
    margin_x, margin_y = round(width * 0.05), round(height * 0.05)
    return _Rect(
        x=margin_x if corner.endswith("left") else width - margin_x - media_width,
        y=margin_y if corner.startswith("top") else height - margin_y - media_height,
        width=media_width,
        height=media_height,
    )


def _subtitle_rect(width: int, height: int) -> _Rect:
    layout = _layout_for(width, height)
    font_size = max(34, min(74, round(width / 12)))
    # Dynamic captions may show two outlined lines plus a phrase highlight.
    top = max(0, height - layout.margin_v - font_size * layout.max_lines - 24)
    return _Rect(0, top, width, height - top)


def _protected_subject_rect(face: FaceRegion, width: int, height: int) -> _Rect:
    """Protect the detected face plus its likely talking-head upper-body framing."""
    padding = max(16, round(min(width, height) * _FACE_PADDING_RATIO))
    left = max(0, round(face.x - face.width * 0.55) - padding)
    top = max(0, round(face.y - face.height * 0.45) - padding)
    right = min(width, round(face.x + face.width * 1.55) + padding)
    bottom = min(height, round(face.y + face.height * 3.2) + padding)
    return _Rect(left, top, max(1, right - left), max(1, bottom - top))


def _forbidden_regions(regions: list[FaceRegion], animation_start_ms: int, animation_end_ms: int, width: int, height: int) -> list[_Rect]:
    relevant = [region for region in regions if animation_start_ms - _SAMPLE_INTERVAL_MS <= region.timestamp_ms <= animation_end_ms + _SAMPLE_INTERVAL_MS]
    return [_subtitle_rect(width, height), *[_protected_subject_rect(face, width, height) for face in relevant]]


def choose_media_placements(plan: AnimationPlan, metadata: VideoMetadata) -> list[MediaPlacement]:
    """Select an unoccupied corner, shrink it when possible, otherwise skip it."""
    placements: list[MediaPlacement] = []
    for animation in plan.animations:
        if animation.type != "media_visual" or not animation.parameters.enabled:
            continue
        if animation.parameters.display_mode == "full_screen":
            placements.append(MediaPlacement(animation_id=animation.id, corner=None, scale=1, skipped=False, reason="full_screen"))
            continue
        forbidden = _forbidden_regions(plan.face_regions, animation.start_ms, animation.end_ms, metadata.width, metadata.height)
        selected: tuple[str, float] | None = None
        for scale in _SCALES:
            for corner in _CORNERS:
                candidate = _corner_rect(corner, scale, metadata.width, metadata.height)
                if not any(candidate.intersects(rectangle) for rectangle in forbidden):
                    selected = (corner, scale)
                    break
            if selected:
                break
        if selected:
            placements.append(MediaPlacement(animation_id=animation.id, corner=selected[0], scale=selected[1], skipped=False, reason="safe_corner"))
        else:
            placements.append(MediaPlacement(animation_id=animation.id, corner=None, scale=0, skipped=True, reason="no_safe_area"))
    return placements


def analyse_face_safe_areas(task_dir: Path, metadata: VideoMetadata, plan: AnimationPlan) -> AnimationPlan:
    """Detect local faces, derive placements, and persist a task-local audit report."""
    task_dir = ensure_storage_path(task_dir)
    regions = detect_face_regions(task_dir / "source.mp4", metadata)
    analysed = plan.model_copy(update={"face_regions": regions})
    placements = choose_media_placements(analysed, metadata)
    analysed = analysed.model_copy(update={"media_placements": placements})
    report = {
        "detector": "opencv-haarcascade-frontalface-default-local-cpu",
        "sample_interval_ms": _SAMPLE_INTERVAL_MS,
        "sampled_timestamps_ms": _sample_timestamps(metadata.duration_seconds),
        "face_regions": [region.model_dump() for region in regions],
        "protected_subject_regions": [
            {"timestamp_ms": region.timestamp_ms, **asdict(_protected_subject_rect(region, metadata.width, metadata.height))}
            for region in regions
        ],
        "media_placements": [placement.model_dump() for placement in placements],
        "subtitle_safe_region": asdict(_subtitle_rect(metadata.width, metadata.height)),
    }
    (task_dir / "face_safe_areas.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return analysed
