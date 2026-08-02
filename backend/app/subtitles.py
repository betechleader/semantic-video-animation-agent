"""ASS subtitle generation and deterministic layout checks."""

from dataclasses import dataclass
import os
from pathlib import Path
import re

from .schemas import Transcript, TranscriptSegment


@dataclass(frozen=True)
class SubtitleLayout:
    max_chars_per_line: int
    max_lines: int = 2
    margin_v: int = 96


def _ass_time(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{milliseconds // 10:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\r", "").replace("\n", r"\N")


def _font_dirs() -> list[Path]:
    candidates = [Path(os.environ["WINDIR"]) / "Fonts"] if os.environ.get("WINDIR") else []
    candidates += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path(__file__).resolve().parents[2] / "assets" / "fonts"]
    return [path for path in candidates if path.is_dir()]


def resolve_local_font(font_name: str = "Microsoft YaHei", font_dirs: list[Path] | None = None) -> Path | None:
    """Return an installed local font file; never downloads or contacts a network."""
    aliases = {"Microsoft YaHei": ("msyh", "msyh.ttc", "msyhbd"), "Noto Sans CJK SC": ("NotoSansCJK",)}
    needles = aliases.get(font_name, (font_name,))
    for directory in font_dirs or _font_dirs():
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"} and any(needle.lower() in path.name.lower() for needle in needles):
                return path
    return None


def _layout_for(width: int, height: int) -> SubtitleLayout:
    # Chinese glyphs are approximately one em wide. Keep captions readable and
    # inside the central 84% safe width of both vertical and landscape videos.
    usable_width = max(240, round(width * 0.84))
    font_size = max(28, min(64, round(width / 18)))
    return SubtitleLayout(max_chars_per_line=max(8, usable_width // font_size))


def _wrap_text(text: str, layout: SubtitleLayout) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    chunks = [text[index:index + layout.max_chars_per_line] for index in range(0, len(text), layout.max_chars_per_line)]
    if len(chunks) <= layout.max_lines:
        return r"\N".join(chunks)
    # Do not emit a third line: distribute the remaining text to the second
    # line, which is preferable to overflowing the safe area.
    first = text[:layout.max_chars_per_line]
    return first + r"\N" + text[layout.max_chars_per_line:layout.max_chars_per_line * layout.max_lines]


def validate_subtitle_layout(transcript: Transcript, width: int, height: int) -> list[str]:
    """Return layout violations instead of silently producing clipped captions."""
    layout = _layout_for(width, height)
    violations: list[str] = []
    for index, segment in enumerate(transcript.segments):
        lines = _wrap_text(segment.text, layout).split(r"\N")
        if len(lines) > layout.max_lines:
            violations.append(f"segment {index} exceeds {layout.max_lines} lines")
        if any(not line.strip() for line in lines):
            violations.append(f"segment {index} contains an empty line")
        if segment.start_ms < 0 or segment.end_ms <= segment.start_ms:
            violations.append(f"segment {index} has an invalid time range")
    return violations


def generate_ass(transcript: Transcript, width: int, height: int, *, font_name: str = "Microsoft YaHei") -> str:
    layout = _layout_for(width, height)
    violations = validate_subtitle_layout(transcript, width, height)
    if violations:
        raise ValueError("Subtitle layout check failed: " + "; ".join(violations))
    font_size = max(28, min(64, round(width / 18)))
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding", f"Style: Default,{font_name},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,{layout.margin_v},1", "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for segment in transcript.segments:
        lines.append(f"Dialogue: 0,{_ass_time(segment.start_ms)},{_ass_time(segment.end_ms)},Default,,0,0,0,,{_escape_ass(_wrap_text(segment.text, layout))}")
    return "\n".join(lines) + "\n"


def write_ass(transcript: Transcript, destination: Path, width: int, height: int, *, font_name: str = "Microsoft YaHei") -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(generate_ass(transcript, width, height, font_name=font_name), encoding="utf-8-sig", newline="\n")
    return destination


def ffmpeg_filter_path(path: Path) -> str:
    """Escape a validated Windows/Unix path for libass's subtitles filter."""
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
