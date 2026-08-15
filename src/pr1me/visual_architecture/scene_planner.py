"""Stage 3: Scene Planner.

Breaks the narration into cinematic teaching scenes. Every scene carries a
teaching contract: purpose, teaching goal, concept, subject, environment,
foreground, background, objects, camera importance, viewer takeaway, and a
time allocation.

The deterministic core builds one scene per narration block (hook,
explanation, practical_insight, ending) with role-specific staging defaults and
allocates the 35-45 second budget proportionally to narration weight. The LLM
path can produce more granular scenes, but the deterministic validation pass
enforces the same invariants either way: every block covered, one idea per
scene, 35-45 seconds total.
"""

from __future__ import annotations

from pr1me.models.contracts.visual import ScriptBlockName
from pr1me.visual_architecture._common import (
    VisualContext,
    llm_or_fallback,
    make_logger,
    model_dump_safe,
)
from pr1me.visual_architecture.contracts import (
    DirectorOutput,
    KnowledgeOutput,
    Scene,
    ScenePlanOutput,
    VisualArchitectureInput,
)
from pr1me.visual_architecture.prompts import SCENE_PLANNER_PROMPT

__all__ = ["ScenePlanner", "plan_scenes"]

#: Target total length of the Short in seconds (channel budget).
_TARGET_SECONDS = 40.0
_MIN_SECONDS = 35.0
_MAX_SECONDS = 45.0

#: Per-block staging defaults used by the deterministic core.
_BLOCK_SCENES: dict[str, dict[str, str]] = {
    "hook": {
        "purpose": "Attention",
        "camera_importance": "critical — the subject must dominate the frame from frame one",
        "viewer_takeaway": "a striking preview that makes the viewer want the explanation",
    },
    "explanation": {
        "purpose": "Explain Mechanism",
        "camera_importance": "critical — the mechanism interface must be fully legible",
        "viewer_takeaway": "a clear mental model of how the mechanism works",
    },
    "practical_insight": {
        "purpose": "Demonstrate",
        "camera_importance": "high — the applied change must be visible and unmistakable",
        "viewer_takeaway": "exactly what to change and where to change it",
    },
    "ending": {
        "purpose": "Memory Anchor",
        "camera_importance": "medium — the finished subject plus the logo zone",
        "viewer_takeaway": "one memorable principle to keep after the video",
    },
}

_ENVIRONMENTS = {
    "hook": "clean workshop bench",
    "explanation": "neutral studio gradient",
    "practical_insight": "workshop with tools at hand",
    "ending": "polished studio showcase",
}

_FOREGROUNDS = {
    "hook": "the subject filling the frame",
    "explanation": "the mechanism shown in cutaway detail",
    "practical_insight": "the change being applied by hand or tool",
    "ending": "the finished result on display",
}

_BACKGROUNDS = {
    "hook": "softly blurred workshop depth",
    "explanation": "clean gradient with no distractions",
    "practical_insight": "the machine ready at the workbench",
    "ending": "soft gradient studio backdrop",
}


class ScenePlanner:
    """Stage 3 engine: narration + knowledge -> cinematic scenes."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("scene_planner")

    async def run(
        self,
        payload: VisualArchitectureInput,
        knowledge: KnowledgeOutput,
        director: DirectorOutput | None = None,
    ) -> ScenePlanOutput:
        """Plan the scenes, preferring the LLM when configured.

        ``director`` is optional for backward compatibility; when supplied, its
        attention flow sharpens each scene's camera importance and the LLM
        path receives the film-level decisions as context.
        """
        self._logger.info(
            "event=scene_planner.started",
            concept=knowledge.primary_concept(),
        )
        plan = await llm_or_fallback(
            context=self._context,
            logger=self._logger,
            template=SCENE_PLANNER_PROMPT,
            variables={
                "script": model_dump_safe(payload),
                "knowledge": model_dump_safe(knowledge),
                "director": model_dump_safe(director) if director else None,
            },
            output_model=ScenePlanOutput,
            fallback=lambda: plan_scenes(payload, knowledge, director),
            predicate=lambda value: _valid_plan(value),
        )
        self._logger.info(
            "event=scene_planner.completed",
            n_scenes=len(plan.scenes),
            total_seconds=plan.total_seconds,
        )
        return plan


def plan_scenes(
    payload: VisualArchitectureInput,
    knowledge: KnowledgeOutput,
    director: DirectorOutput | None = None,
) -> ScenePlanOutput:
    """Deterministic scene plan: one teaching scene per narration block."""
    blocks: list[tuple[ScriptBlockName, str]] = [
        ("hook", payload.hook),
        ("explanation", payload.explanation),
        ("practical_insight", payload.practical_insight),
        ("ending", payload.ending),
    ]
    seconds = _allocate_seconds(blocks)
    concept = knowledge.primary_concept() or "the mechanism"
    subject = _subject(knowledge)
    objects = knowledge.objects or (
        [knowledge.scale.reference_object] if knowledge.scale.reference_object else []
    )
    mechanism = next(iter(knowledge.mechanisms), None)
    attention = _attention_map(director)

    scenes: list[Scene] = []
    for index, (block, text) in enumerate(blocks, start=1):
        defaults = _BLOCK_SCENES[block]
        scenes.append(
            Scene(
                id=index,
                narration_block=block,
                purpose=defaults["purpose"],
                teaching_goal=_teaching_goal(block, concept, text),
                concept=concept,
                subject=subject,
                environment=_ENVIRONMENTS[block],
                foreground=_FOREGROUNDS[block],
                background=_BACKGROUNDS[block],
                objects=objects,
                camera_importance=_camera_importance(defaults, attention, block),
                viewer_takeaway=defaults["viewer_takeaway"],
                seconds_allocated=seconds[index - 1],
            )
        )
    if mechanism is not None:
        scenes[1] = scenes[1].model_copy(update={"concept": mechanism.name})
    return ScenePlanOutput(scenes=scenes, total_seconds=round(sum(seconds), 3))


# ---------------------------------------------------------------- internals --


def _attention_map(director: DirectorOutput | None) -> dict[str, str]:
    """Index the director's attention flow by narration block, if provided."""
    if director is None:
        return {}
    mapping: dict[str, str] = {}
    for line in director.attention_flow:
        block, _, rest = line.partition(":")
        block = block.strip()
        if block in _BLOCK_SCENES and rest.strip():
            mapping[block] = rest.strip()
    return mapping


def _camera_importance(
    defaults: dict[str, str],
    attention: dict[str, str],
    block: ScriptBlockName,
) -> str:
    if block not in attention:
        return defaults["camera_importance"]
    return f"critical — the eye goes where {attention[block]}"


def _teaching_goal(block: ScriptBlockName, concept: str, block_text: str) -> str:
    if block == "hook":
        return f"The viewer is curious about {concept} and wants the explanation."
    if block == "explanation":
        return f"The viewer understands how {concept} works and the physics behind it."
    if block == "practical_insight":
        return f"The viewer can apply {concept} to their own setup after this scene."
    return f"The viewer remembers the single principle {concept}."


def _subject(knowledge: KnowledgeOutput) -> str:
    if knowledge.objects:
        return knowledge.objects[0]
    if knowledge.scale.reference_object:
        return knowledge.scale.reference_object
    return "engineering mechanism"


def _allocate_seconds(blocks: list[tuple[ScriptBlockName, str]]) -> list[float]:
    weights = [max(1.0, float(len(text.split()))) for _, text in blocks]
    total = sum(weights)
    raw = [weight / total * _TARGET_SECONDS for weight in weights]
    clamped = [min(12.0, max(5.0, value)) for value in raw]
    # rescale back to the target so the budget is spent exactly.
    scale = _TARGET_SECONDS / sum(clamped)
    return [round(value * scale, 3) for value in clamped]


def _valid_plan(plan: ScenePlanOutput) -> bool:
    if not plan.scenes:
        return False
    if not (_MIN_SECONDS <= plan.total_seconds <= _MAX_SECONDS):
        return False
    covered = {scene.narration_block for scene in plan.scenes}
    return {"hook", "explanation", "practical_insight", "ending"} <= covered
