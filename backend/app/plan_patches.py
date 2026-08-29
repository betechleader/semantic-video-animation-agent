import re
from copy import deepcopy

from .schemas import (
    Animation,
    AnimationPlan,
    InformationGraphicParameters,
    KeywordPopParameters,
    MediaVisualParameters,
    PlanPatch,
    PlanPatchOperation,
    QuoteCardParameters,
)


class PlanPatchError(ValueError):
    """Raised when an instruction cannot become a safe, bounded plan patch."""


def _stronger_animation(animation: Animation) -> Animation:
    updated = animation.model_copy(deep=True)
    parameters = updated.parameters
    if isinstance(parameters, KeywordPopParameters):
        parameters = parameters.model_copy(update={"color": "#FFD166", "position": "center"})
    elif isinstance(parameters, (QuoteCardParameters, InformationGraphicParameters)):
        parameters = parameters.model_copy(update={"accent_color": "#FFD166"})
    elif isinstance(parameters, MediaVisualParameters):
        parameters = parameters.model_copy(update={"accent_color": "#FFD166"})
    return updated.model_copy(update={
        "parameters": parameters,
        "selection_reason": "Natural-language request: stronger opening",
        "confidence": 0.9,
    })


def build_rule_plan_patch(instruction: str, plan: AnimationPlan) -> PlanPatch:
    """Produce typed operations for a small, deterministic offline instruction set."""

    normalized = "".join(instruction.strip().lower().split())
    operations: list[PlanPatchOperation] = []
    targeted_ids = set(re.findall(r"animation_[A-Za-z0-9_-]+", instruction))

    def replace(animation: Animation, after: Animation, reason: str, confidence: float) -> None:
        operations.append(PlanPatchOperation(
            operation_id=f"operation_{len(operations) + 1:03d}",
            operation="replace_animation",
            target_animation_id=animation.id,
            before=animation,
            after=after,
            reason=reason,
            confidence=confidence,
            evidence_ids=list(after.evidence_ids),
        ))

    if any(token in normalized for token in ("前三秒更抓人", "开头更抓人", "strongeropening", "strongerfirst3seconds")):
        candidates = sorted(plan.animations, key=lambda item: (item.start_ms, item.id))
        if candidates:
            replace(candidates[0], _stronger_animation(candidates[0]), "Strengthen the opening visual", 0.9)

    if any(token in normalized for token in ("减少全屏素材", "不要遮挡人脸", "少用全屏", "reducefullscreen", "avoidcoveringfaces")):
        for animation in plan.animations:
            if animation.type != "media_visual":
                continue
            parameters = animation.parameters
            assert isinstance(parameters, MediaVisualParameters)
            if parameters.display_mode == "full_screen":
                existing_index = next((index for index, item in enumerate(operations) if item.target_animation_id == animation.id), None)
                base_after = operations[existing_index].after if existing_index is not None else animation
                assert base_after is not None and isinstance(base_after.parameters, MediaVisualParameters)
                after = base_after.model_copy(update={
                    "parameters": base_after.parameters.model_copy(update={"display_mode": "side_card"}),
                    "selection_reason": "Natural-language request: preserve the talking head",
                    "confidence": 0.95,
                })
                if existing_index is None:
                    replace(animation, after, "Change full-screen media to a face-safe side card", 0.95)
                else:
                    previous = operations[existing_index]
                    operations[existing_index] = previous.model_copy(update={
                        "after": after,
                        "reason": f"{previous.reason}; change full-screen media to a face-safe side card",
                        "confidence": min(previous.confidence, 0.95),
                        "evidence_ids": list(after.evidence_ids),
                    })

    if targeted_ids:
        by_id = {item.id: item for item in plan.animations}
        unknown = targeted_ids - set(by_id)
        if unknown:
            raise PlanPatchError(f"Unknown animation target: {sorted(unknown)[0]}")
        for animation_id in sorted(targeted_ids):
            if animation_id in {item.target_animation_id for item in operations}:
                continue
            animation = by_id[animation_id]
            if any(token in normalized for token in ("删除", "移除", "remove")):
                operations.append(PlanPatchOperation(
                    operation_id=f"operation_{len(operations) + 1:03d}",
                    operation="remove_animation",
                    target_animation_id=animation.id,
                    before=animation,
                    reason="Remove the explicitly named animation",
                    confidence=0.99,
                    evidence_ids=list(animation.evidence_ids),
                ))
            elif animation.type == "media_visual" and any(token in normalized for token in ("关闭", "禁用", "disable")):
                parameters = animation.parameters
                assert isinstance(parameters, MediaVisualParameters)
                replace(
                    animation,
                    animation.model_copy(update={"parameters": parameters.model_copy(update={"enabled": False})}),
                    "Disable the explicitly named media visual",
                    0.99,
                )

    if not operations:
        raise PlanPatchError(
            "Instruction did not map to a supported safe edit; name an animation ID or request a stronger opening/reduced full-screen media"
        )
    return PlanPatch(operations=operations)


def apply_plan_patch(
    current: AnimationPlan,
    patch: PlanPatch,
    approved_operation_ids: list[str],
) -> AnimationPlan:
    """Apply approved operations only after matching their before snapshots."""

    approved = set(approved_operation_ids)
    known = {item.operation_id for item in patch.operations}
    if not approved or not approved.issubset(known):
        raise PlanPatchError("Approved operation IDs must belong to the patch")
    animations = {item.id: item for item in current.animations}
    order = [item.id for item in current.animations]
    for operation in patch.operations:
        if operation.operation_id not in approved:
            continue
        authoritative = animations.get(operation.target_animation_id)
        if authoritative is None or authoritative.model_dump() != operation.before.model_dump():
            raise PlanPatchError("The formal plan changed after this patch was previewed")
        if operation.operation == "remove_animation":
            del animations[operation.target_animation_id]
            order.remove(operation.target_animation_id)
        else:
            assert operation.after is not None
            animations[operation.target_animation_id] = operation.after
    if not animations:
        raise PlanPatchError("A patch cannot remove every animation")
    data = deepcopy(current.model_dump())
    data["animations"] = [animations[item_id].model_dump() for item_id in order]
    adopted_evidence_ids = {
        evidence_id for animation in animations.values() for evidence_id in animation.evidence_ids
    }
    data["evidence"] = [
        item for item in data.get("evidence", []) if item["chunk_id"] in adopted_evidence_ids
    ]
    # Renderer-owned data is always rebuilt from the authoritative source and plan.
    data["media_assets"] = []
    data["face_regions"] = []
    data["media_placements"] = []
    return AnimationPlan.model_validate(data)
