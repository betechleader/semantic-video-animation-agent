"""Typed, offline-only roles for the optional P11 multi-Agent experiment."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent_tools import (
    PlanViolation,
    PlanningToolInput,
    ValidationToolInput,
    invoke_planning_tool,
    invoke_validation_tool,
)
from backend.app.planning_rules import validate_animation_plan
from backend.app.providers import MockAnimationPlanningProvider
from backend.app.rag_tools import (
    RetrieveEvidenceInput,
    build_evidence_queries,
    invoke_retrieve_evidence_tool,
)
from backend.app.schemas import EvidenceReference, Transcript


class MaterialCandidate(BaseModel):
    """Privacy-safe material candidate proposed by the Researcher role."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(pattern=r"^material_[0-9a-f]{16}$")
    query_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: str = "concept_visual"


class ResearcherOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=20)
    material_candidates: list[MaterialCandidate] = Field(default_factory=list, max_length=6)
    retrieval_errors: list[str] = Field(default_factory=list, max_length=6)


class CriticIssue(BaseModel):
    """A bounded issue and actionable suggestion; never a replacement plan."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    path: list[str | int] = Field(default_factory=list, max_length=12)
    suggestion: str = Field(min_length=1, max_length=160)


class CriticOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    issues: list[CriticIssue] = Field(default_factory=list, max_length=50)


def run_researcher(
    transcript: Transcript,
    search: Callable[..., dict[str, Any]],
) -> ResearcherOutput:
    """Retrieve evidence and opaque material candidates without creating a plan."""

    queries = build_evidence_queries(transcript)
    retrieved = invoke_retrieve_evidence_tool(
        RetrieveEvidenceInput(queries=queries),
        search,
    )
    candidates = [
        MaterialCandidate(
            candidate_id=f"material_{summary.query_sha256[:16]}",
            query_sha256=summary.query_sha256,
        )
        for summary in retrieved.queries
    ]
    return ResearcherOutput(
        evidence=retrieved.evidence,
        material_candidates=candidates,
        retrieval_errors=retrieved.errors,
    )


def run_planner(
    tool_input: PlanningToolInput,
    *,
    scenario: str,
    critic_issues: list[CriticIssue],
) -> dict[str, Any] | None:
    """Generate a candidate; Critic feedback is input but cannot bypass validation."""

    provider = MockAnimationPlanningProvider()

    def generate(value: PlanningToolInput) -> dict[str, Any]:
        candidate = provider.plan(value.transcript).model_dump()
        has_feedback = bool(critic_issues)
        if scenario == "invalid_schema_once" and not has_feedback:
            candidate.pop("animations", None)
        elif scenario == "invalid_rule_once" and not has_feedback:
            candidate["animations"][0]["start_ms"] = 0
            candidate["animations"][0]["end_ms"] = 500
        elif scenario == "persistent_overlap" and not has_feedback:
            duplicate = dict(candidate["animations"][0])
            duplicate["id"] = "animation_eval_overlap"
            candidate["animations"].append(duplicate)
        return candidate

    result = invoke_planning_tool(
        tool_input,
        generate,
        planner_id="offline_mock_multi_agent",
        model_id=None,
    )
    return result.candidate


def run_critic(transcript: Transcript, candidate: dict[str, Any] | None) -> CriticOutput:
    """Return structured problems and suggestions without editing or rendering."""

    validation = invoke_validation_tool(
        ValidationToolInput(transcript=transcript, candidate=candidate),
        validate_animation_plan,
    )
    suggestions = {
        "missing_candidate": "return one schema-valid AnimationPlan object",
        "planning_rule": "remove invalid timing, overlap, density, or grounding conflicts",
        "validation_error": "retry the typed validation boundary with a corrected candidate",
    }
    issues = [
        CriticIssue(
            code=violation.code,
            path=violation.path,
            suggestion=(
                "restore every required AnimationPlan field"
                if violation.code.startswith("schema.")
                else suggestions.get(violation.code, "correct the structured violation")
            ),
        )
        for violation in validation.violations
    ]
    return CriticOutput(valid=validation.valid, issues=issues)


def critic_violations(issues: list[CriticIssue]) -> list[PlanViolation]:
    """Convert bounded Critic feedback into the existing Planner repair contract."""

    return [
        PlanViolation(code=item.code, path=item.path, message=item.suggestion)
        for item in issues
    ]


def no_evidence_search(query: str, **_kwargs: Any) -> dict[str, Any]:
    """Deterministic no-network search used when an eval case has no evidence fixture."""

    del query
    return {"results": []}
