"""Typed local RAG tools and citation trust-boundary validation for Agent plans."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .knowledge_base import KnowledgeBaseService, tokenize_for_retrieval
from .schemas import Animation, AnimationPlan, EvidenceReference, Transcript

RAG_TOOL_VERSION = "retrieve-evidence-v1"
MAX_EVIDENCE_QUERIES = 6
MAX_EVIDENCE_RESULTS = 20


class EvidenceValidationError(ValueError):
    """Raised when a plan's factual claims are not backed by current evidence."""


class EvidenceQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(pattern=r"^query_[0-9]{3}$")
    text: str = Field(min_length=1, max_length=500)


class RetrieveEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: list[EvidenceQuery] = Field(max_length=MAX_EVIDENCE_QUERIES)
    method: Literal["keyword", "vector", "hybrid"] = "hybrid"
    per_query_limit: int = Field(default=3, ge=1, le=5)
    rerank: bool = True


class EvidenceQuerySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(pattern=r"^query_[0-9]{3}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    character_count: int = Field(ge=1, le=500)
    result_count: int = Field(ge=0, le=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class RetrieveEvidenceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_version: str = RAG_TOOL_VERSION
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=MAX_EVIDENCE_RESULTS)
    queries: list[EvidenceQuerySummary] = Field(default_factory=list, max_length=MAX_EVIDENCE_QUERIES)
    errors: list[str] = Field(default_factory=list, max_length=MAX_EVIDENCE_QUERIES)


def build_evidence_queries(transcript: Transcript) -> list[EvidenceQuery]:
    """Create bounded, deterministic queries from corrected transcript segments."""

    values: list[str] = []
    seen: set[str] = set()
    for segment in transcript.segments:
        compact = " ".join(segment.text.split()).strip()
        normalized = re.sub(r"\s+", "", compact).casefold()
        if compact and normalized not in seen:
            seen.add(normalized)
            values.append(compact[:500])
        if len(values) == MAX_EVIDENCE_QUERIES:
            break
    return [
        EvidenceQuery(query_id=f"query_{index:03d}", text=value)
        for index, value in enumerate(values, start=1)
    ]


def invoke_retrieve_evidence_tool(
    tool_input: RetrieveEvidenceInput,
    search: Callable[..., dict[str, Any]],
) -> RetrieveEvidenceOutput:
    """Run bounded local searches and return de-duplicated typed evidence."""

    evidence_by_id: dict[str, EvidenceReference] = {}
    query_summaries: list[EvidenceQuerySummary] = []
    errors: list[str] = []
    for query in tool_input.queries:
        query_hash = hashlib.sha256(query.text.encode("utf-8")).hexdigest()
        try:
            payload = search(
                query.text,
                method=tool_input.method,
                limit=tool_input.per_query_limit,
                rerank=tool_input.rerank,
            )
            raw_results = payload.get("results", [])
            if not isinstance(raw_results, list):
                raise TypeError("knowledge search results must be a list")
            query_ids: list[str] = []
            for raw in raw_results:
                reference = EvidenceReference(
                    chunk_id=raw["chunk_id"],
                    document_id=raw["document_id"],
                    source=raw["source"],
                    excerpt=raw["content"][:1_200],
                    content_sha256=raw["content_sha256"],
                    score=max(0.0, min(1.0, float(raw["score"]))),
                    retrieval_method=raw["retrieval_method"],
                    index_version=raw["index_version"],
                )
                query_ids.append(reference.chunk_id)
                previous = evidence_by_id.get(reference.chunk_id)
                if previous is None or reference.score > previous.score:
                    evidence_by_id[reference.chunk_id] = reference
            query_summaries.append(
                EvidenceQuerySummary(
                    query_id=query.query_id,
                    query_sha256=query_hash,
                    character_count=len(query.text),
                    result_count=len(query_ids),
                    evidence_ids=query_ids,
                )
            )
        except Exception as exc:
            errors.append(exc.__class__.__name__)
            query_summaries.append(
                EvidenceQuerySummary(
                    query_id=query.query_id,
                    query_sha256=query_hash,
                    character_count=len(query.text),
                    result_count=0,
                )
            )
    ranked = sorted(
        evidence_by_id.values(),
        key=lambda item: (-item.score, item.chunk_id),
    )[:MAX_EVIDENCE_RESULTS]
    return RetrieveEvidenceOutput(
        evidence=ranked,
        queries=query_summaries,
        errors=errors,
    )


_FACT_MARKERS = re.compile(
    r"(?:\d|%|％|研究发现|数据显示|统计|作者|出版|排名|增长|下降|证明|导致|"
    r"人物关系|因果|《|》|第一|第二|第三)"
)
_FACTUAL_MEDIA_THEMES = {
    "book", "factory", "product", "money", "people", "place", "business", "technology"
}


def _visible_text(animation: Animation) -> str:
    parameters = animation.parameters
    values = [animation.trigger_text]
    for name in ("text", "headline", "body", "title"):
        value = getattr(parameters, name, None)
        if isinstance(value, str):
            values.append(value)
    items = getattr(parameters, "items", None)
    if isinstance(items, list):
        values.extend(str(item) for item in items)
    return " ".join(values)


def animation_requires_evidence(animation: Animation) -> bool:
    """Classify factual/knowledge visuals conservatively and deterministically."""

    if animation.type in {"keyword_pop", "quote_card"}:
        return False
    if animation.type == "info_graphic":
        return True
    if animation.type == "media_visual" and animation.parameters.theme in _FACTUAL_MEDIA_THEMES:
        return True
    return bool(_FACT_MARKERS.search(_visible_text(animation)))


def _support_score(claim: str, excerpt: str) -> float:
    claim_tokens = {
        token for token in tokenize_for_retrieval(claim)
        if len(token) > 1 or token.isascii()
    }
    evidence_tokens = set(tokenize_for_retrieval(excerpt))
    if not claim_tokens:
        return 0.0
    return len(claim_tokens & evidence_tokens) / len(claim_tokens)


def _downgraded_keyword(animation: Animation) -> dict[str, Any]:
    text = re.sub(r"\s+", "", animation.trigger_text).strip()[:80] or "内容重点"
    return {
        "id": animation.id,
        "type": "keyword_pop",
        "template_id": "keyword_pop_v1",
        "start_ms": animation.start_ms,
        "end_ms": animation.end_ms,
        "trigger_text": animation.trigger_text,
        "parameters": {
            "text": text,
            "color": "#FFD400",
            "position": "top-right",
        },
        "evidence_ids": [],
        "confidence": 0.5,
        "selection_reason": "fact_safe_transcript_emphasis_no_evidence",
    }


def ground_candidate_with_evidence(
    candidate: dict[str, Any],
    evidence: Sequence[EvidenceReference],
) -> dict[str, Any]:
    """Attach supported citations and downgrade unsupported factual visuals."""

    raw_animations = candidate.get("animations")
    if not isinstance(raw_animations, list):
        return candidate
    grounded_animations: list[dict[str, Any]] = []
    used: dict[str, EvidenceReference] = {}
    for raw_animation in raw_animations:
        try:
            animation = Animation.model_validate(raw_animation)
        except ValidationError:
            grounded_animations.append(raw_animation)
            continue
        if not animation_requires_evidence(animation):
            payload = animation.model_dump()
            if animation.type == "media_visual":
                payload["parameters"].update(
                    title="抽象主题视觉",
                    theme="concept",
                    search_query="abstract concept",
                )
            payload.update(
                evidence_ids=[],
                confidence=0.75,
                selection_reason=(
                    "abstract_visual_packaging"
                    if animation.type in {"media_visual", "info_graphic"}
                    else "transcript_emphasis"
                ),
            )
            grounded_animations.append(payload)
            continue
        supported = sorted(
            (
                (_support_score(_visible_text(animation), item.excerpt), item)
                for item in evidence
            ),
            key=lambda pair: (-pair[0], -pair[1].score, pair[1].chunk_id),
        )
        selected = [item for support, item in supported if support >= 0.12][:2]
        if not selected:
            grounded_animations.append(_downgraded_keyword(animation))
            continue
        payload = animation.model_dump()
        payload.update(
            evidence_ids=[item.chunk_id for item in selected],
            confidence=round(
                min(1.0, max(0.1, sum(item.score for item in selected) / len(selected))),
                4,
            ),
            selection_reason="project_knowledge_support",
        )
        grounded_animations.append(payload)
        used.update((item.chunk_id, item) for item in selected)
    return {
        **candidate,
        "animations": grounded_animations,
        "evidence": [used[chunk_id].model_dump() for chunk_id in sorted(used)],
    }


def validate_evidence_citations(
    plan: AnimationPlan,
    service: KnowledgeBaseService,
) -> AnimationPlan:
    """Validate claim support and compare every citation with the live index."""

    references = {item.chunk_id: item for item in plan.evidence}
    if len(references) != len(plan.evidence):
        raise EvidenceValidationError("evidence references must be unique")
    used_ids = {
        chunk_id
        for animation in plan.animations
        for chunk_id in animation.evidence_ids
    }
    if used_ids != set(references):
        raise EvidenceValidationError(
            "plan evidence must exactly match cited animation evidence_ids"
        )
    current = service.resolve_chunks(sorted(used_ids))
    for chunk_id in sorted(used_ids):
        reference = references[chunk_id]
        resolved = current.get(chunk_id)
        if resolved is None:
            raise EvidenceValidationError(f"evidence {chunk_id} is missing from the current index")
        for field in ("document_id", "source", "content_sha256", "index_version"):
            if resolved[field] != getattr(reference, field):
                raise EvidenceValidationError(f"evidence {chunk_id} no longer matches the current index")
        if reference.excerpt != resolved["content"][:1_200]:
            raise EvidenceValidationError(f"evidence {chunk_id} excerpt does not match the current index")
    for animation in plan.animations:
        if animation_requires_evidence(animation) and not animation.evidence_ids:
            raise EvidenceValidationError(
                f"{animation.id} contains factual content without project evidence"
            )
        for chunk_id in animation.evidence_ids:
            if _support_score(_visible_text(animation), references[chunk_id].excerpt) < 0.12:
                raise EvidenceValidationError(
                    f"{animation.id} is not supported by evidence {chunk_id}"
                )
    return plan


def evidence_status(plan: AnimationPlan, service: KnowledgeBaseService) -> dict[str, Any]:
    """Return reviewer-facing excerpts plus live valid/missing/stale status."""

    ids = [item.chunk_id for item in plan.evidence]
    current = service.resolve_chunks(ids)
    items: list[dict[str, Any]] = []
    for reference in plan.evidence:
        resolved = current.get(reference.chunk_id)
        status = "missing" if resolved is None else "valid"
        if resolved is not None and any(
            resolved[field] != getattr(reference, field)
            for field in ("document_id", "source", "content_sha256", "index_version")
        ):
            status = "stale"
        if resolved is not None and reference.excerpt != resolved["content"][:1_200]:
            status = "stale"
        items.append({**reference.model_dump(), "status": status})
    cited_by = {
        item.chunk_id: [
            animation.id
            for animation in plan.animations
            if item.chunk_id in animation.evidence_ids
        ]
        for item in plan.evidence
    }
    for item in items:
        item["cited_by"] = cited_by[item["chunk_id"]]
    violations: list[str] = []
    try:
        validate_evidence_citations(plan, service)
    except EvidenceValidationError as exc:
        violations.append(str(exc)[:240])
    return {
        "valid": not violations and all(item["status"] == "valid" for item in items),
        "count": len(items),
        "items": items,
        "violations": violations,
    }
