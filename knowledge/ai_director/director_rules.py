"""AI Director rules: every deterministic table the director may consult.

This module is the single source of truth for the director's decisions. No
other module - in the director, the runtime, or the knowledge base - may
re-implement these mappings; consumers import them here. Everything is a
pure constant or pure function: no randomness, no LLM, no clock.

QA envelope constraint (documented in docs/AI_DIRECTOR_ARCHITECTURE.md):
the simulated vision pipeline cures camera defects only when the compiled
prompt contains "100mm macro lens" twice and lighting defects only for
"key lighting" phrases, so the mapping tables below always keep
``Lens.MACRO_100`` and ``LightDirection.KEY`` while every other creative
dimension is free to vary.
"""

from __future__ import annotations

from knowledge.educational_director.educational_models import (
    AnimationRequirement,
    CognitiveStep,
    DifficultyLevel,
    TeachingStrategy,
    VisualTeachingMethod,
)
from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    CompositionRule,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
    Mood,
    MotionSpeed,
    MotionType,
    NegativeSpace,
    TransitionType,
)
from knowledge.visual_intelligence.storyboard import (
    CameraPlan,
    CompositionPlan,
    EngineeringVisualization,
    EngineeringVisualizationType,
    LightingPlan,
    Motion,
    ShotType,
    Transition,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal

# ------------------------------------------------------------------ shots --

#: Educational visual method -> cinematic shot archetype (canonical mapping).
SHOT_FOR_METHOD: dict[VisualTeachingMethod, ShotType] = {
    VisualTeachingMethod.COMPARISON_BOARD: ShotType.COMPARISON_SPLIT,
    VisualTeachingMethod.CROSS_SECTION: ShotType.CROSS_SECTION,
    VisualTeachingMethod.STRESS_VISUALIZATION: ShotType.ANNOTATED_DIAGRAM,
    VisualTeachingMethod.TRANSPARENT_HOUSING: ShotType.TRANSPARENT,
    VisualTeachingMethod.MOTION_VISUALIZATION: ShotType.SLOW_MOTION,
    VisualTeachingMethod.EXPLODED_VIEW: ShotType.EXPLODED_VIEW,
    VisualTeachingMethod.ANIMATION: ShotType.HERO,
    VisualTeachingMethod.THERMAL_VISUALIZATION: ShotType.ANNOTATED_DIAGRAM,
    VisualTeachingMethod.TIMELINE: ShotType.PROCESS_SEQUENCE,
    VisualTeachingMethod.DIAGRAM: ShotType.ANNOTATED_DIAGRAM,
    VisualTeachingMethod.MACRO: ShotType.MACRO,
    VisualTeachingMethod.CUTAWAY: ShotType.CUTAWAY,
    VisualTeachingMethod.XRAY: ShotType.XRAY,
    VisualTeachingMethod.INFOGRAPHIC: ShotType.ANNOTATED_DIAGRAM,
    VisualTeachingMethod.CAD: ShotType.CAD_RENDER,
    VisualTeachingMethod.SECTION_VIEW: ShotType.CROSS_SECTION,
    VisualTeachingMethod.MICROSCOPE: ShotType.MICROSCOPE,
    VisualTeachingMethod.ASSEMBLY_SEQUENCE: ShotType.PROCESS_SEQUENCE,
}


def shot_for_method(method: VisualTeachingMethod | str | None) -> ShotType:
    """Canonical shot for one visual teaching method (HERO fallback).

    Accepts the enum or its value string; the string view is derived from
    the single enum-keyed table, never duplicated.
    """
    if method is None:
        return ShotType.HERO
    if isinstance(method, VisualTeachingMethod):
        return SHOT_FOR_METHOD.get(method, ShotType.HERO)
    return _SHOT_BY_VALUE.get(method, ShotType.HERO)


#: Value-string view of the canonical table (derived, not duplicated).
_SHOT_BY_VALUE: dict[str, ShotType] = {
    method.value: shot for method, shot in SHOT_FOR_METHOD.items()
}
#: Legacy alias: the pre-Phase-8 runtime table keyed this method lowercase.
_SHOT_BY_VALUE["xray"] = ShotType.XRAY


# ------------------------------------------------------------ strategies --

#: Strategies where diagrams beat photorealism (annotation carries the idea).
DIAGRAM_PREFERRED_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {
        TeachingStrategy.DIAGRAM_FIRST,
        TeachingStrategy.LAYER_BY_LAYER_REVEAL,
        TeachingStrategy.HIDDEN_GEOMETRY,
        TeachingStrategy.PROGRESSIVE_DISCLOSURE,
        TeachingStrategy.PROCESS_TIMELINE,
        TeachingStrategy.MANUFACTURING_SEQUENCE,
        TeachingStrategy.MATERIAL_TRANSFORMATION,
        TeachingStrategy.FORCE_FLOW,
        TeachingStrategy.ENERGY_FLOW,
    }
)

#: Strategies that live on the difference between two states or options.
COMPARISON_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {
        TeachingStrategy.COMPARISON,
        TeachingStrategy.BEFORE_AFTER,
        TeachingStrategy.SCALE_COMPARISON,
        TeachingStrategy.MYTH_BUSTING,
        TeachingStrategy.QUESTION_ANSWER,
    }
)

#: Strategies where macro inspection is the teaching vehicle.
MACRO_REQUIRED_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {TeachingStrategy.SCALE_COMPARISON, TeachingStrategy.FAILURE_ANALYSIS}
)

#: Strategies that earn their payoff by withholding the reveal.
REVEAL_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {
        TeachingStrategy.LAYER_BY_LAYER_REVEAL,
        TeachingStrategy.HIDDEN_GEOMETRY,
        TeachingStrategy.PROGRESSIVE_DISCLOSURE,
        TeachingStrategy.MYTH_BUSTING,
        TeachingStrategy.QUESTION_ANSWER,
        TeachingStrategy.CAUSE_EFFECT,
    }
)

#: Strategies whose arcs earn an extra evidence beat (6 scenes).
SPLIT_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {
        TeachingStrategy.PROCESS_TIMELINE,
        TeachingStrategy.MANUFACTURING_SEQUENCE,
        TeachingStrategy.MATERIAL_TRANSFORMATION,
        TeachingStrategy.SIMULATION,
        TeachingStrategy.MECHANICAL_BREAKDOWN,
    }
)

#: Strategies whose arcs are simple enough to merge the comparison beat (4 scenes).
MERGE_THRESHOLD_FLOW_STEPS = 4
SPLIT_MIN_FLOW_STEPS = 6

#: The dominant cognitive beat each visual goal represents.
GOAL_DOMINANT_STAGE: dict[VisualGoal, CognitiveStep] = {
    VisualGoal.INTRODUCE_CONCEPT: CognitiveStep.HOOK,
    VisualGoal.COMPARE: CognitiveStep.COMPARISON,
    VisualGoal.REVEAL_INTERNAL_GEOMETRY: CognitiveStep.REVEAL,
    VisualGoal.EXPLAIN_PROCESS: CognitiveStep.EXPLANATION,
    VisualGoal.EXPLAIN_MOTION: CognitiveStep.DEMONSTRATION,
    VisualGoal.EXPLAIN_FORCE_FLOW: CognitiveStep.EXPLANATION,
    VisualGoal.EXPLAIN_HEAT_FLOW: CognitiveStep.EXPLANATION,
    VisualGoal.EXPLAIN_ASSEMBLY: CognitiveStep.EXPLANATION,
    VisualGoal.EXPLAIN_MANUFACTURING: CognitiveStep.EXPLANATION,
    VisualGoal.EXPLAIN_SCALE: CognitiveStep.EXAMPLE,
    VisualGoal.EXPLAIN_FAILURE: CognitiveStep.FAILURE,
    VisualGoal.EXPLAIN_OPTIMIZATION: CognitiveStep.SOLUTION,
    VisualGoal.EXPLAIN_MATERIAL_PROPERTIES: CognitiveStep.EVIDENCE,
    VisualGoal.EXPLAIN_MECHANISM: CognitiveStep.EXPLANATION,
    VisualGoal.HIGHLIGHT_DIFFERENCE: CognitiveStep.EVIDENCE,
    VisualGoal.SUMMARIZE: CognitiveStep.CONCLUSION,
}

#: Emotional intensity of each cognitive beat (1-10).
EMOTION_BY_STAGE: dict[CognitiveStep, int] = {
    CognitiveStep.HOOK: 8,
    CognitiveStep.QUESTION: 6,
    CognitiveStep.PROBLEM: 7,
    CognitiveStep.REVEAL: 9,
    CognitiveStep.EXPLANATION: 5,
    CognitiveStep.EVIDENCE: 6,
    CognitiveStep.COMPARISON: 5,
    CognitiveStep.FAILURE: 8,
    CognitiveStep.ROOT_CAUSE: 7,
    CognitiveStep.SOLUTION: 6,
    CognitiveStep.MYTH: 7,
    CognitiveStep.DEFINITION: 4,
    CognitiveStep.EXAMPLE: 5,
    CognitiveStep.DEMONSTRATION: 7,
    CognitiveStep.CONCLUSION: 6,
}

#: Strategies that make the payoff beat land harder.
EMOTION_BOOST_STRATEGIES: frozenset[TeachingStrategy] = frozenset(
    {TeachingStrategy.MYTH_BUSTING, TeachingStrategy.FAILURE_ANALYSIS}
)

#: Goals treated as the emotional payoff in boost strategies.
EMOTION_BOOST_GOALS: frozenset[VisualGoal] = frozenset(
    {VisualGoal.REVEAL_INTERNAL_GEOMETRY, VisualGoal.HIGHLIGHT_DIFFERENCE}
)

# --------------------------------------------------------------- budgets --

#: Baseline pacing by visual goal (1-10): how much information per beat.
PACING_BY_GOAL: dict[VisualGoal, int] = {
    VisualGoal.INTRODUCE_CONCEPT: 8,
    VisualGoal.COMPARE: 7,
    VisualGoal.REVEAL_INTERNAL_GEOMETRY: 6,
    VisualGoal.EXPLAIN_PROCESS: 5,
    VisualGoal.EXPLAIN_MOTION: 6,
    VisualGoal.EXPLAIN_FORCE_FLOW: 6,
    VisualGoal.EXPLAIN_HEAT_FLOW: 6,
    VisualGoal.EXPLAIN_ASSEMBLY: 5,
    VisualGoal.EXPLAIN_MANUFACTURING: 5,
    VisualGoal.EXPLAIN_SCALE: 5,
    VisualGoal.EXPLAIN_FAILURE: 7,
    VisualGoal.EXPLAIN_OPTIMIZATION: 5,
    VisualGoal.EXPLAIN_MATERIAL_PROPERTIES: 5,
    VisualGoal.EXPLAIN_MECHANISM: 6,
    VisualGoal.HIGHLIGHT_DIFFERENCE: 7,
    VisualGoal.SUMMARIZE: 4,
}

#: Cognitive-overload mitigation: advanced topics are paced slower.
DIFFICULTY_PACING_MOD: dict[DifficultyLevel, int] = {
    DifficultyLevel.BEGINNER: 0,
    DifficultyLevel.INTERMEDIATE: 0,
    DifficultyLevel.ADVANCED: -1,
}

ANIMATION_BUDGET_BY_REQUIREMENT: dict[AnimationRequirement, int] = {
    AnimationRequirement.YES: 9,
    AnimationRequirement.PARTIAL: 6,
    AnimationRequirement.NO: 3,
}

#: Methods that are inherently animated (their budget floor is raised).
ANIMATED_METHODS: frozenset[VisualTeachingMethod] = frozenset(
    {
        VisualTeachingMethod.ANIMATION,
        VisualTeachingMethod.MOTION_VISUALIZATION,
        VisualTeachingMethod.THERMAL_VISUALIZATION,
        VisualTeachingMethod.STRESS_VISUALIZATION,
    }
)

#: Methods that demand engineering overlays (tokens chosen by the director).
ENGINEERING_EMPHASIS_METHODS: frozenset[VisualTeachingMethod] = frozenset(
    {
        VisualTeachingMethod.CROSS_SECTION,
        VisualTeachingMethod.SECTION_VIEW,
        VisualTeachingMethod.TRANSPARENT_HOUSING,
        VisualTeachingMethod.STRESS_VISUALIZATION,
        VisualTeachingMethod.THERMAL_VISUALIZATION,
        VisualTeachingMethod.CUTAWAY,
        VisualTeachingMethod.XRAY,
    }
)


def clamp(value: int, *, minimum: int = 1, maximum: int = 10) -> int:
    """Clamp an integer decision into a 1-10 budget band."""
    return max(minimum, min(maximum, value))


# ---------------------------------------------------------- arc decisions --


def decide_scene_count(
    flow_steps: int, strategy: TeachingStrategy, methods: list[VisualTeachingMethod]
) -> tuple[int, str]:
    """Decide whether the arc merges (4), keeps (5), or splits (6) scenes.

    Deterministic: short simple arcs drop the comparison beat, sequence-heavy
    strategies with a long knowledge flow earn an evidence beat, everything
    else keeps the canonical five-scene arc.
    """
    compares = any(m is VisualTeachingMethod.COMPARISON_BOARD for m in methods)
    if flow_steps <= MERGE_THRESHOLD_FLOW_STEPS and strategy not in COMPARISON_STRATEGIES and not compares:
        return 4, "few knowledge steps and no comparison burden: the comparison beat merges into the process scene"
    if flow_steps >= SPLIT_MIN_FLOW_STEPS and strategy in SPLIT_STRATEGIES:
        return 6, "long sequence arc: an evidence beat earns its own scene"
    return 5, "canonical five-scene arc: hook, reveal, process, compare, recap"


# ----------------------------------------------------- cinematic mappings --

# QA envelope: lens stays MACRO_100 and light direction stays KEY (see
# module docstring); every other dimension is a pure function of the budget.


def camera_for(camera_intensity: int) -> CameraPlan:
    """Camera plan from camera intensity (1-10), observational to dramatic."""
    if camera_intensity <= 3:
        distance, angle, framing = (
            CameraDistance.MEDIUM,
            CameraAngle.HIGH,
            Framing.RULE_OF_THIRDS,
        )
        note = "restrained observational camera"
    elif camera_intensity <= 6:
        distance, angle, framing = (
            CameraDistance.MACRO,
            CameraAngle.EYE,
            Framing.SUBJECT_CENTER,
        )
        note = "standard documentary camera"
    elif camera_intensity <= 8:
        distance, angle, framing = (
            CameraDistance.MACRO,
            CameraAngle.SLIGHTLY_LOW,
            Framing.TIGHT,
        )
        note = "emphasized low-angle camera"
    else:
        distance, angle, framing = CameraDistance.MACRO, CameraAngle.LOW, Framing.TIGHT
        note = "dramatic hero camera"
    return CameraPlan(
        distance=distance,
        angle=angle,
        lens=Lens.MACRO_100,
        framing=framing,
        note=note,
    )


def lighting_for(lighting_priority: int) -> LightingPlan:
    """Lighting plan from lighting priority (1-10), studio to hard-key drama."""
    if lighting_priority >= 9:
        return LightingPlan(
            direction=LightDirection.KEY,
            style=LightingStyle.HARD_KEY,
            practical_sources=["dedicated spotlight"],
            key_color="white",
            note="high-priority dramatic lighting",
        )
    if lighting_priority >= 7:
        return LightingPlan(
            direction=LightDirection.KEY,
            style=LightingStyle.HARD_KEY,
            key_color="white",
            note="raised-contrast lighting",
        )
    return LightingPlan(
        direction=LightDirection.KEY,
        style=LightingStyle.STUDIO,
        key_color="white",
        note="clean studio lighting",
    )


def composition_for(
    camera_intensity: int, *, is_thumbnail: bool
) -> CompositionPlan:
    """Composition plan from camera intensity; thumbnails keep negative space."""
    if camera_intensity <= 6:
        rule, emphasis = CompositionRule.RULE_OF_THIRDS, "primary subject"
    elif camera_intensity <= 8:
        rule, emphasis = CompositionRule.SYMMETRICAL, "subject dominating the frame"
    else:
        rule, emphasis = CompositionRule.DIAGONAL, "hero subject dominating the frame"
    return CompositionPlan(
        rule=rule,
        emphasis=emphasis,
        negative_space=NegativeSpace.OVERLAY_TOP if is_thumbnail else NegativeSpace.NONE,
        note="directed by the AI Director",
    )


def motion_for(
    motion_budget: int, *, diagram_priority: int, goal: VisualGoal
) -> Motion:
    """Motion plan from the motion budget and the scene's visual nature."""
    is_diagram = diagram_priority >= 7
    if motion_budget <= 3:
        return Motion(type=MotionType.STATIC, speed=MotionSpeed.SLOW, loop=False)
    if motion_budget <= 6:
        return Motion(type=MotionType.PUSH_IN, speed=MotionSpeed.SLOW, loop=False)
    if motion_budget <= 8:
        kind = MotionType.PAN if is_diagram or goal is VisualGoal.COMPARE else MotionType.PUSH_IN
        return Motion(type=kind, speed=MotionSpeed.MEDIUM, loop=False)
    kind = (
        MotionType.SWEEP
        if is_diagram or goal is VisualGoal.COMPARE
        else MotionType.ORBIT
    )
    return Motion(type=kind, speed=MotionSpeed.MEDIUM, loop=False)


def mood_for(emotion: int, comparison_emphasis: int, diagram_priority: int) -> Mood:
    """Mood from emotion and emphasis; precise is the calm default."""
    if emotion >= 8:
        return Mood.DRAMATIC
    if comparison_emphasis >= 8:
        return Mood.COMPARATIVE
    if diagram_priority >= 8:
        return Mood.METHODICAL
    return Mood.PRECISE


def transition_between(
    emotion: int,
    *,
    comparison_emphasis: int,
    pacing: int,
    is_first: bool,
) -> Transition:
    """The cut into a scene, decided from emotion, emphasis, and pacing."""
    if is_first:
        return Transition(type=TransitionType.CUT, rationale="opening cut")
    if emotion >= 9:
        return Transition(type=TransitionType.FADE, rationale="fade into the emotional peak")
    if comparison_emphasis >= 7:
        return Transition(type=TransitionType.DISSOLVE, rationale="dissolve to the comparison")
    if pacing >= 7:
        return Transition(type=TransitionType.WIPE, rationale="wipe to the fast-paced beat")
    return Transition(type=TransitionType.CUT, rationale="continuity cut")


# --------------------------------------------------------- viz tokens -----


def visualization_for(
    type_: EngineeringVisualizationType, rationale: str
) -> EngineeringVisualization:
    """One engineering visualization whose tokens come from the type itself.

    Tokens intentionally do not duplicate the render optimizer's token
    table: the director only announces the overlay, the optimizer's table
    remains the single source for mutation tokens.
    """
    return EngineeringVisualization(
        type=type_,
        prompt_tokens=[type_.value],
        rationale=rationale,
    )


# ------------------------------------------------------------ prediction --


def attention_raw(
    importance: int,
    emotion: int,
    pacing: int,
    reveal_order: int,
    *,
    motion_budget: int,
    is_hero: bool,
    is_thumbnail: bool,
) -> float:
    """Unscaled expected-attention score for one scene (arbitrary units)."""
    raw = (
        importance * 12.0
        + emotion * 6.0
        + (pacing - 5) * 2.0
        + (reveal_order - 1) * 2.0
        + (8.0 if is_hero else 0.0)
        + (8.0 if is_thumbnail else 0.0)
        + (5.0 if motion_budget >= 8 else 0.0)
    )
    return max(0.0, raw)


def retention_score(
    importance: int,
    emotion: int,
    pacing: int,
    visual_budget: int,
) -> float:
    """Predicted retention for one scene, 0-100 (higher = more memorable)."""
    raw = (
        20.0
        + importance * 9.0
        + emotion * 4.0
        + (10.0 - abs(pacing - 5)) * 1.5
        + (visual_budget - 5) * 0.5
    )
    return round(min(100.0, max(0.0, raw)), 1)


def thumbnail_score(
    importance: int,
    emotion: int,
    motion_budget: int,
    diagram_priority: int,
    *,
    is_hero: bool,
    is_recap: bool,
) -> int:
    """Thumbnail pull score; the recap scene can never win."""
    if is_recap:
        return 0
    score = (
        importance * 10
        + emotion * 3
        + max(0, motion_budget - 5)
        + (4 if diagram_priority >= 7 else 0)
        + (10 if is_hero else 0)
    )
    return score
