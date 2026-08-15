"""Stage 4: Shot Planner.

Designs every shot with intentional camera language: shot type, camera angle,
lens, movement, distance, framing, depth, composition, focus, subject motion,
and transition. The planner is fully deterministic by design — camera grammar
is rule-governed so a given scene always produces the same deliberate shot
list, and the first shot of the hook scene is always the thumbnail candidate
(``is_thumbnail``).

The grammar table maps each narration block onto two camera treatments: the
first opens the block (attention / legibility), the second advances the
explanation (context / proof). Movement is never decorative: push-ins isolate,
static frames teach, orbits only reveal finished products. When the Director
AI is supplied, its climax, hero block, and concept treatments are pinned onto
the matching shots.
"""

from __future__ import annotations

from pr1me.models.contracts.visual import ScriptBlockName
from pr1me.visual_architecture._common import VisualContext, make_logger
from pr1me.visual_architecture.contracts import (
    DirectorOutput,
    Scene,
    ScenePlanOutput,
    Shot,
    ShotPlanOutput,
)

__all__ = ["ShotPlanner", "plan_shots"]

#: Camera grammar per narration block. Each block owns two treatments: the
#: opener and the proof shot. Every attribute must read as a deliberate,
#: mechanical decision, not a decorative flourish.
_GRAMMAR: dict[ScriptBlockName, list[dict[str, str]]] = {
    "hook": [
        {
            "shot_type": "Extreme close-up",
            "camera_angle": "slight low angle",
            "lens": "macro 100mm",
            "camera_movement": "slow push-in",
            "distance": "macro distance",
            "framing": "tight, subject fills the frame",
            "depth": "shallow depth of field",
            "composition": "large central subject, minimal clutter",
            "focus": "primary subject surface",
            "motion": "subject held in a striking still pose",
            "transition": "cut",
            "reason": "An extreme close-up isolates the subject and creates immediate curiosity.",
        },
        {
            "shot_type": "Close-up",
            "camera_angle": "eye level",
            "lens": "85mm telephoto",
            "camera_movement": "static",
            "distance": "close distance",
            "framing": "medium framing, subject with context",
            "depth": "shallow depth of field",
            "composition": "rule of thirds, subject on the left third",
            "focus": "subject plus its immediate context",
            "motion": "slow ambient drift only",
            "transition": "cut",
            "reason": "A second hook frame adds context so the subject is recognizable, not abstract.",
        },
    ],
    "explanation": [
        {
            "shot_type": "Close-up",
            "camera_angle": "45-degree angle",
            "lens": "85mm telephoto",
            "camera_movement": "static",
            "distance": "close distance",
            "framing": "medium framing",
            "depth": "medium depth of field",
            "composition": "side cutaway, mechanism centered",
            "focus": "the mechanism interface",
            "motion": "mechanism operating slowly",
            "transition": "cut",
            "reason": "A static close-up keeps the mechanism legible while the narration explains it.",
        },
        {
            "shot_type": "Medium shot",
            "camera_angle": "top-down",
            "lens": "50mm standard",
            "camera_movement": "slow push-in",
            "distance": "medium distance",
            "framing": "wide framing",
            "depth": "deep depth of field",
            "composition": "cross-section view, full mechanism in frame",
            "focus": "internal structure",
            "motion": "part progression across the frame",
            "transition": "cut",
            "reason": "A top-down cross-section reveals the internal structure the explanation depends on.",
        },
    ],
    "practical_insight": [
        {
            "shot_type": "Medium shot",
            "camera_angle": "eye level",
            "lens": "35mm wide",
            "camera_movement": "slow zoom-in",
            "distance": "medium distance",
            "framing": "wide framing",
            "depth": "deep depth of field",
            "composition": "subject with environment, action zone centered",
            "focus": "where the change is applied",
            "motion": "the change being applied deliberately",
            "transition": "cut",
            "reason": "A wider frame shows exactly where the practical change happens in the real setup.",
        },
        {
            "shot_type": "Close-up",
            "camera_angle": "top-down",
            "lens": "50mm standard",
            "camera_movement": "static",
            "distance": "close distance",
            "framing": "medium framing",
            "depth": "shallow depth of field",
            "composition": "before-after split in one frame",
            "focus": "the changed setting or part",
            "motion": "slow compare gesture",
            "transition": "cut",
            "reason": "A close comparison frame makes the result of the change undeniable.",
        },
    ],
    "ending": [
        {
            "shot_type": "Wide shot",
            "camera_angle": "low angle",
            "lens": "35mm wide",
            "camera_movement": "slow orbit",
            "distance": "wide distance",
            "framing": "wide framing, subject in lower third",
            "depth": "deep depth of field",
            "composition": "rule of thirds, finished subject centered",
            "focus": "the finished subject",
            "motion": "slow turntable rotation",
            "transition": "fade",
            "reason": "A slow orbit of the finished result gives the ending a premium, resolved feel.",
        },
        {
            "shot_type": "Medium close-up",
            "camera_angle": "eye level",
            "lens": "50mm standard",
            "camera_movement": "static",
            "distance": "medium distance",
            "framing": "medium framing",
            "depth": "medium depth of field",
            "composition": "centered, clean negative space for the logo zone",
            "focus": "the key detail that embodies the takeaway",
            "motion": "still, held frame",
            "transition": "fade",
            "reason": "A clean held frame anchors the single memory the viewer should keep.",
        },
    ],
}

#: Fraction of the scene's seconds the opener shot receives.
_OPENER_SHARE = 0.45


class ShotPlanner:
    """Stage 4 engine: scenes -> camera-designed shots (deterministic)."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("shot_planner")

    async def run(
        self,
        plan: ScenePlanOutput,
        director: DirectorOutput | None = None,
    ) -> ShotPlanOutput:
        """Design the shot list from the scene plan.

        ``director`` is optional for backward compatibility; when supplied, its
        climax, hero focus, and treatments are pinned onto the matching shots.
        """
        self._logger.info(
            "event=shot_planner.started",
            n_scenes=len(plan.scenes),
            total_seconds=plan.total_seconds,
        )
        shots = plan_shots(plan.scenes, director)
        self._logger.info("event=shot_planner.completed", n_shots=len(shots))
        return ShotPlanOutput(shots=shots)


def plan_shots(
    scenes: list[Scene],
    director: DirectorOutput | None = None,
) -> list[Shot]:
    """Deterministic shot design: two intentional treatments per scene.

    When ``director`` is supplied, the shot list additionally pins: the climax
    (the first shot of the climax block), hero shots (every shot in the climax
    block, which deserve the highest render quality), and per-concept visual
    treatments (macro detail, exploded view, animation) onto the shots whose
    scene concept they target.
    """
    shots: list[Shot] = []
    shot_id = 1
    climax_block = director.climax.block if director else "explanation"
    treatments_by_concept = _treatments_by_concept(director)
    default_treatment = _default_treatment(director)
    seen_climax_block = False
    for scene in scenes:
        grammar = _GRAMMAR.get(scene.narration_block, _GRAMMAR["explanation"])
        seconds = _split_seconds(scene.seconds_allocated, len(grammar))
        concept_treatment = treatments_by_concept.get(scene.concept)
        if not concept_treatment and scene.narration_block == "explanation":
            concept_treatment = default_treatment
        in_climax_block = scene.narration_block == climax_block and not seen_climax_block
        for index, treatment in enumerate(grammar):
            is_thumbnail = scene.narration_block == "hook" and index == 0 and scene.id == 1
            shots.append(
                Shot(
                    id=shot_id,
                    scene_id=scene.id,
                    narration_block=scene.narration_block,
                    duration_seconds=seconds[index],
                    shot_type=treatment["shot_type"],
                    camera_angle=treatment["camera_angle"],
                    lens=treatment["lens"],
                    camera_movement=treatment["camera_movement"],
                    distance=treatment["distance"],
                    framing=treatment["framing"],
                    depth=treatment["depth"],
                    composition=treatment["composition"],
                    focus=treatment["focus"],
                    motion=treatment["motion"],
                    transition=treatment["transition"],
                    reason=treatment["reason"],
                    is_thumbnail=is_thumbnail,
                    is_climax=in_climax_block and index == 0,
                    is_hero=in_climax_block,
                    treatment=concept_treatment or "",
                )
            )
            shot_id += 1
        if in_climax_block:
            seen_climax_block = True
    return shots


def _default_treatment(director: DirectorOutput | None) -> str:
    """Fallback treatment for the explanation block when no concept matches.

    LLM scene plans may name concepts that differ from the knowledge block's
    concepts; the explanation block still carries the strongest claim, so it
    inherits the first mandated treatment when one exists.
    """
    if director is None or not director.treatments:
        return ""
    return director.treatments[0].treatment


def _treatments_by_concept(director: DirectorOutput | None) -> dict[str, str]:
    if director is None:
        return {}
    return {treatment.concept: treatment.treatment for treatment in director.treatments}


def _split_seconds(total: float, parts: int) -> list[float]:
    if parts <= 1:
        return [round(total, 3)]
    opener = round(total * _OPENER_SHARE, 3)
    remainder = round(total - opener, 3)
    return [opener, remainder]
