"""ASS subtitle generation and deterministic layout checks."""

from dataclasses import dataclass
import base64
import os
from pathlib import Path
import re

from .schemas import AnimationPlan, Transcript, TranscriptSegment


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
    windows_root = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    candidates = [Path(windows_root) / "Fonts", Path(r"C:\Windows\Fonts")]
    candidates += [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"), Path(__file__).resolve().parents[2] / "assets" / "fonts"]
    return [path for path in candidates if path.is_dir()]


def resolve_local_font(font_name: str = "Microsoft YaHei", font_dirs: list[Path] | None = None) -> Path | None:
    """Return an installed local font file; never downloads or contacts a network."""
    aliases = {"Microsoft YaHei": ("msyh", "msyh.ttc", "msyhbd"), "Noto Sans CJK SC": ("NotoSansCJK", "NotoSansSC")}
    needles = aliases.get(font_name, (font_name,))
    for directory in font_dirs or _font_dirs():
        for path in sorted(directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".ttf", ".otf", ".ttc"} and any(needle.lower() in path.name.lower() for needle in needles):
                return path
    return None


def renderer_font_data_uri(font_name: str = "Noto Sans CJK SC") -> str | None:
    """Embed an installed font in render props so headless Chromium has CJK glyphs.

    This avoids a browser-side network font request and keeps the font out of
    the Windows command line. It is intentionally task-local render input, not
    copied into the output or any metrics artifact.
    """
    path = resolve_local_font(font_name) or resolve_local_font("Microsoft YaHei")
    if path is None:
        return None
    mime_type = "font/ttf" if path.suffix.lower() == ".ttf" else "font/collection"
    return f"data:{mime_type};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


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


def _subtitle_normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text).lower()


def build_dynamic_subtitle_cues(transcript: Transcript, plan: AnimationPlan) -> list[dict]:
    """Build short phrase cues with word-level emphasis for the Remotion overlay.

    Captions remain transcript-derived.  Planner triggers only influence the
    appearance of matching words; they never create new spoken text.
    """
    emphasis_triggers = {
        _subtitle_normalize(animation.trigger_text)
        for animation in plan.animations
        if animation.type in {"keyword_pop", "quote_card", "info_graphic"}
    }
    cues: list[dict] = []
    max_phrase_chars = 15
    for segment in transcript.segments:
        phrase_words = []
        phrase_chars = 0
        for word in segment.words:
            clean = word.text.strip()
            if not clean:
                continue
            normalized = _subtitle_normalize(clean)
            emphasized = bool(normalized and any(normalized in trigger or trigger in normalized for trigger in emphasis_triggers))
            phrase_words.append({
                "text": clean, "start_ms": word.start_ms, "end_ms": word.end_ms, "emphasized": emphasized,
            })
            phrase_chars += len(normalized or clean)
            duration = word.end_ms - phrase_words[0]["start_ms"]
            if phrase_chars >= max_phrase_chars or duration >= 1_600:
                cues.append({
                    "start_ms": phrase_words[0]["start_ms"], "end_ms": phrase_words[-1]["end_ms"], "words": phrase_words,
                })
                phrase_words, phrase_chars = [], 0
        if phrase_words:
            cues.append({
                "start_ms": phrase_words[0]["start_ms"], "end_ms": phrase_words[-1]["end_ms"], "words": phrase_words,
            })
    return cues


def ffmpeg_filter_path(path: Path) -> str:
    """Escape a validated Windows/Unix path for libass's subtitles filter."""
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
