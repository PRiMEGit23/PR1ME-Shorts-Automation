"""Prompt mutator: turn typed changes into exact, deterministic prompt edits.

The storyboard compiler builds prompts from fixed phrase templates
(see knowledge/compiler/compilers/sdxl.py): camera is
"{distance} shot, {angle} angle, {lens} lens, {framing} framing", lighting
is "{direction} lighting, {style} style", composition is "{rule} composition",
and engineering visualizations append "engineering visualization: ...".

The mutator exploits those exact phrases. For every typed change it produces
a PromptMutation that names the phrase to replace and its replacement. apply()
runs the edits over the compiled prompt: REPLACE swaps the first occurrence
of the target phrase, and if the target is absent the replacement is appended
instead - so apply() is total and deterministic on any prompt.
"""

from __future__ import annotations

from knowledge.render_optimizer.optimization_models import (
    CameraChange,
    CompositionChange,
    LightingChange,
    MutationKind,
    OptimizationAction,
    PromptMutation,
    VisualizationChange,
)
from knowledge.visual_architecture import NegativeSpace

_CAMERA_PHRASES = {
    "shot": "shot",
    "angle": "angle",
    "lens": "lens",
    "framing": "framing",
}
_LIGHTING_PHRASES = {
    "direction": "lighting",
    "style": "style",
}
_COMPOSITION_RULE_PHRASE = "composition"


def _replacement_mutations(
    target_prompt: str,
    field_labels: dict[str, str],
    old_values: dict[str, str],
    new_values: dict[str, str],
    *,
    rationale: str,
) -> list[PromptMutation]:
    """Build REPLACE mutations: target = "{old} {label}", replacement = "{new} {label}"."""
    mutations: list[PromptMutation] = []
    for field, label in field_labels.items():
        old = old_values.get(field)
        new = new_values.get(field)
        if old is None or new is None or old == new:
            continue
        mutations.append(
            PromptMutation(
                kind=MutationKind.REPLACE,
                target_prompt=target_prompt,
                target=f"{old} {label}",
                replacement=f"{new} {label}",
                rationale=rationale,
            )
        )
    return mutations


def _append_mutations(
    target_prompt: str,
    field_labels: dict[str, str],
    new_values: dict[str, str],
    *,
    rationale: str,
) -> list[PromptMutation]:
    """Fallback when the old phrase values are unknown: append the new phrase."""
    mutations: list[PromptMutation] = []
    for field, label in field_labels.items():
        new = new_values.get(field)
        if new is None:
            continue
        mutations.append(
            PromptMutation(
                kind=MutationKind.APPEND,
                target_prompt=target_prompt,
                target="",
                replacement=f"{new} {label}",
                rationale=rationale,
            )
        )
    return mutations


def camera_mutations(
    change: CameraChange,
    old_values: dict[str, str] | None = None,
) -> list[PromptMutation]:
    """Map a camera change to edits of the compiled camera phrase.

    ``old_values`` maps field name -> the value currently in the prompt
    (the optimizer has it from the storyboard scene). Without it, the
    mutations append the new phrase instead of replacing it.
    """
    new_values: dict[str, str] = {}
    if change.distance is not None:
        new_values["shot"] = f"{change.distance.value}"
    if change.angle is not None:
        new_values["angle"] = f"{change.angle.value}"
    if change.lens is not None:
        new_values["lens"] = f"{change.lens.value}"
    if change.framing is not None:
        new_values["framing"] = f"{change.framing.value}"
    if not new_values:
        return []
    if old_values is None:
        return _append_mutations("positive", _CAMERA_PHRASES, new_values, rationale=change.rationale)
    return _replacement_mutations(
        "positive", _CAMERA_PHRASES, old_values, new_values, rationale=change.rationale
    )


def lighting_mutations(
    change: LightingChange,
    old_values: dict[str, str] | None = None,
) -> list[PromptMutation]:
    """Map a lighting change to edits of the compiled lighting phrase."""
    new_values: dict[str, str] = {}
    if change.direction is not None:
        new_values["direction"] = f"{change.direction.value}"
    if change.style is not None:
        new_values["style"] = f"{change.style.value}"
    if not new_values:
        return []
    if old_values is None:
        return _append_mutations("positive", _LIGHTING_PHRASES, new_values, rationale=change.rationale)
    return _replacement_mutations(
        "positive", _LIGHTING_PHRASES, old_values, new_values, rationale=change.rationale
    )


def composition_mutations(
    change: CompositionChange,
    old_rule: str | None = None,
) -> list[PromptMutation]:
    """Map a composition change to edits of the compiled composition phrase."""
    mutations: list[PromptMutation] = []
    if change.rule is not None:
        if old_rule:
            mutations.append(
                PromptMutation(
                    kind=MutationKind.REPLACE,
                    target_prompt="positive",
                    target=f"{old_rule} composition",
                    replacement=f"{change.rule.value} composition",
                    rationale=change.rationale,
                )
            )
        else:
            mutations.append(
                PromptMutation(
                    kind=MutationKind.APPEND,
                    target_prompt="positive",
                    target="",
                    replacement=f"{change.rule.value} composition",
                    rationale=change.rationale,
                )
            )
    if change.negative_space is not None and change.negative_space is not NegativeSpace.NONE:
        mutations.append(
            PromptMutation(
                kind=MutationKind.APPEND,
                target_prompt="positive",
                target="",
                replacement=f"negative space at {change.negative_space.value}",
                rationale=change.rationale,
            )
        )
    if change.emphasis:
        mutations.append(
            PromptMutation(
                kind=MutationKind.APPEND,
                target_prompt="positive",
                target="",
                replacement=change.emphasis,
                rationale=change.rationale,
            )
        )
    return mutations


def visualization_mutations(change: VisualizationChange) -> list[PromptMutation]:
    """Append the visualization tokens to the positive prompt."""
    if not change.prompt_tokens:
        return []
    return [
        PromptMutation(
            kind=MutationKind.APPEND,
            target_prompt="positive",
            target="",
            replacement="engineering visualization: " + ", ".join(change.prompt_tokens),
            rationale=change.rationale,
        )
    ]


def negative_mutations(tokens: list[str], *, rationale: str) -> list[PromptMutation]:
    """Append avoidance tokens to the negative prompt."""
    if not tokens:
        return []
    return [
        PromptMutation(
            kind=MutationKind.APPEND,
            target_prompt="negative",
            target="",
            replacement=", ".join(tokens),
            rationale=rationale,
        )
    ]


def apply(
    positive: str,
    negative: str,
    mutations: list[PromptMutation],
) -> tuple[str, str]:
    """Apply mutations to the prompts; always succeeds, deterministically."""
    for mutation in mutations:
        if mutation.target_prompt == "positive":
            positive = _apply_one(positive, mutation)
        else:
            negative = _apply_one(negative, mutation)
    return positive, negative


def _apply_one(text: str, mutation: PromptMutation) -> str:
    if mutation.kind is MutationKind.REPLACE:
        if mutation.target and mutation.target in text:
            return text.replace(mutation.target, mutation.replacement, 1)
        if mutation.replacement:
            return f"{text}, {mutation.replacement}"
        return text
    if mutation.replacement:
        return f"{text}, {mutation.replacement}"
    return text


def build_prompt(
    positive: str,
    negative: str,
    *,
    camera: list[CameraChange] = None,
    lighting: list[LightingChange] = None,
    composition: list[CompositionChange] = None,
    visualization: list[VisualizationChange] = None,
    actions: list[OptimizationAction] = None,
) -> tuple[str, str]:
    """Convenience: expand every typed change into applied prompt edits.

    Returns (positive, negative) after applying all derived mutations.
    """
    mutations: list[PromptMutation] = []
    for change in camera or []:
        mutations.extend(camera_mutations(change))
    for change in lighting or []:
        mutations.extend(lighting_mutations(change))
    for change in composition or []:
        mutations.extend(composition_mutations(change))
    for change in visualization or []:
        mutations.extend(visualization_mutations(change))
    for action in actions or []:
        if action.instruction:
            mutations.append(
                PromptMutation(
                    kind=MutationKind.APPEND,
                    target_prompt="positive",
                    target="",
                    replacement=action.instruction,
                    rationale=action.rationale,
                )
            )
    return apply(positive, negative, mutations)