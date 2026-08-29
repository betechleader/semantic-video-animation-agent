"""Typed planning tools used only by the recoverable Agent workflow."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .planning_rules import PlanningRuleError
from .schemas import AnimationPlan, EvidenceReference, Transcript

DIRECTOR_INSTRUCTION_MAX_LENGTH = 2_000
MAX_PLAN_REPAIR_ATTEMPTS = 2
AGENT_PROMPT_VERSION = "agent-planning-v2-rag"
ANIMATION_PLAN_SCHEMA_VERSION = "animation-plan-v2-evidence"


class PlanViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=120)
    path: list[str | int] = Field(default_factory=list, max_length=12)
    message: str = Field(min_length=1, max_length=240)


class PlanningToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: Transcript
    director_instruction: str | None = Field(
        default=None,
        max_length=DIRECTOR_INSTRUCTION_MAX_LENGTH,
    )
    repair_attempt: int = Field(ge=0, le=MAX_PLAN_REPAIR_ATTEMPTS)
    violations: list[PlanViolation] = Field(default_factory=list, max_length=50)
    evidence: list[EvidenceReference] = Field(default_factory=list, max_length=20)


class PlanningToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: dict[str, Any] | None = None
    violations: list[PlanViolation] = Field(default_factory=list, max_length=50)
    planner_id: str = Field(min_length=1, max_length=120)
    model_id: str | None = Field(default=None, max_length=160)
    prompt_version: str = AGENT_PROMPT_VERSION
    schema_version: str = ANIMATION_PLAN_SCHEMA_VERSION


class ValidationToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: Transcript
    candidate: dict[str, Any] | None = None


class ValidationToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    plan: AnimationPlan | None = None
    violations: list[PlanViolation] = Field(default_factory=list, max_length=50)


def _safe_message(value: str) -> str:
    """Keep audit messages bounded without copying invalid input values."""

    compact = " ".join(value.split())
    return compact[:240] or "validation failed"


def planner_error_violation(exc: Exception) -> PlanViolation:
    return PlanViolation(
        code="planner_error",
        path=[],
        message=f"planner call failed ({exc.__class__.__name__})",
    )


def invoke_planning_tool(
    tool_input: PlanningToolInput,
    generate_candidate: Callable[[PlanningToolInput], Any],
    *,
    planner_id: str,
    model_id: str | None,
) -> PlanningToolOutput:
    """Call a planner behind a bounded, JSON-serializable tool envelope."""

    try:
        candidate = generate_candidate(tool_input)
        if isinstance(candidate, AnimationPlan):
            candidate = candidate.model_dump()
        if not isinstance(candidate, dict):
            raise TypeError("planner candidate must be an object")
        return PlanningToolOutput(
            candidate=candidate,
            planner_id=planner_id,
            model_id=model_id,
        )
    except Exception as exc:
        return PlanningToolOutput(
            candidate=None,
            violations=[planner_error_violation(exc)],
            planner_id=planner_id,
            model_id=model_id,
        )


def invoke_validation_tool(
    tool_input: ValidationToolInput,
    validate_rules: Callable[[AnimationPlan, Transcript], AnimationPlan],
) -> ValidationToolOutput:
    """Apply AnimationPlan schema validation, then transcript planning rules."""

    if tool_input.candidate is None:
        return ValidationToolOutput(
            valid=False,
            violations=[
                PlanViolation(
                    code="missing_candidate",
                    path=[],
                    message="planner did not return a plan candidate",
                )
            ],
        )
    try:
        plan = AnimationPlan.model_validate(tool_input.candidate)
    except ValidationError as exc:
        violations = [
            PlanViolation(
                code=f"schema.{error['type']}",
                path=list(error.get("loc", ())),
                message=_safe_message(str(error.get("msg", "schema validation failed"))),
            )
            for error in exc.errors(include_url=False, include_input=False)[:50]
        ]
        return ValidationToolOutput(valid=False, violations=violations)
    try:
        validated = validate_rules(plan, tool_input.transcript)
    except PlanningRuleError as exc:
        return ValidationToolOutput(
            valid=False,
            violations=[
                PlanViolation(
                    code="planning_rule",
                    path=[],
                    message=_safe_message(str(exc)),
                )
            ],
        )
    except Exception as exc:
        return ValidationToolOutput(
            valid=False,
            violations=[
                PlanViolation(
                    code="validation_error",
                    path=[],
                    message=f"validation tool failed ({exc.__class__.__name__})",
                )
            ],
        )
    return ValidationToolOutput(valid=True, plan=AnimationPlan.model_validate(validated))
