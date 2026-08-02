from .schemas import Animation, AnimationPlan, Transcript, TranscriptSegment, WordTiming


def create_mock_transcript() -> Transcript:
    return Transcript(
        language="zh",
        full_text="结构化输出非常重要",
        segments=[
            TranscriptSegment(
                text="结构化输出非常重要",
                start_ms=1000,
                end_ms=4000,
                words=[
                    WordTiming(text="结构化输出", start_ms=1000, end_ms=2500),
                    WordTiming(text="非常重要", start_ms=2500, end_ms=4000),
                ],
            )
        ],
    )


def create_mock_plan(transcript: Transcript) -> AnimationPlan:
    keyword = transcript.segments[0].words[0]
    segment = transcript.segments[0]
    return AnimationPlan(
        animations=[
            Animation(
                id="animation_001",
                type="keyword_pop",
                template_id="keyword_pop_v1",
                start_ms=keyword.start_ms,
                end_ms=min(keyword.end_ms, 3000),
                trigger_text=keyword.text,
                parameters={
                    "text": keyword.text,
                    "color": "#FFD400",
                    "position": "top-right",
                },
            ),
            Animation(
                id="animation_002",
                type="quote_card",
                template_id="quote_card_v1",
                start_ms=keyword.end_ms,
                end_ms=segment.end_ms,
                trigger_text=segment.words[1].text,
                parameters={
                    "headline": segment.words[1].text,
                    "body": segment.text,
                    "accent_color": "#6EE7B7",
                },
            ),
        ],
        semantic_segments=[],
    )
