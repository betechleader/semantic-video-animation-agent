from collections.abc import Iterable

from .schemas import AnimationPlan, Transcript


class PlanningRuleError(ValueError):
    """Raised when a semantically valid plan cannot be safely rendered."""


MIN_ANIMATION_DURATION_MS = 300
MAX_ANIMATION_DURATION_MS = 5_000
MAX_ANIMATIONS_PER_10_SECONDS = 2
_DENSITY_WINDOW_MS = 10_000


def _contains(start_ms: int, end_ms: int, container_start_ms: int, container_end_ms: int) -> bool:
    return container_start_ms <= start_ms < end_ms <= container_end_ms


def _is_bound_to_interval(start_ms: int, end_ms: int, intervals: Iterable[tuple[int, int]]) -> bool:
    return any(_contains(start_ms, end_ms, interval_start, interval_end) for interval_start, interval_end in intervals)


def validate_animation_plan(plan: AnimationPlan, transcript: Transcript) -> AnimationPlan:
    """Validate planner output against transcript timing and rendering safety rules.

    Schema validation proves that a plan is well formed; these rules prove that it
    is grounded in the particular transcript being rendered.
    """
    segment_intervals = [(segment.start_ms, segment.end_ms) for segment in transcript.segments]
    adjacent_segment_intervals = [
        (current.start_ms, following.end_ms)
        for current, following in zip(transcript.segments, transcript.segments[1:])
        if 0 <= following.start_ms - current.end_ms <= 1_200
    ]
    grounded_segment_intervals = segment_intervals + adjacent_segment_intervals
    word_intervals = [
        (word.start_ms, word.end_ms)
        for segment in transcript.segments
        for word in segment.words
    ]

    animation_ids = [animation.id for animation in plan.animations]
    if len(animation_ids) != len(set(animation_ids)):
        raise PlanningRuleError("animation IDs must be unique")

    media_animation_ids = [
        animation.parameters.asset_id
        for animation in plan.animations
        if animation.type == "media_visual" and animation.parameters.enabled
    ]
    if len(media_animation_ids) != len(set(media_animation_ids)):
        raise PlanningRuleError("media visual asset IDs must be unique")
    if plan.media_assets:
        asset_ids = {asset.asset_id for asset in plan.media_assets}
        if len(asset_ids) != len(plan.media_assets):
            raise PlanningRuleError("media asset audit IDs must be unique")
        if asset_ids != set(media_animation_ids):
            raise PlanningRuleError("media asset audit metadata must exactly match media visual references")
        if any(asset.usage_end_ms <= asset.usage_start_ms for asset in plan.media_assets):
            raise PlanningRuleError("media asset usage intervals must be valid")

    if plan.media_placements:
        placement_ids = [placement.animation_id for placement in plan.media_placements]
        if len(placement_ids) != len(set(placement_ids)):
            raise PlanningRuleError("media placement animation IDs must be unique")
        if set(placement_ids) != {
            animation.id for animation in plan.animations
            if animation.type == "media_visual" and animation.parameters.enabled
        }:
            raise PlanningRuleError("media placements must exactly match media visual animations")

    for animation in plan.animations:
        duration_ms = animation.end_ms - animation.start_ms
        if duration_ms < MIN_ANIMATION_DURATION_MS or duration_ms > MAX_ANIMATION_DURATION_MS:
            raise PlanningRuleError(
                f"{animation.id} duration must be between "
                f"{MIN_ANIMATION_DURATION_MS} and {MAX_ANIMATION_DURATION_MS} ms"
            )
        if not _is_bound_to_interval(animation.start_ms, animation.end_ms, word_intervals + grounded_segment_intervals):
            raise PlanningRuleError(
                f"{animation.id} must be fully contained in one transcript word or segment"
            )

    for semantic_segment in plan.semantic_segments:
        if not _is_bound_to_interval(semantic_segment.start_ms, semantic_segment.end_ms, grounded_segment_intervals):
            raise PlanningRuleError(
                f"{semantic_segment.id} must be fully contained in one transcript segment"
            )

    ordered_animations = sorted(plan.animations, key=lambda animation: (animation.start_ms, animation.end_ms, animation.id))
    for previous, current in zip(ordered_animations, ordered_animations[1:]):
        if current.start_ms < previous.end_ms:
            raise PlanningRuleError(
                f"{previous.id} conflicts with {current.id}: animation time ranges cannot overlap"
            )

    for index, animation in enumerate(ordered_animations):
        window_end_ms = animation.start_ms + _DENSITY_WINDOW_MS
        count = sum(1 for candidate in ordered_animations[index:] if candidate.start_ms < window_end_ms)
        if count > MAX_ANIMATIONS_PER_10_SECONDS:
            raise PlanningRuleError(
                f"animation density exceeds {MAX_ANIMATIONS_PER_10_SECONDS} starts per 10 seconds"
            )
    return plan
