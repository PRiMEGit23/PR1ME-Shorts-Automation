"""Shot selection: the cinematic archetype that realizes a visual goal.

ShotType lives in the storyboard schema (knowledge.visual_intelligence.storyboard);
this module owns the deterministic decision table: which shot archetype a goal
maps to, the prompt prefix each shot type compiles to, and the set of shot
types that must carry diagram-style negatives.
"""

from __future__ import annotations

from knowledge.visual_architecture import Modality, Scene
from knowledge.visual_intelligence.storyboard import ShotType
from knowledge.visual_intelligence.visual_goal import VisualGoal

SHOT_PREFIXES: dict[ShotType, str] = {
    ShotType.MACRO: "macro photograph of",
    ShotType.EXTREME_MACRO: "extreme macro photograph of",
    ShotType.HERO: "hero photograph of",
    ShotType.CROSS_SECTION: "cross-section cutaway of",
    ShotType.CUTAWAY: "cutaway view of",
    ShotType.TRANSPARENT: "transparent view of",
    ShotType.EXPLODED_VIEW: "exploded view diagram of",
    ShotType.ISOMETRIC: "isometric diagram of",
    ShotType.ORTHOGRAPHIC: "orthographic diagram of",
    ShotType.BLUEPRINT: "blueprint drawing of",
    ShotType.CAD_RENDER: "CAD render of",
    ShotType.MICROSCOPE: "microscope image of",
    ShotType.SLOW_MOTION: "slow motion photograph of",
    ShotType.TIME_LAPSE: "time lapse photograph of",
    ShotType.PROCESS_SEQUENCE: "step-by-step process diagram of",
    ShotType.BEFORE_AFTER: "before and after comparison of",
    ShotType.COMPARISON_SPLIT: "split-screen comparison of",
    ShotType.XRAY: "X-ray view of",
    ShotType.WIREFRAME_OVERLAY: "wireframe overlay view of",
    ShotType.ANNOTATED_DIAGRAM: "annotated technical diagram of",
    ShotType.MANUFACTURING_SEQUENCE: "manufacturing sequence diagram of",
}

DIAGRAM_LIKE_SHOTS: frozenset[ShotType] = frozenset(
    {
        ShotType.CROSS_SECTION,
        ShotType.CUTAWAY,
        ShotType.EXPLODED_VIEW,
        ShotType.ISOMETRIC,
        ShotType.ORTHOGRAPHIC,
        ShotType.BLUEPRINT,
        ShotType.PROCESS_SEQUENCE,
        ShotType.XRAY,
        ShotType.WIREFRAME_OVERLAY,
        ShotType.ANNOTATED_DIAGRAM,
        ShotType.MANUFACTURING_SEQUENCE,
    }
)

_ROW_SHOTS: frozenset[ShotType] = frozenset(
    {
        ShotType.PROCESS_SEQUENCE,
        ShotType.BEFORE_AFTER,
        ShotType.COMPARISON_SPLIT,
        ShotType.MANUFACTURING_SEQUENCE,
    }
)

_GOAL_SHOT_TABLE: dict[VisualGoal, ShotType] = {
    VisualGoal.INTRODUCE_CONCEPT: ShotType.HERO,
    VisualGoal.COMPARE: ShotType.COMPARISON_SPLIT,
    VisualGoal.REVEAL_INTERNAL_GEOMETRY: ShotType.CROSS_SECTION,
    VisualGoal.EXPLAIN_PROCESS: ShotType.PROCESS_SEQUENCE,
    VisualGoal.EXPLAIN_MOTION: ShotType.SLOW_MOTION,
    VisualGoal.EXPLAIN_FORCE_FLOW: ShotType.ANNOTATED_DIAGRAM,
    VisualGoal.EXPLAIN_HEAT_FLOW: ShotType.ANNOTATED_DIAGRAM,
    VisualGoal.EXPLAIN_ASSEMBLY: ShotType.EXPLODED_VIEW,
    VisualGoal.EXPLAIN_MANUFACTURING: ShotType.MANUFACTURING_SEQUENCE,
    VisualGoal.EXPLAIN_SCALE: ShotType.ORTHOGRAPHIC,
    VisualGoal.EXPLAIN_FAILURE: ShotType.CUTAWAY,
    VisualGoal.EXPLAIN_OPTIMIZATION: ShotType.CAD_RENDER,
    VisualGoal.EXPLAIN_MATERIAL_PROPERTIES: ShotType.MACRO,
    VisualGoal.EXPLAIN_MECHANISM: ShotType.ANNOTATED_DIAGRAM,
    VisualGoal.HIGHLIGHT_DIFFERENCE: ShotType.BEFORE_AFTER,
    VisualGoal.SUMMARIZE: ShotType.HERO,
}

_MODALITY_FORCES: dict[Modality, ShotType] = {
    Modality.CROSS_SECTION: ShotType.CROSS_SECTION,
    Modality.EXPLODED_VIEW: ShotType.EXPLODED_VIEW,
    Modality.SPLIT_COMPARE: ShotType.COMPARISON_SPLIT,
    Modality.MACRO_INSPECTION: ShotType.MACRO,
}

_FALLBACK_SHOT = ShotType.MACRO


def _text_has(scene: Scene, *tokens: str) -> bool:
    text = " ".join(
        part
        for part in (scene.engineering_goal, scene.teaching_goal, scene.action, scene.visual_focus)
        if part
    ).lower()
    return any(token in text for token in tokens)


def select_shot_type(
    goal: VisualGoal,
    scene: Scene,
) -> ShotType:
    """Pick the shot archetype for a scene, deterministically.

    The spec's modality is a hard constraint when it names a specific shot
    genre (cross-section, exploded view, split compare, macro). Otherwise the
    goal table decides, with a few goal-specific refinements driven by scene
    text, and a deterministic fallback.
    """
    forced = _MODALITY_FORCES.get(scene.modality)
    if forced is not None:
        return forced

    shot = _GOAL_SHOT_TABLE[goal]

    if goal is VisualGoal.REVEAL_INTERNAL_GEOMETRY:
        if scene.secondary_subjects or _text_has(scene, "housing", "enclosure", "case", "shell"):
            return ShotType.TRANSPARENT
        return shot

    if goal is VisualGoal.EXPLAIN_MATERIAL_PROPERTIES:
        if _text_has(scene, "microscop", "grain", "fiber", "crystal"):
            return ShotType.MICROSCOPE
        return shot

    if goal is VisualGoal.EXPLAIN_FAILURE:
        if _text_has(scene, "crack", "fracture", "tear", "snap"):
            return ShotType.MACRO
        return shot

    if goal is VisualGoal.EXPLAIN_SCALE:
        return ShotType.ORTHOGRAPHIC

    return shot


def is_row_shot(shot: ShotType) -> bool:
    """True for shots that lay options side by side in a row."""
    return shot in _ROW_SHOTS


def is_diagram_like(shot: ShotType) -> bool:
    """True for shots that must reject photographic artifacts."""
    return shot in DIAGRAM_LIKE_SHOTS