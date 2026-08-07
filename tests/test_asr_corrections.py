from backend.app.asr_corrections import PhraseCorrectionRule, correct_transcript, load_phrase_corrections
from backend.app.config import ASR_CORRECTION_DICTIONARY_PATH
from backend.app.providers import TranscriptAnimationPlanningProvider
from backend.app.schemas import Transcript
from backend.app.subtitles import build_dynamic_subtitle_cues


def transcript_for(text: str, words: list[tuple[str, int, int]]) -> Transcript:
    return Transcript.model_validate({
        "language": "zh",
        "full_text": text,
        "segments": [{
            "text": text,
            "start_ms": words[0][1],
            "end_ms": words[-1][2],
            "words": [{"text": value, "start_ms": start, "end_ms": end} for value, start, end in words],
        }],
    })


def test_contextual_homophone_correction_preserves_existing_interval() -> None:
    raw = transcript_for("重新改写会姑娘的故事", [
        ("重新改写", 1000, 1800), ("会", 1800, 2000), ("姑", 2000, 2200), ("娘", 2200, 2400), ("的故事", 2400, 3000),
    ])
    corrected = correct_transcript(raw, [PhraseCorrectionRule("会姑娘", "灰姑娘", ("故事",))])

    assert corrected.full_text == "重新改写灰姑娘的故事"
    assert corrected.raw_asr.full_text == "重新改写会姑娘的故事"
    assert corrected.corrections[0].start_ms == 1800
    assert corrected.corrections[0].end_ms == 2400
    word = next(word for word in corrected.segments[0].words if word.text == "灰姑娘")
    assert (word.start_ms, word.end_ms) == (1800, 2400)


def test_book_title_correction_updates_subtitles_and_animation_plan() -> None:
    raw = transcript_for("最近看了心理学有生活这本书", [
        ("最近看了", 0, 800), ("心理学", 800, 1300), ("有", 1300, 1450), ("生活", 1450, 1800), ("这本书", 1800, 2600),
    ])
    corrected = correct_transcript(raw, [PhraseCorrectionRule("心理学有生活", "心理学与生活", ("书",))])
    plan = TranscriptAnimationPlanningProvider().plan(corrected)
    cues = build_dynamic_subtitle_cues(corrected, plan)

    assert corrected.full_text == "最近看了心理学与生活这本书"
    assert plan.animations[0].trigger_text == "心理学与生活"
    assert plan.animations[0].parameters.title == "心理学与生活"
    assert plan.animations[0].parameters.search_query == "book: Psychology and Life Richard J. Gerrig Philip G. Zimbardo"
    assert "".join(word["text"] for cue in cues for word in cue["words"]) == corrected.full_text


def test_configured_context_corrections_clean_observed_animation_copy_errors() -> None:
    raw = transcript_for("介绍了三种对抑提高创新性的方法", [
        ("介绍了", 0, 500), ("三种", 500, 900), ("对抑", 900, 1200),
        ("提高", 1200, 1600), ("创新性", 1600, 2200), ("的方法", 2200, 2800),
    ])

    corrected = correct_transcript(raw, load_phrase_corrections(ASR_CORRECTION_DICTIONARY_PATH))

    assert corrected.full_text == "介绍了三种可以提高创新性的方法"
    assert corrected.raw_asr.full_text == raw.full_text
