"""Configurable post-ASR Chinese phrase correction without invented timing."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .schemas import RawAsrTranscript, Transcript, TranscriptCorrection, TranscriptSegment, WordTiming


@dataclass(frozen=True)
class PhraseCorrectionRule:
    source: str
    target: str
    context_any: tuple[str, ...] = ()


def load_phrase_corrections(path: Path) -> list[PhraseCorrectionRule]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"ASR correction dictionary could not be loaded: {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("ASR correction dictionary must contain a JSON list")
    rules: list[PhraseCorrectionRule] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not isinstance(item.get("source"), str) or not isinstance(item.get("target"), str):
            raise RuntimeError(f"ASR correction dictionary item {index} must contain source and target strings")
        contexts = item.get("context_any", [])
        if not isinstance(contexts, list) or not all(isinstance(value, str) and value for value in contexts):
            raise RuntimeError(f"ASR correction dictionary item {index} context_any must be a string list")
        if not item["source"] or not item["target"]:
            raise RuntimeError(f"ASR correction dictionary item {index} source and target cannot be empty")
        rules.append(PhraseCorrectionRule(item["source"], item["target"], tuple(contexts)))
    return sorted(rules, key=lambda rule: len(rule.source), reverse=True)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _replace_word_span(words: list[WordTiming], source: str, target: str) -> tuple[list[WordTiming], int, int] | None:
    """Replace one occurrence, merging its existing word intervals when needed."""
    values = [_compact(word.text) for word in words]
    joined = "".join(values)
    offset = joined.find(_compact(source))
    if offset < 0:
        return None
    match_end = offset + len(_compact(source))
    cursor = 0
    first = last = None
    first_offset = last_offset = 0
    for index, value in enumerate(values):
        word_end = cursor + len(value)
        if first is None and word_end > offset:
            first, first_offset = index, offset - cursor
        if cursor < match_end <= word_end:
            last, last_offset = index, match_end - cursor
            break
        cursor = word_end
    if first is None or last is None:
        return None
    prefix = values[first][:first_offset]
    suffix = values[last][last_offset:]
    replacement = WordTiming(
        text=prefix + target + suffix,
        start_ms=words[first].start_ms,
        end_ms=words[last].end_ms,
    )
    return words[:first] + [replacement] + words[last + 1 :], replacement.start_ms, replacement.end_ms


def correct_transcript(transcript: Transcript, rules: list[PhraseCorrectionRule]) -> Transcript:
    """Apply contextual phrase rules before planning and keep the raw ASR snapshot."""
    raw = transcript.raw_asr or RawAsrTranscript(
        language=transcript.language,
        language_confidence=transcript.language_confidence,
        full_text=transcript.full_text,
        segments=transcript.segments,
    )
    segments = [segment.model_copy(deep=True) for segment in transcript.segments]
    corrections = list(transcript.corrections)
    for segment_index, segment in enumerate(segments):
        nearby = "".join(item.text for item in segments[max(0, segment_index - 1) : segment_index + 2])
        text = segment.text
        words = list(segment.words)
        for rule in rules:
            if rule.context_any and not any(token in nearby for token in rule.context_any):
                continue
            while rule.source in text:
                replaced = _replace_word_span(words, rule.source, rule.target)
                if replaced is None:
                    break
                words, start_ms, end_ms = replaced
                text = text.replace(rule.source, rule.target, 1)
                corrections.append(TranscriptCorrection(
                    source=rule.source,
                    target=rule.target,
                    segment_index=segment_index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    kind="dictionary",
                ))
        segments[segment_index] = TranscriptSegment(
            text=text,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            words=words,
        )
    return transcript.model_copy(update={
        "full_text": "".join(segment.text for segment in segments),
        "segments": segments,
        "raw_asr": raw,
        "corrections": corrections,
    })


def normalize_review_transcript(submitted: Transcript, stored: Transcript) -> tuple[Transcript, bool]:
    """Make reviewer text authoritative while reusing only submitted ASR intervals."""
    segments: list[TranscriptSegment] = []
    corrections = list(stored.corrections)
    changed = len(submitted.segments) != len(stored.segments)
    for index, segment in enumerate(submitted.segments):
        old = stored.segments[index] if index < len(stored.segments) else None
        words = list(segment.words)
        word_text = _compact("".join(word.text for word in words))
        segment_text = _compact(segment.text)
        if word_text != segment_text:
            start_ms = words[0].start_ms
            end_ms = words[-1].end_ms
            words = [WordTiming(text=segment.text, start_ms=start_ms, end_ms=end_ms)]
        if old is None or segment.text != old.text or words != old.words:
            changed = True
            corrections.append(TranscriptCorrection(
                source=old.text if old else segment.text,
                target=segment.text,
                segment_index=index,
                start_ms=words[0].start_ms,
                end_ms=words[-1].end_ms,
                kind="manual",
            ))
        segments.append(segment.model_copy(update={"words": words}))
    normalized = submitted.model_copy(update={
        "full_text": "".join(segment.text for segment in segments),
        "segments": segments,
        "raw_asr": stored.raw_asr,
        "corrections": corrections,
    })
    if normalized.full_text != stored.full_text:
        changed = True
    return normalized, changed
