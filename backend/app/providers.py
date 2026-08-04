import json
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import requests
from pydantic import ValidationError

from .mock_services import create_mock_plan, create_mock_transcript
from .planning_rules import PlanningRuleError, validate_animation_plan
from .schemas import AnimationPlan, Transcript


class SpeechRecognitionProvider(Protocol):
    def transcribe(self, audio_path: Path) -> Transcript: ...


class AnimationPlanningProvider(Protocol):
    def plan(self, transcript: Transcript) -> AnimationPlan: ...


class MockSpeechRecognitionProvider:
    def transcribe(self, _audio_path: Path) -> Transcript:
        return create_mock_transcript()


class MockAnimationPlanningProvider:
    def plan(self, transcript: Transcript) -> AnimationPlan:
        return create_mock_plan(transcript)


class TranscriptAnimationPlanningProvider:
    """Offline planner that anchors readable highlights to real ASR segments."""

    _minimum_gap_ms = 5_000
    _maximum_duration_ms = 2_000

    _maximum_keyword_characters = 18

    _emphasis_patterns = (
        r"三种[^，。]{0,12}创新性[^，。]{0,8}方法",
        r"第一个[^，。]{0,14}", r"第二个[^，。]{0,14}", r"第三个[^，。]{0,14}",
        r"接触各种各样的文化", r"两种不同文化", r"设想未来", r"一年之后",
        r"更高的创新性", r"更加好的创新性", r"研究发现", r"创新性",
    )

    @classmethod
    def _keyword(cls, text: str) -> str:
        cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
        # The renderer wraps up to three lines. Keeping a meaningful short
        # phrase prevents the old six-character hard cut (for example,
        # "对于自媒体博" instead of "对于自媒体博主来说").
        return (cleaned or text.strip())[:cls._maximum_keyword_characters]

    @classmethod
    def _meaningful_phrase(cls, text: str) -> str:
        compact = re.sub(r"\s+", "", text)
        for pattern in cls._emphasis_patterns:
            match = re.search(pattern, compact)
            if match:
                return cls._keyword(match.group(0))
        if compact.startswith("对于") and compact.endswith("来说"):
            return ""
        compact = re.sub(r"^(?:然后|因为|比如说|而不是|对于|就是|去)+", "", compact)
        return cls._keyword(compact or text)

    @staticmethod
    def _time_anchor(segment, phrase: str, maximum_duration_ms: int) -> tuple[int, int]:
        """Anchor an effect to the actual word(s) containing its visible phrase."""
        normalized_phrase = re.sub(r"[^\w\u4e00-\u9fff]+", "", phrase)
        pieces: list[tuple[int, int, int, int]] = []
        cursor = 0
        for word in segment.words:
            value = re.sub(r"[^\w\u4e00-\u9fff]+", "", word.text)
            pieces.append((cursor, cursor + len(value), word.start_ms, word.end_ms))
            cursor += len(value)
        joined = "".join(re.sub(r"[^\w\u4e00-\u9fff]+", "", word.text) for word in segment.words)
        offset = joined.find(normalized_phrase) if normalized_phrase else -1
        if offset >= 0:
            phrase_end = offset + len(normalized_phrase)
            matched = [piece for piece in pieces if piece[1] > offset and piece[0] < phrase_end]
            start_ms, end_ms = matched[0][2], matched[-1][3]
        else:
            start_ms, end_ms = segment.start_ms, segment.end_ms
        end_ms = min(segment.end_ms, max(end_ms, start_ms + 300), start_ms + maximum_duration_ms)
        if end_ms - start_ms < 300:
            start_ms = max(segment.start_ms, segment.end_ms - 300)
            end_ms = segment.end_ms
        return start_ms, end_ms

    @staticmethod
    def _book_title(text: str) -> str | None:
        match = re.search(r"《([^》]{1,48})》", text)
        if match:
            title = match.group(1).strip()
            # Faster-whisper can confuse the short function word "与" with
            # "有" in this commonly cited title. This normalises that ASR
            # variant without using any external cover artwork.
            return {"心理学有生活": "心理学与生活"}.get(title, title)
        unquoted = re.search(r"心理学[有与]生活", text)
        if unquoted:
            return "心理学与生活"
        if any(token in text.lower() for token in ("book", "reading", "书", "阅读", "心理学")):
            return "Book topic"
        return None

    @staticmethod
    def _visual_spec(text: str) -> dict[str, str] | None:
        """Turn transcript-grounded topic cues into retrieval queries.

        Queries are compact English descriptors because the no-key Commons
        catalogue is generally indexed more reliably that way; the visible
        title always remains excerpted from the spoken transcript.
        """
        normalized = text.lower()
        categories = (
            (("《", "书", "阅读", "作者", "book", "reading"), "book", "book reading", "external_image", "full_screen"),
            (("工厂", "制造", "生产", "车间", "factory", "manufacturing"), "factory", "factory manufacturing", "external_video", "full_screen"),
            (("产品", "商品", "超市", "食品", "货架", "product", "supermarket"), "product", "supermarket product", "external_video", "full_screen"),
            (("钱", "价格", "成本", "赚钱", "预算", "money", "price", "cost"), "money", "money price", "external_image", "side_card"),
            (("学习", "教育", "课程", "知识", "learn", "study"), "learning", "learning study", "external_image", "side_card"),
            (("用户", "消费者", "家庭", "人物", "人群", "people", "customer"), "people", "people customer", "external_image", "side_card"),
            (("城市", "国家", "地点", "商店", "市场", "place", "city"), "place", "city location", "external_image", "side_card"),
            (("文化", "中西方", "中国文化"), "concept", "cultural diversity", "external_image", "side_card"),
            (("实验", "研究发现", "研究"), "learning", "psychology research experiment", "external_image", "full_screen"),
            (("未来", "一年之后"), "concept", "future planning", "external_image", "side_card"),
            (("故事", "改写"), "learning", "creative story writing", "external_image", "full_screen"),
        )
        for tokens, theme, query, kind, display_mode in categories:
            if any(token in normalized for token in tokens):
                label = re.sub(r"\s+", " ", text).strip()[:42]
                return {"theme": theme, "query": query, "kind": kind, "display_mode": display_mode, "title": label or theme}
        return None

    @staticmethod
    def _infographic_spec(text: str, previous_text: str = "") -> dict[str, object] | None:
        normalized = text.lower()
        compact = re.sub(r"\s+", "", text).strip()
        numbered = re.search(r"第([一二三四五六七八九十]+)个(?:方法)?(?:是|就是)?(.+)", compact)
        if numbered:
            item = numbered.group(2).strip("，,。 ") or compact
            return {"variant": "number_list", "headline": f"第{numbered.group(1)}个方法", "items": [item[:36]]}
        if "而不是" in compact:
            left, right = compact.split("而不是", 1)
            left = left or re.sub(r"\s+", "", previous_text)
            if left and right:
                return {"variant": "comparison", "headline": "两种思考方式", "items": [left[-24:], right[:24]]}
        culture_match = re.search(r"只接触(.+?)和接触(.+?)两组", compact)
        if culture_match:
            return {"variant": "comparison", "headline": "两组文化接触实验", "items": [culture_match.group(1), culture_match.group(2)]}
        if any(token in normalized for token in ("区别", "vs", "versus")):
            parts = [part.strip() for part in re.split(r"(?:区别|vs|versus|，|,)", compact) if part.strip()]
            if len(parts) >= 2:
                return {"variant": "comparison", "headline": compact[:32], "items": parts[:2]}
        if any(token in normalized for token in ("步骤", "流程", "首先", "然后", "最后", "过程", "flow")):
            parts = [part.strip() for part in re.split(r"(?:首先|然后|最后|、|，|,)", compact) if part.strip()]
            items = parts[:4]
            if len(items) >= 2:
                return {"variant": "flow", "headline": compact[:32], "items": items}
        if re.search(r"\d+|一|二|三|四|五|六|七|八|九|十", compact):
            items = [part.strip() for part in re.split(r"[，,、]", compact) if part.strip()][:4]
            if len(items) >= 2:
                return {"variant": "number_list", "headline": compact[:32], "items": items}
        return None

    def plan(self, transcript: Transcript) -> AnimationPlan:
        animations = []
        semantic_segments = []
        last_start_ms = -self._minimum_gap_ms
        for index, segment in enumerate(transcript.segments, start=1):
            previous_text = transcript.segments[index - 2].text if index > 1 else ""
            book_title = self._book_title(segment.text)
            visual = self._visual_spec(segment.text)
            if book_title:
                query = "Psychology and Life book" if book_title == "心理学与生活" else "book reading"
                visual = {"theme": "book", "query": query, "kind": "external_image", "display_mode": "full_screen", "title": book_title}
            infographic = None if book_title else self._infographic_spec(segment.text, previous_text)
            if infographic:
                visual = None
            priority = bool(book_title or visual or infographic)
            new_rank = 2 if infographic else 1 if (book_title or visual) else 0
            if segment.start_ms < last_start_ms + self._minimum_gap_ms and not priority:
                continue
            if priority and animations and segment.start_ms < last_start_ms + self._minimum_gap_ms:
                # A semantic B-roll or diagram is editorially more valuable
                # than a nearby generic highlight. Do not repeatedly replace
                # one meaningful visual with another cue of equal priority.
                previous_rank = {"keyword_pop": 0, "media_visual": 1, "info_graphic": 2, "quote_card": 1}[animations[-1]["type"]]
                if new_rank <= previous_rank:
                    continue
                animations.pop()
                semantic_segments.pop()
                last_start_ms = animations[-1]["start_ms"] if animations else -self._minimum_gap_ms
                if segment.start_ms < last_start_ms + self._minimum_gap_ms:
                    continue
            keyword = self._meaningful_phrase(segment.text)
            if not keyword:
                continue
            anchor_phrase = keyword
            if book_title:
                anchor_phrase = "心理学有生活" if "心理学有生活" in segment.text else "心理学与生活" if "心理学与生活" in segment.text else "书"
            start_ms, end_ms = self._time_anchor(segment, anchor_phrase, self._maximum_duration_ms)
            if end_ms - start_ms < 300:
                continue
            identifier = f"{index:03d}"
            if book_title or visual:
                spec = visual or {"theme": "book", "query": "book reading", "kind": "external_image", "display_mode": "side_card", "title": book_title}
                animations.append({
                    "id": f"animation_{identifier}", "type": "media_visual", "template_id": "media_visual_v1",
                    "start_ms": start_ms, "end_ms": end_ms, "trigger_text": anchor_phrase,
                    "parameters": {"asset_id": f"media_{identifier}", "title": str(spec["title"]), "theme": spec["theme"], "accent_color": "#FFD400", "search_query": spec["query"], "desired_asset_kind": spec["kind"], "display_mode": spec["display_mode"]},
                })
            elif infographic:
                animations.append({
                    "id": f"animation_{identifier}", "type": "info_graphic", "template_id": "knowledge_infographic_v1",
                    "start_ms": start_ms, "end_ms": end_ms, "trigger_text": keyword,
                    "parameters": {"variant": infographic["variant"], "headline": infographic["headline"], "items": infographic["items"], "accent_color": "#FFD400"},
                })
            else:
                animations.append({
                    "id": f"animation_{identifier}", "type": "keyword_pop", "template_id": "keyword_pop_v1",
                    "start_ms": start_ms, "end_ms": end_ms, "trigger_text": keyword,
                    "parameters": {"text": keyword, "color": "#FFD400", "position": "top-right"},
                })
            semantic_segments.append({
                "id": f"semantic_{identifier}", "text": segment.text[:240], "start_ms": start_ms,
                "end_ms": end_ms, "intent": "emphasis", "keywords": [keyword],
            })
            last_start_ms = start_ms
        if not animations:
            raise RuntimeError("Transcript has no segment long enough for a safe animation")
        return validate_animation_plan(AnimationPlan(animations=animations, semantic_segments=semantic_segments), transcript)


class LocalLlmAnimationPlanningProvider:
    """Plan animations through a local OpenAI-compatible chat-completions server."""

    def __init__(self, model: str, base_url: str, timeout_seconds: int = 60) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("PLANNER_BASE_URL must point to a local loopback server")
        if timeout_seconds <= 0:
            raise ValueError("planner timeout must be positive")
        self.model = model
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _prompt(transcript: Transcript) -> str:
        return """You are a Chinese short-video semantic planner. Return one JSON object only, without Markdown.
Use only the supplied transcript text and timestamps. Do not invent words or times.
The object must match this schema exactly:
{
  "animations": [{"id": "animation_<id>", "type": "keyword_pop", "template_id": "keyword_pop_v1", "start_ms": 0, "end_ms": 1, "trigger_text": "source text", "parameters": {"text": "max 80 chars", "color": "#RRGGBB", "position": "top-left|top-right|bottom-left|bottom-right|center"}}],
  "semantic_segments": [{"id": "semantic_<id>", "text": "source text", "start_ms": 0, "end_ms": 1, "intent": "emphasis|explanation|transition|summary", "keywords": ["source keyword"]}]
}
Return at least one animation. Each animation must be fully contained in one supplied word or transcript segment, last 300-5000 ms, never overlap another animation, and have no more than two animation starts in any 10-second window.
For a quote_card use type quote_card, template_id quote_card_v1, and parameters {"headline": "max 48 chars", "body": "max 160 chars", "accent_color": "#RRGGBB"}.
For a topic visual use type media_visual, template_id media_visual_v1, and parameters {"asset_id": "media_<id>", "title": "transcript-grounded topic label", "theme": "book|factory|product|money|learning|people|place|concept|wellbeing|business|technology", "accent_color": "#RRGGBB", "search_query": "short search query", "desired_asset_kind": "external_image|external_video", "display_mode": "side_card|full_screen"}. Never invent facts from a visual source: external materials are B-roll only and their source is selected by the pipeline.
For an original diagram use type info_graphic, template_id knowledge_infographic_v1, and parameters {"variant": "number_list|comparison|flow", "headline": "transcript-grounded headline", "items": ["two to four transcript-grounded labels"], "accent_color": "#RRGGBB"}.
Transcript JSON:
""" + transcript.model_dump_json()

    @staticmethod
    def _extract_json(content: str) -> dict:
        value = content.strip()
        if value.startswith("```"):
            value = value.split("\n", 1)[1] if "\n" in value else ""
            if value.rstrip().endswith("```"):
                value = value.rstrip()[:-3]
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Local LLM returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Local LLM response must be a JSON object")
        return parsed

    def plan(self, transcript: Transcript) -> AnimationPlan:
        try:
            response = requests.post(
                self.endpoint,
                json={"model": self.model, "messages": [{"role": "user", "content": self._prompt(transcript)}], "temperature": 0.2},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Local LLM planning request failed: {exc}") from exc
        if not isinstance(content, str):
            raise RuntimeError("Local LLM response content must be text")
        try:
            plan = AnimationPlan.model_validate(self._extract_json(content))
            return validate_animation_plan(plan, transcript)
        except (ValidationError, PlanningRuleError, RuntimeError) as exc:
            raise RuntimeError(f"Local LLM returned an invalid animation plan: {exc}") from exc


class FasterWhisperProvider:
    def __init__(self, model_name: str, model_dir: Path, local_files_only: bool = True) -> None:
        self.model_name = model_name
        self.model_dir = model_dir
        self.local_files_only = local_files_only

    def transcribe(self, audio_path: Path) -> Transcript:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper is not installed; keep ASR_PROVIDER=mock or install the optional dependency") from exc
        self.model_dir.mkdir(parents=True, exist_ok=True)
        model = WhisperModel(self.model_name, device="cpu", compute_type="int8", download_root=str(self.model_dir), local_files_only=self.local_files_only)
        segments, info = model.transcribe(str(audio_path), language="zh", word_timestamps=True)
        converted = []
        for segment in segments:
            words = [
                {
                    "text": word.word.strip(),
                    "start_ms": max(0, round(word.start * 1000)),
                    # Faster-whisper timestamps have sub-millisecond precision. Preserve a
                    # valid interval when rounding collapses a very short word to one ms.
                    "end_ms": max(max(0, round(word.start * 1000)) + 1, round(word.end * 1000)),
                }
                for word in (segment.words or []) if word.start is not None and word.end is not None and word.word.strip()
            ]
            if words:
                start_ms = max(0, round(segment.start * 1000))
                converted.append({"text": segment.text.strip(), "start_ms": start_ms, "end_ms": max(start_ms + 1, round(segment.end * 1000)), "words": words})
        if not converted:
            raise RuntimeError("faster-whisper returned no word timestamps")
        return Transcript(language=info.language or "zh", language_confidence=getattr(info, "language_probability", None), full_text="".join(item["text"] for item in converted), segments=converted)
