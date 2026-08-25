import sys
import types
from pathlib import Path

from backend.app.providers import FasterWhisperProvider


def test_faster_whisper_provider_converts_word_timestamps(monkeypatch, tmp_path: Path) -> None:
    class Word:
        def __init__(self, word, start, end):
            self.word, self.start, self.end = word, start, end

    class Segment:
        text, start, end = "结构化输出", 1.0, 2.5
        words = [Word("结构化", 1.0, 1.7), Word("输出", 1.7, 2.5)]

    class Info:
        language, language_probability = "zh", 0.98

    class Model:
        def __init__(self, *_args, **kwargs):
            assert kwargs["device"] == "cpu"
            assert kwargs["compute_type"] == "int8"
            assert kwargs["local_files_only"] is True

        def transcribe(self, *_args, **_kwargs):
            return iter([Segment()]), Info()

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    transcript = FasterWhisperProvider("small", tmp_path).transcribe(tmp_path / "audio.wav")
    assert transcript.language_confidence == 0.98
    assert transcript.segments[0].words[1].end_ms == 2500


def test_faster_whisper_provider_keeps_short_word_intervals_valid(monkeypatch, tmp_path: Path) -> None:
    class Word:
        word, start, end = "short", 12.4, 12.4004

    class Segment:
        text, start, end = "short", 12.4, 12.4004
        words = [Word()]

    class Info:
        language, language_probability = "zh", 0.98

    class Model:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return iter([Segment()]), Info()

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    transcript = FasterWhisperProvider("small", tmp_path).transcribe(tmp_path / "audio.wav")
    word = transcript.segments[0].words[0]
    assert (word.start_ms, word.end_ms) == (12400, 12401)
