"""Stage 2.5: Director AI.

Sits between the Engineering Visual Analyzer and the Scene Planner and thinks
like a documentary director *before* any scene exists:

- what the viewer must see (``show``) and what must never appear (``hide``)
- the strongest teaching method for the narration
- where attention goes in each narration block (``attention_flow``)
- the single visual climax of the Short
- the shot that deserves the highest render quality (``hero_shot_focus``)
- which concepts require macro detail, an exploded view, or animation
  (``treatments``)

The deterministic core derives every decision from the extracted knowledge and
the analyzer's strategy: show = the critical visual elements, hide = the
forbidden inaccuracies plus the channel's anti-cliche library, teaching method
and attention flow follow the four-act narration structure, the climax lands on
the mechanism the explanation depends on, and treatments are keyed off the
knowledge vocabulary. The LLM path (when configured) makes the same decisions
through the director template.
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
    VisualClimax,
    VisualizationStrategyOutput,
    VisualTreatment,
)
from pr1me.visual_architecture.prompts import DIRECTOR_PROMPT

__all__ = ["Director", "direct_decisions"]

#: Treatments never derive from the strategy style alone; they are keyed off
#: concrete vocabulary in the knowledge block so a mandate always has a reason.
_MACRO_TRIGGERS = (
    "surface",
    "finish",
    "micro",
    "nozzle",
    "interface",
    "grip",
    "texture",
    "tolerance",
    "filament",
)
_EXPLODED_TRIGGERS = (
    "assembly",
    "assembled",
    "components",
    "parts",
    "fits together",
    "screw",
    "stack",
    "layer stack",
)
_ANIMATION_TRIGGERS = (
    "flow",
    "melt",
    "moves",
    "movement",
    "motion",
    "process",
    "travel",
    "deposition",
    "rotation",
    "extrude",
)

#: Channel anti-cliche library: visuals that read as AI slop instead of
#: documentary engineering. Always suppressed on top of the knowledge block's
#: own forbidden inaccuracies.
_HIDE_DEFAULTS = (
    "glossy marketing render",
    "abstract stock footage",
    "unrealistic glowing effects",
    "invented measurement labels",
    "decorative light streaks",
    "floating detached parts",
)

#: Where attention goes per narration block, in act order.
_BLOCK_ATTENTION: dict[ScriptBlockName, str] = {
    "hook": "the subject fills the frame from the first frame",
    "explanation": "the working interface of the mechanism",
    "practical_insight": "the exact place the change is applied",
    "ending": "the finished subject with one memorable detail",
}

_TEACHING_METHOD = (
    "show the mechanism in its working context first, reveal how it works step "
    "by step, then end on the single applied change the viewer can copy"
)


class Director:
    """Stage 2.5 engine: knowledge + strategy -> film-level decisions."""

    def __init__(self, context: VisualContext) -> None:
        self._context = context
        self._logger = make_logger("director")

    async def run(
        self,
        knowledge: KnowledgeOutput,
        strategy: VisualizationStrategyOutput,
    ) -> DirectorOutput:
        """Direct the film, preferring the LLM when configured."""
        self._logger.info(
            "event=director.started",
            strategy=strategy.style.value,
            n_concepts=len(knowledge.concepts),
        )
        decisions = await llm_or_fallback(
            context=self._context,
            logger=self._logger,
            template=DIRECTOR_PROMPT,
            variables={
                "knowledge": model_dump_safe(knowledge),
                "strategy": model_dump_safe(strategy),
            },
            output_model=DirectorOutput,
            fallback=lambda: direct_decisions(knowledge, strategy),
            predicate=lambda value: _valid_decisions(value),
        )
        self._logger.info(
            "event=director.completed",
            n_treatments=len(decisions.treatments),
            climax=decisions.climax.concept,
        )
        return decisions


def direct_decisions(
    knowledge: KnowledgeOutput,
    strategy: VisualizationStrategyOutput,
) -> DirectorOutput:
    """Deterministic film direction from the knowledge and strategy."""
    show = _show_list(knowledge)
    hide = _hide_list(knowledge)
    concept = knowledge.primary_concept() or "the mechanism"
    climax_block = _climax_block(knowledge)
    return DirectorOutput(
        show=show,
        hide=hide,
        teaching_method=_TEACHING_METHOD,
        attention_flow=[_block_attention(block, concept) for block in _BLOCK_ORDER],
        climax=VisualClimax(
            concept=concept,
            block=climax_block,
            moment=_climax_moment(concept, strategy),
            reason=(
                f"The explanation of {concept} is where the narration commits its "
                "strongest claim, so the visuals must land it at full fidelity."
            ),
        ),
        hero_shot_focus=f"the working interface of {concept} at maximum detail",
        treatments=_treatments(knowledge),
    )


# ---------------------------------------------------------------- internals --


#: Narration act order (matches the scene planner's block coverage contract).
_BLOCK_ORDER: tuple[ScriptBlockName, ...] = (
    "hook",
    "explanation",
    "practical_insight",
    "ending",
)


def _show_list(knowledge: KnowledgeOutput) -> list[str]:
    elements = list(knowledge.critical_visual_elements)
    if not elements:
        elements = list(knowledge.objects or knowledge.concepts)
    return elements


def _hide_list(knowledge: KnowledgeOutput) -> list[str]:
    hidden = list(knowledge.forbidden_inaccuracies)
    for cliche in _HIDE_DEFAULTS:
        if cliche not in hidden:
            hidden.append(cliche)
    return hidden


def _block_attention(block: ScriptBlockName, concept: str) -> str:
    return f"{block}: {_BLOCK_ATTENTION[block].format(concept=concept)}"


def _climax_block(knowledge: KnowledgeOutput) -> ScriptBlockName:
    """The climax lands where the narration makes its strongest claim.

    Mechanisms and physics always live in the explanation; a knowledge block
    without mechanisms has no climax-worthy reveal, so the hook (the promised
    payoff) carries it instead.
    """
    if knowledge.mechanisms or knowledge.physics:
        return "explanation"
    return "hook"


def _climax_moment(concept: str, strategy: VisualizationStrategyOutput) -> str:
    style = strategy.style.value
    if style == "exploded_cad":
        return f"{concept} separating into every part along its assembly axis"
    if style == "cross_section":
        return f"{concept} cut open at the section plane showing the working interior"
    if style == "macro_mechanical":
        return f"the surface of {concept} at extreme macro scale"
    if style == "simulation":
        return f"{concept} mid-operation with the physics visualized"
    return f"{concept} at full fidelity, the single strongest frame of the film"


def _treatments(knowledge: KnowledgeOutput) -> list[VisualTreatment]:
    haystack = _knowledge_text(knowledge)
    treatments: list[VisualTreatment] = []
    for concept in knowledge.concepts:
        if any(token in haystack for token in _MACRO_TRIGGERS):
            treatments.append(
                VisualTreatment(
                    concept=concept,
                    treatment="macro_detail",
                    reason=(
                        f"{concept} depends on surface and interface detail "
                        "that only macro scale can make legible."
                    ),
                )
            )
        if any(token in haystack for token in _EXPLODED_TRIGGERS):
            treatments.append(
                VisualTreatment(
                    concept=concept,
                    treatment="exploded_view",
                    reason=f"{concept} is an assembly; separating its parts makes the fit visible.",
                )
            )
        if any(token in haystack for token in _ANIMATION_TRIGGERS):
            treatments.append(
                VisualTreatment(
                    concept=concept,
                    treatment="animation",
                    reason=f"{concept} only makes sense in motion, so it must be caught mid-action.",
                )
            )
    return treatments


def _knowledge_text(knowledge: KnowledgeOutput) -> str:
    parts = list(knowledge.concepts)
    parts.extend(knowledge.objects)
    parts.extend(knowledge.processes)
    parts.extend(knowledge.motion)
    parts.extend(mechanism.name for mechanism in knowledge.mechanisms)
    return " ".join(parts).lower()


def _valid_decisions(decisions: DirectorOutput) -> bool:
    """The LLM path must produce a complete, film-level set of decisions."""
    if not decisions.teaching_method or not decisions.hero_shot_focus:
        return False
    if not decisions.climax.moment or not decisions.climax.concept:
        return False
    return len(decisions.attention_flow) >= 3
