"""Visual goals: the semantic intent of each scene, classified deterministically.

A VisualGoal describes WHAT the viewer must understand from a scene before any
shot, camera, or lighting decision is made. Classification is keyword-driven
and position-aware (first scene defaults to introduction, last to summary),
so the same classifier runs in production and in tests with identical output.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from knowledge.visual_architecture import Modality, Scene

VISUAL_GOALS: tuple[str, ...] = (
    "introduce",
    "compare",
    "reveal_internal_geometry",
    "explain_process",
    "explain_motion",
    "explain_force_flow",
    "explain_heat_flow",
    "explain_assembly",
    "explain_manufacturing",
    "explain_scale",
    "explain_failure",
    "explain_optimization",
    "explain_material_properties",
    "explain_mechanism",
    "highlight_difference",
    "summarize",
)


class VisualGoal(StrEnum):
    INTRODUCE_CONCEPT = "introduce"
    COMPARE = "compare"
    REVEAL_INTERNAL_GEOMETRY = "reveal_internal_geometry"
    EXPLAIN_PROCESS = "explain_process"
    EXPLAIN_MOTION = "explain_motion"
    EXPLAIN_FORCE_FLOW = "explain_force_flow"
    EXPLAIN_HEAT_FLOW = "explain_heat_flow"
    EXPLAIN_ASSEMBLY = "explain_assembly"
    EXPLAIN_MANUFACTURING = "explain_manufacturing"
    EXPLAIN_SCALE = "explain_scale"
    EXPLAIN_FAILURE = "explain_failure"
    EXPLAIN_OPTIMIZATION = "explain_optimization"
    EXPLAIN_MATERIAL_PROPERTIES = "explain_material_properties"
    EXPLAIN_MECHANISM = "explain_mechanism"
    HIGHLIGHT_DIFFERENCE = "highlight_difference"
    SUMMARIZE = "summarize"


_KEYWORD_RULES: tuple[tuple[str, VisualGoal], ...] = (
    ("hook", VisualGoal.INTRODUCE_CONCEPT),
    ("introduce", VisualGoal.INTRODUCE_CONCEPT),
    ("what is", VisualGoal.INTRODUCE_CONCEPT),
    ("overview", VisualGoal.INTRODUCE_CONCEPT),
    ("takeaway", VisualGoal.SUMMARIZE),
    ("summary", VisualGoal.SUMMARIZE),
    ("conclusion", VisualGoal.SUMMARIZE),
    ("remember", VisualGoal.SUMMARIZE),
    ("recap", VisualGoal.SUMMARIZE),
    ("vs", VisualGoal.COMPARE),
    ("versus", VisualGoal.COMPARE),
    ("compare", VisualGoal.COMPARE),
    ("side-by-side", VisualGoal.COMPARE),
    ("comparison", VisualGoal.COMPARE),
    ("difference", VisualGoal.HIGHLIGHT_DIFFERENCE),
    ("differ", VisualGoal.HIGHLIGHT_DIFFERENCE),
    ("fail", VisualGoal.EXPLAIN_FAILURE),
    ("crack", VisualGoal.EXPLAIN_FAILURE),
    ("break", VisualGoal.EXPLAIN_FAILURE),
    ("warp", VisualGoal.EXPLAIN_FAILURE),
    ("defect", VisualGoal.EXPLAIN_FAILURE),
    ("snag", VisualGoal.EXPLAIN_FAILURE),
    ("fracture", VisualGoal.EXPLAIN_FAILURE),
    ("heat", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("temperature", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("thermal", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("warm", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("cool", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("infrared", VisualGoal.EXPLAIN_HEAT_FLOW),
    ("force", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("load", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("stress", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("torque", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("shear", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("tension", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("compression", VisualGoal.EXPLAIN_FORCE_FLOW),
    ("motion", VisualGoal.EXPLAIN_MOTION),
    ("moves", VisualGoal.EXPLAIN_MOTION),
    ("movement", VisualGoal.EXPLAIN_MOTION),
    ("rotate", VisualGoal.EXPLAIN_MOTION),
    ("rotation", VisualGoal.EXPLAIN_MOTION),
    ("slide", VisualGoal.EXPLAIN_MOTION),
    ("spin", VisualGoal.EXPLAIN_MOTION),
    ("assembly", VisualGoal.EXPLAIN_ASSEMBLY),
    ("assemble", VisualGoal.EXPLAIN_ASSEMBLY),
    ("fits together", VisualGoal.EXPLAIN_ASSEMBLY),
    ("exploded", VisualGoal.EXPLAIN_ASSEMBLY),
    ("manufactur", VisualGoal.EXPLAIN_MANUFACTURING),
    ("extrud", VisualGoal.EXPLAIN_MANUFACTURING),
    ("mold", VisualGoal.EXPLAIN_MANUFACTURING),
    ("produce", VisualGoal.EXPLAIN_MANUFACTURING),
    ("machine", VisualGoal.EXPLAIN_MANUFACTURING),
    ("scale", VisualGoal.EXPLAIN_SCALE),
    ("size", VisualGoal.EXPLAIN_SCALE),
    ("micron", VisualGoal.EXPLAIN_SCALE),
    ("dimension", VisualGoal.EXPLAIN_SCALE),
    ("proportion", VisualGoal.EXPLAIN_SCALE),
    ("process", VisualGoal.EXPLAIN_PROCESS),
    ("sequence", VisualGoal.EXPLAIN_PROCESS),
    ("step", VisualGoal.EXPLAIN_PROCESS),
    ("mechanism", VisualGoal.EXPLAIN_MECHANISM),
    ("gear", VisualGoal.EXPLAIN_MECHANISM),
    ("linkage", VisualGoal.EXPLAIN_MECHANISM),
    ("cam", VisualGoal.EXPLAIN_MECHANISM),
    ("lever", VisualGoal.EXPLAIN_MECHANISM),
    ("optimiz", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("lightweight", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("efficient", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("reduce", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("lighter", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("stronger", VisualGoal.EXPLAIN_OPTIMIZATION),
    ("material", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("property", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("stiff", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("ductile", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("brittle", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("filament", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("alloy", VisualGoal.EXPLAIN_MATERIAL_PROPERTIES),
    ("inside", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("internal", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("cut open", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("cutaway", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("cross-section", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("cross section", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("expose", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("reveal", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("lattice", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
    ("infill", VisualGoal.REVEAL_INTERNAL_GEOMETRY),
)


_MODALITY_FALLBACKS: dict[Modality, VisualGoal] = {
    Modality.CROSS_SECTION: VisualGoal.REVEAL_INTERNAL_GEOMETRY,
    Modality.MACRO_INSPECTION: VisualGoal.REVEAL_INTERNAL_GEOMETRY,
    Modality.EXPLODED_VIEW: VisualGoal.EXPLAIN_ASSEMBLY,
    Modality.SPLIT_COMPARE: VisualGoal.COMPARE,
    Modality.DIAGRAM: VisualGoal.EXPLAIN_MECHANISM,
    Modality.SCHEMATIC: VisualGoal.EXPLAIN_PROCESS,
    Modality.PHOTOREAL: VisualGoal.INTRODUCE_CONCEPT,
}


def classify_visual_goal(
    scene: Scene,
    *,
    scene_index: int,
    scene_count: int,
    keywords: Sequence[str] = (),
    summary: str = "",
) -> VisualGoal:
    """Classify the semantic intent of one scene, deterministically.

    Keyword rules run in priority order over the scene's engineering and
    teaching goals, the topic keywords, and the engineering summary. When
    nothing matches, position rules apply (first scene introduces, last
    scene summarizes), then the scene modality decides.
    """
    text = " ".join(
        part
        for part in (scene.engineering_goal, scene.teaching_goal, summary, " ".join(keywords))
        if part
    ).lower()

    for token, goal in _KEYWORD_RULES:
        if token in text:
            return goal

    if scene_index == 1:
        return VisualGoal.INTRODUCE_CONCEPT
    if scene_index == scene_count:
        return VisualGoal.SUMMARIZE
    return _MODALITY_FALLBACKS.get(scene.modality, VisualGoal.EXPLAIN_PROCESS)