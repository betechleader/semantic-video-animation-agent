"""Deterministic, network-free comparison of standard and Agent planning paths."""

from __future__ import annotations

import json
import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent_tools import (
    MAX_PLAN_REPAIR_ATTEMPTS,
    PlanViolation,
    PlanningToolInput,
    ValidationToolInput,
    invoke_planning_tool,
    invoke_validation_tool,
)
from backend.app.planning_rules import (
    MAX_ANIMATION_DURATION_MS,
    MIN_ANIMATION_DURATION_MS,
    validate_animation_plan,
)
from backend.app.providers import MockAnimationPlanningProvider
from backend.app.schemas import AnimationPlan, Transcript, TranscriptSegment, WordTiming
from backend.app.rag_tools import (
    RetrieveEvidenceInput,
    build_evidence_queries,
    invoke_retrieve_evidence_tool,
)
from .multi_agent import (
    critic_violations,
    no_evidence_search,
    run_critic,
    run_planner,
    run_researcher,
)

EVAL_SCHEMA_VERSION = "agent-eval-v3-multi-agent"
DATASET_SCHEMA_VERSION = "agent-eval-dataset-v2-rag"


class EvalSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=240)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    source: Literal["self_authored"]
    description: str = Field(min_length=1, max_length=200)
    segments: list[EvalSegment] = Field(min_length=1)
    agent_scenario: Literal[
        "none", "invalid_schema_once", "invalid_rule_once", "persistent_overlap"
    ] = "none"
    evidence_text: str | None = Field(default=None, min_length=1, max_length=500)

    def transcript(self) -> Transcript:
        segments = []
        for item in self.segments:
            text_split = max(1, len(item.text) // 2)
            time_split = item.start_ms + (item.end_ms - item.start_ms) // 2
            segments.append(
                TranscriptSegment(
                    text=item.text,
                    start_ms=item.start_ms,
                    end_ms=item.end_ms,
                    words=[
                        WordTiming(
                            text=item.text[:text_split],
                            start_ms=item.start_ms,
                            end_ms=time_split,
                        ),
                        WordTiming(
                            text=item.text[text_split:],
                            start_ms=time_split,
                            end_ms=item.end_ms,
                        ),
                    ],
                )
            )
        return Transcript(
            language="zh",
            language_confidence=1.0,
            full_text="".join(item.text for item in self.segments),
            segments=segments,
        )


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["agent-eval-dataset-v2-rag"]
    name: str = Field(min_length=1, max_length=120)
    cases: list[EvalCase] = Field(min_length=10)


@dataclass
class RunObservation:
    case_id: str
    mode: Literal["standard", "agent", "multi_agent"]
    status: Literal["completed", "awaiting_human", "failed"] = "failed"
    schema_valid: bool = False
    grounded_items: int = 0
    grounding_items: int = 0
    legal_intervals: int = 0
    intervals: int = 0
    overlap_violations: int = 0
    animation_count: int = 0
    tool_calls: int = 0
    successful_tool_calls: int = 0
    repair_required: bool = False
    repair_succeeded: bool = False
    retry_count: int = 0
    human_intervention: bool = False
    retrieval_expected: int = 0
    retrieval_hits: int = 0
    citation_items: int = 0
    correct_citations: int = 0
    latencies_ms: dict[str, list[float]] = field(
        default_factory=lambda: {"retrieval": [], "planning": [], "validation": []}
    )
    calls: list[dict[str, Any]] = field(default_factory=list)
    failure_category: str | None = None

    @property
    def run_id(self) -> str:
        return f"eval:{self.mode}:{self.case_id}"

    def record_call(self, node: str, tool_name: str, status: str, duration_ms: float) -> None:
        self.tool_calls += 1
        if status == "completed":
            self.successful_tool_calls += 1
        ordinal = 1 + sum(call["node"] == node for call in self.calls)
        self.calls.append(
            {
                "run_id": self.run_id,
                "node_run_id": f"{self.run_id}:{node}",
                "tool_call_id": f"{self.run_id}:{node}:{tool_name}:{ordinal}",
                "node": node,
                "tool_name": tool_name,
                "status": status,
                "duration_ms": duration_ms,
            }
        )


def load_dataset(path: Path) -> EvalDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvalDataset.model_validate(payload)


def _duration_ms(started_at: float) -> float:
    return max(0.0, round((time.perf_counter() - started_at) * 1_000, 3))


def _normalized(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text).casefold()


def _contained(start_ms: int, end_ms: int, transcript: Transcript) -> bool:
    intervals = [(segment.start_ms, segment.end_ms) for segment in transcript.segments]
    intervals.extend(
        (current.start_ms, following.end_ms)
        for current, following in zip(transcript.segments, transcript.segments[1:])
        if 0 <= following.start_ms - current.end_ms <= 1_200
    )
    return any(start <= start_ms < end_ms <= end for start, end in intervals)


def _observe_plan(
    observation: RunObservation,
    candidate: dict[str, Any] | None,
    transcript: Transcript,
) -> AnimationPlan | None:
    if candidate is None:
        return None
    try:
        plan = AnimationPlan.model_validate(candidate)
    except Exception:
        return None
    observation.schema_valid = True
    transcript_text = _normalized(transcript.full_text)
    for animation in plan.animations:
        observation.animation_count += 1
        observation.intervals += 1
        duration = animation.end_ms - animation.start_ms
        if (
            MIN_ANIMATION_DURATION_MS <= duration <= MAX_ANIMATION_DURATION_MS
            and _contained(animation.start_ms, animation.end_ms, transcript)
        ):
            observation.legal_intervals += 1
        observation.grounding_items += 1
        if _normalized(animation.trigger_text) in transcript_text:
            observation.grounded_items += 1
    for semantic in plan.semantic_segments:
        observation.intervals += 1
        if _contained(semantic.start_ms, semantic.end_ms, transcript):
            observation.legal_intervals += 1
        observation.grounding_items += 1
        if _normalized(semantic.text) in transcript_text:
            observation.grounded_items += 1
    ordered = sorted(plan.animations, key=lambda item: (item.start_ms, item.end_ms, item.id))
    observation.overlap_violations = sum(
        current.start_ms < previous.end_ms
        for previous, current in zip(ordered, ordered[1:])
    )
    return plan


def _mutate_candidate(
    candidate: dict[str, Any], scenario: str, repair_attempt: int
) -> dict[str, Any]:
    mutated = json.loads(json.dumps(candidate, ensure_ascii=False))
    if scenario == "invalid_schema_once" and repair_attempt == 0:
        mutated.pop("animations", None)
    elif scenario == "invalid_rule_once" and repair_attempt == 0:
        mutated["animations"][0]["start_ms"] = 0
        mutated["animations"][0]["end_ms"] = 500
    elif scenario == "persistent_overlap":
        duplicate = json.loads(json.dumps(mutated["animations"][0], ensure_ascii=False))
        duplicate["id"] = "animation_eval_overlap"
        mutated["animations"].append(duplicate)
    return mutated


def _run_standard(case: EvalCase) -> RunObservation:
    observation = RunObservation(case_id=case.id, mode="standard")
    transcript = case.transcript()
    provider = MockAnimationPlanningProvider()
    candidate: dict[str, Any] | None = None
    started_at = time.perf_counter()
    try:
        candidate = provider.plan(transcript).model_dump()
        planning_status = "completed"
    except Exception as exc:
        planning_status = "failed"
        observation.failure_category = f"planning_{exc.__class__.__name__.lower()}"
    planning_ms = _duration_ms(started_at)
    observation.latencies_ms["planning"].append(planning_ms)
    observation.record_call("planning", "standard_planner", planning_status, planning_ms)
    if candidate is None:
        return observation

    started_at = time.perf_counter()
    result = invoke_validation_tool(
        ValidationToolInput(transcript=transcript, candidate=candidate),
        validate_animation_plan,
    )
    validation_ms = _duration_ms(started_at)
    observation.latencies_ms["validation"].append(validation_ms)
    observation.record_call(
        "validation",
        "validate_animation_plan",
        "completed" if result.valid else "failed",
        validation_ms,
    )
    _observe_plan(observation, candidate, transcript)
    if result.valid:
        observation.status = "completed"
    else:
        observation.failure_category = "plan_validation_failed"
    return observation


def _run_agent(case: EvalCase) -> RunObservation:
    observation = RunObservation(case_id=case.id, mode="agent")
    transcript = case.transcript()
    provider = MockAnimationPlanningProvider()
    candidate: dict[str, Any] | None = None
    violations: list[PlanViolation] = []
    retrieved_evidence = []

    if case.evidence_text:
        expected_chunk_id = f"chunk_{hashlib.sha256((case.id + ':expected').encode()).hexdigest()[:32]}"
        distractor_chunk_id = f"chunk_{hashlib.sha256((case.id + ':distractor').encode()).hexdigest()[:32]}"

        def fake_search(_query: str, **kwargs) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "chunk_id": expected_chunk_id,
                        "document_id": f"doc_{hashlib.sha256(case.id.encode()).hexdigest()[:24]}",
                        "source": f"self-authored-{case.id}.md",
                        "content": case.evidence_text,
                        "content_sha256": hashlib.sha256(case.evidence_text.encode()).hexdigest(),
                        "score": 0.95,
                        "retrieval_method": kwargs["method"],
                        "index_version": "knowledge-index-v1",
                    },
                    {
                        "chunk_id": distractor_chunk_id,
                        "document_id": f"doc_{hashlib.sha256((case.id + ':d').encode()).hexdigest()[:24]}",
                        "source": "self-authored-distractor.md",
                        "content": "无关的天气与旅行记录。",
                        "content_sha256": hashlib.sha256("无关的天气与旅行记录。".encode()).hexdigest(),
                        "score": 0.1,
                        "retrieval_method": kwargs["method"],
                        "index_version": "knowledge-index-v1",
                    },
                ]
            }

        started_at = time.perf_counter()
        retrieved = invoke_retrieve_evidence_tool(
            RetrieveEvidenceInput(queries=build_evidence_queries(transcript)),
            fake_search,
        )
        retrieved_evidence = retrieved.evidence
        retrieval_ms = _duration_ms(started_at)
        observation.latencies_ms["retrieval"].append(retrieval_ms)
        observation.record_call("planning", "retrieve_evidence", "completed", retrieval_ms)
        retrieved_ids = {item.chunk_id for item in retrieved.evidence}
        observation.retrieval_expected = 1
        observation.retrieval_hits = int(expected_chunk_id in retrieved_ids)
        observation.citation_items = 1
        observation.correct_citations = int(
            bool(retrieved.evidence) and retrieved.evidence[0].chunk_id == expected_chunk_id
        )

    for repair_attempt in range(MAX_PLAN_REPAIR_ATTEMPTS + 1):
        observation.retry_count = repair_attempt
        started_at = time.perf_counter()
        planning = invoke_planning_tool(
            PlanningToolInput(
                transcript=transcript,
                repair_attempt=repair_attempt,
                violations=violations,
                evidence=retrieved_evidence,
            ),
            lambda value, attempt=repair_attempt: _mutate_candidate(
                provider.plan(value.transcript).model_dump(), case.agent_scenario, attempt
            ),
            planner_id="offline_mock",
            model_id=None,
        )
        planning_ms = _duration_ms(started_at)
        observation.latencies_ms["planning"].append(planning_ms)
        observation.record_call(
            "planning",
            "plan_animation",
            "completed" if planning.candidate is not None else "failed",
            planning_ms,
        )
        candidate = planning.candidate
        started_at = time.perf_counter()
        validation = invoke_validation_tool(
            ValidationToolInput(transcript=transcript, candidate=candidate),
            validate_animation_plan,
        )
        validation_ms = _duration_ms(started_at)
        observation.latencies_ms["validation"].append(validation_ms)
        observation.record_call(
            "validation",
            "validate_animation_plan",
            "completed" if validation.valid else "failed",
            validation_ms,
        )
        if validation.valid:
            observation.status = "completed"
            observation.repair_succeeded = repair_attempt > 0
            break
        observation.repair_required = True
        violations = validation.violations
    else:
        observation.status = "awaiting_human"
        observation.human_intervention = True
        observation.failure_category = "plan_repair_exhausted"

    _observe_plan(observation, candidate, transcript)
    return observation


def _run_multi_agent(case: EvalCase) -> RunObservation:
    """Run the feature-flagged Researcher → Planner → Critic experiment."""

    observation = RunObservation(case_id=case.id, mode="multi_agent")
    transcript = case.transcript()
    expected_chunk_id: str | None = None
    search = no_evidence_search
    if case.evidence_text:
        expected_chunk_id = (
            f"chunk_{hashlib.sha256((case.id + ':expected').encode()).hexdigest()[:32]}"
        )
        distractor_chunk_id = (
            f"chunk_{hashlib.sha256((case.id + ':distractor').encode()).hexdigest()[:32]}"
        )

        def search(_query: str, **kwargs) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "chunk_id": expected_chunk_id,
                        "document_id": f"doc_{hashlib.sha256(case.id.encode()).hexdigest()[:24]}",
                        "source": f"self-authored-{case.id}.md",
                        "content": case.evidence_text,
                        "content_sha256": hashlib.sha256(case.evidence_text.encode()).hexdigest(),
                        "score": 0.95,
                        "retrieval_method": kwargs["method"],
                        "index_version": "knowledge-index-v1",
                    },
                    {
                        "chunk_id": distractor_chunk_id,
                        "document_id": f"doc_{hashlib.sha256((case.id + ':d').encode()).hexdigest()[:24]}",
                        "source": "self-authored-distractor.md",
                        "content": "无关的天气与旅行记录。",
                        "content_sha256": hashlib.sha256(
                            "无关的天气与旅行记录。".encode()
                        ).hexdigest(),
                        "score": 0.1,
                        "retrieval_method": kwargs["method"],
                        "index_version": "knowledge-index-v1",
                    },
                ]
            }

    started_at = time.perf_counter()
    research = run_researcher(transcript, search)
    research_ms = _duration_ms(started_at)
    observation.latencies_ms["retrieval"].append(research_ms)
    observation.record_call("research", "research_evidence_and_materials", "completed", research_ms)
    if expected_chunk_id is not None:
        retrieved_ids = {item.chunk_id for item in research.evidence}
        observation.retrieval_expected = 1
        observation.retrieval_hits = int(expected_chunk_id in retrieved_ids)
        observation.citation_items = 1
        observation.correct_citations = int(
            bool(research.evidence) and research.evidence[0].chunk_id == expected_chunk_id
        )

    candidate: dict[str, Any] | None = None
    issues: list[Any] = []
    for repair_attempt in range(MAX_PLAN_REPAIR_ATTEMPTS + 1):
        observation.retry_count = repair_attempt
        started_at = time.perf_counter()
        candidate = run_planner(
            PlanningToolInput(
                transcript=transcript,
                repair_attempt=repair_attempt,
                violations=critic_violations(issues),
                evidence=research.evidence,
            ),
            scenario=case.agent_scenario,
            critic_issues=issues,
        )
        planning_ms = _duration_ms(started_at)
        observation.latencies_ms["planning"].append(planning_ms)
        observation.record_call(
            "planning",
            "multi_agent_planner",
            "completed" if candidate is not None else "failed",
            planning_ms,
        )

        started_at = time.perf_counter()
        critique = run_critic(transcript, candidate)
        critic_ms = _duration_ms(started_at)
        observation.latencies_ms["validation"].append(critic_ms)
        observation.record_call(
            "critique",
            "structured_plan_critic",
            "completed",
            critic_ms,
        )
        if critique.valid:
            observation.status = "completed"
            observation.repair_succeeded = repair_attempt > 0
            break
        observation.repair_required = True
        issues = critique.issues
    else:
        observation.status = "awaiting_human"
        observation.human_intervention = True
        observation.failure_category = "critic_repair_exhausted"

    _observe_plan(observation, candidate, transcript)
    return observation


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 6)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _aggregate(observations: list[RunObservation]) -> dict[str, Any]:
    latencies = {
        stage: [value for item in observations for value in item.latencies_ms[stage]]
        for stage in ("retrieval", "planning", "validation")
    }
    repair_required = sum(item.repair_required for item in observations)
    return {
        "run_count": len(observations),
        "animation_plan_schema_pass_rate": _ratio(
            sum(item.schema_valid for item in observations), len(observations)
        ),
        "transcript_grounding_precision": _ratio(
            sum(item.grounded_items for item in observations),
            sum(item.grounding_items for item in observations),
        ),
        "time_interval_valid_rate": _ratio(
            sum(item.legal_intervals for item in observations),
            sum(item.intervals for item in observations),
        ),
        "overlap_violation_rate": _ratio(
            sum(item.overlap_violations for item in observations),
            sum(item.animation_count for item in observations),
        ),
        "tool_call_success_rate": _ratio(
            sum(item.successful_tool_calls for item in observations),
            sum(item.tool_calls for item in observations),
        ),
        "average_tool_call_count": round(
            sum(item.tool_calls for item in observations) / len(observations), 6
        ),
        "auto_repair_success_rate": _ratio(
            sum(item.repair_succeeded for item in observations), repair_required
        ),
        "average_retry_count": round(
            sum(item.retry_count for item in observations) / len(observations), 6
        ),
        "human_intervention_rate": _ratio(
            sum(item.human_intervention for item in observations), len(observations)
        ),
        "task_success_rate": _ratio(
            sum(item.status == "completed" for item in observations), len(observations)
        ),
        "evidence_retrieval_hit_rate": _ratio(
            sum(item.retrieval_hits for item in observations),
            sum(item.retrieval_expected for item in observations),
        ),
        "citation_correctness_rate": _ratio(
            sum(item.correct_citations for item in observations),
            sum(item.citation_items for item in observations),
        ),
        "stage_latency_ms": {
            stage: {
                "sample_count": len(values),
                "p50": _percentile(values, 0.50),
                "p95": _percentile(values, 0.95),
            }
            for stage, values in latencies.items()
        },
        "run_latency_ms": {
            "p50": _percentile(
                [sum(call["duration_ms"] for call in item.calls) for item in observations],
                0.50,
            ),
            "p95": _percentile(
                [sum(call["duration_ms"] for call in item.calls) for item in observations],
                0.95,
            ),
        },
    }


def _comparison(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    baseline_name: str = "standard",
    candidate_name: str = "agent",
) -> dict[str, Any]:
    metrics = (
        "animation_plan_schema_pass_rate",
        "transcript_grounding_precision",
        "time_interval_valid_rate",
        "overlap_violation_rate",
        "tool_call_success_rate",
        "average_tool_call_count",
        "auto_repair_success_rate",
        "average_retry_count",
        "human_intervention_rate",
        "task_success_rate",
        "evidence_retrieval_hit_rate",
        "citation_correctness_rate",
    )
    comparison: dict[str, Any] = {}
    for name in metrics:
        baseline_value = baseline.get(name)
        candidate_value = candidate.get(name)
        comparison[name] = {
            baseline_name: baseline_value,
            candidate_name: candidate_value,
            f"delta_{candidate_name}_minus_{baseline_name}": (
                None
                if baseline_value is None or candidate_value is None
                else round(candidate_value - baseline_value, 6)
            ),
        }
    return comparison


def _public_run(item: RunObservation) -> dict[str, Any]:
    return {
        "run_id": item.run_id,
        "case_id": item.case_id,
        "mode": item.mode,
        "status": item.status,
        "retry_count": item.retry_count,
        "human_intervention": item.human_intervention,
        "failure_category": item.failure_category,
        "calls": item.calls,
    }


def run_evaluation(
    dataset: EvalDataset,
    *,
    enable_multi_agent_experiment: bool = False,
) -> dict[str, Any]:
    standard_runs = [_run_standard(case) for case in dataset.cases]
    agent_runs = [_run_agent(case) for case in dataset.cases]
    standard_metrics = _aggregate(standard_runs)
    agent_metrics = _aggregate(agent_runs)
    modes = {
        "standard": standard_metrics,
        "agent": agent_metrics,
    }
    runs = [*map(_public_run, standard_runs), *map(_public_run, agent_runs)]
    experiment: dict[str, Any] = {
        "enabled": enable_multi_agent_experiment,
        "feature_flag": "--enable-multi-agent-experiment",
        "default_workflow_changed": False,
        "promotion": {
            "evaluated": False,
            "passed": False,
            "decision": "keep_single_agent_default",
            "checks": [],
        },
    }
    if enable_multi_agent_experiment:
        multi_agent_runs = [_run_multi_agent(case) for case in dataset.cases]
        multi_agent_metrics = _aggregate(multi_agent_runs)
        modes["multi_agent"] = multi_agent_metrics
        runs.extend(map(_public_run, multi_agent_runs))
        experiment.update(
            {
                "roles": {
                    "researcher": "evidence_and_material_candidates_only",
                    "planner": "animation_plan_candidate_only",
                    "critic": "structured_issues_and_suggestions_only",
                },
                "comparison_to_single_agent": _comparison(
                    agent_metrics,
                    multi_agent_metrics,
                    baseline_name="agent",
                    candidate_name="multi_agent",
                ),
            }
        )
    return {
        "schema_version": EVAL_SCHEMA_VERSION,
        "dataset": {
            "name": dataset.name,
            "schema_version": dataset.schema_version,
            "case_count": len(dataset.cases),
            "content_policy": "self_authored_chinese_transcripts_and_knowledge_only",
        },
        "modes": modes,
        "comparison": _comparison(standard_metrics, agent_metrics),
        "multi_agent_experiment": experiment,
        "runs": runs,
        "privacy": {
            "contains_user_storage_content": False,
            "contains_transcript_text": False,
            "contains_absolute_paths": False,
            "network_required": False,
        },
    }
