"""Contracts for the Visual Intelligence Architecture.

The architecture replaces the single "topic -> prompt -> ComfyUI" hop with nine
stages that produce documentary-grade engineering imagery:

    1. Knowledge Extractor      (research -> engineering knowledge)
    2. Engineering Visual Analyzer (knowledge -> visualization strategy)
    3. Director AI              (strategy -> film-level decisions)
    4. Scene Planner            (narration -> cinematic scenes)
    5. Shot Planner             (scenes -> camera-designed shots)
    6. Visual Director          (shots -> lighting / mood / palette)
    7. Consistency Engine       (everything -> cross-shot baseline)
    8. Prompt Composer          (baseline -> production-grade prompts)
    9. Prompt Validator         (prompts -> scored, >=95, comfyui-ready)

Every model here is plain JSON data (``StableModel``) so each stage handoff
serializes losslessly and can be audited or replayed. The final output also
carries ``comfyui_ready`` variables that match the existing ComfyUI workflow
template placeholders exactly, so no provider or workflow change is required.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from pr1me.models.common import ScriptCorrections, StableModel
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.visual import ScriptBlockName

__all__ = [
    "CanonicalObject",
    "ComfyUIReady",
    "ComposedPrompt",
    "ConsistencyOutput",
    "CriterionScore",
    "DirectorOutput",
    "KnowledgeOutput",
    "Mechanism",
    "PaletteColor",
    "PromptCompositionOutput",
    "PromptFields",
    "PromptValidationOutput",
    "ScaleDescriptor",
    "Scene",
    "ScenePlanOutput",
    "Shot",
    "ShotConsistencyNote",
    "ShotPlanOutput",
    "ValidatedPrompt",
    "VisualArchitectureInput",
    "VisualClimax",
    "VisualIntelligenceOutput",
    "VisualizationStrategyOutput",
    "VisualizationStyle",
    "VisualStyleOutput",
    "VisualTreatment",
]

# ----------------------------------------------------------------------- input -


class VisualArchitectureInput(StageInput):
    """Input for the whole visual intelligence chain.

    Carries the approved narration (the same blocks the existing visual stage
    consumes) plus the fact-check verdict and any research-side factual
    context, so the knowledge layer never invents claims.
    """

    topic: str = Field(..., min_length=1, max_length=60)
    hook: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    practical_insight: str = Field(..., min_length=1)
    ending: str = Field(..., min_length=1)
    word_count: int | None = Field(default=None, ge=1, le=120)
    verdict: str | None = Field(default=None)
    corrections: ScriptCorrections = Field(default_factory=ScriptCorrections)
    factual_context: str | None = Field(default=None)


# -------------------------------------------------------------- stage 1: knowledge -


class Mechanism(StableModel):
    """One engineering mechanism the narration depends on."""

    name: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    physics_principles: list[str] = Field(default_factory=list)


class ScaleDescriptor(StableModel):
    """Physical scale reference for the subject."""

    reference_object: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)


class KnowledgeOutput(StageOutput):
    """Stage 1 output: engineering knowledge distilled from the narration."""

    concepts: list[str] = Field(default_factory=list)
    mechanisms: list[Mechanism] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)
    scale: ScaleDescriptor
    physics: list[str] = Field(default_factory=list)
    motion: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    critical_visual_elements: list[str] = Field(default_factory=list)
    forbidden_inaccuracies: list[str] = Field(default_factory=list)

    def primary_concept(self) -> str:
        """The single concept the visuals must emphasize."""
        if not self.concepts:
            return ""
        return self.concepts[0]

    def is_substantive(self) -> bool:
        """True when the knowledge block can drive a visual plan."""
        return bool(self.concepts or self.objects or self.materials or self.mechanisms)


# --------------------------------------------------------- stage 2: visual analyzer -


class VisualizationStyle(StrEnum):
    """Documentary visualization styles the analyzer may choose."""

    INDUSTRIAL_PHOTOGRAPHY = "industrial_photography"
    EXPLODED_CAD = "exploded_cad"
    CROSS_SECTION = "cross_section"
    MACRO_MECHANICAL = "macro_mechanical"
    ASSEMBLY_SEQUENCE = "assembly_sequence"
    MANUFACTURING_PROCESS = "manufacturing_process"
    SIMULATION = "simulation"
    BLUEPRINT = "blueprint"
    TECHNICAL_ILLUSTRATION = "technical_illustration"
    REAL_WORLD_COMPARISON = "real_world_comparison"
    MATERIAL_VISUALIZATION = "material_visualization"
    MICROSCOPE = "microscope"
    SLOW_MOTION = "slow_motion"


class VisualizationStrategyOutput(StageOutput):
    """Stage 2 output: the single best way to teach the concept on screen."""

    style: VisualizationStyle
    rationale: str = Field(..., min_length=1)
    alternatives: list[str] = Field(default_factory=list)
    educational_requirement: str = Field(..., min_length=1)


# -------------------------------------------------------- stage 2.5: director -


class VisualTreatment(StableModel):
    """One concept-level visual treatment the director mandates.

    ``treatment`` names the rendering requirement the shot covering
    ``concept`` must satisfy: extreme macro detail, an exploded view, or a
    mechanism caught mid-motion. The Prompt Composer turns the treatment into
    concrete prompt guidance.
    """

    concept: str = Field(..., min_length=1)
    treatment: Literal["macro_detail", "exploded_view", "animation"]
    reason: str = Field(..., min_length=1)


class VisualClimax(StableModel):
    """The single strongest visual moment of the Short."""

    concept: str = Field(..., min_length=1)
    block: ScriptBlockName
    moment: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class DirectorOutput(StageOutput):
    """Stage 2.5 output: the director's film-level decisions.

    The Director thinks like a documentary filmmaker *before* any scene or
    shot exists: what the viewer must see, what must never appear, the
    strongest teaching method, where attention goes in each narration block,
    the visual climax, the scene that deserves the highest quality, and which
    concepts need macro / exploded / animation treatments. The Scene Planner,
    Shot Planner, and Prompt Composer consume these decisions downstream.
    """

    show: list[str] = Field(default_factory=list)
    hide: list[str] = Field(default_factory=list)
    teaching_method: str = Field(..., min_length=1)
    attention_flow: list[str] = Field(default_factory=list)
    climax: VisualClimax
    hero_shot_focus: str = Field(..., min_length=1)
    treatments: list[VisualTreatment] = Field(default_factory=list)


# ---------------------------------------------------------------- stage 3: scenes -


class Scene(StableModel):
    """One cinematic scene mapped from a narration block."""

    id: int
    narration_block: ScriptBlockName
    purpose: str = Field(..., min_length=1)
    teaching_goal: str = Field(..., min_length=1)
    concept: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    environment: str = Field(..., min_length=1)
    foreground: str = Field(..., min_length=1)
    background: str = Field(..., min_length=1)
    objects: list[str] = Field(default_factory=list)
    camera_importance: str = Field(..., min_length=1)
    viewer_takeaway: str = Field(..., min_length=1)
    seconds_allocated: float = Field(..., gt=0.0)


class ScenePlanOutput(StageOutput):
    """Stage 3 output: the narration broken into cinematic scenes."""

    scenes: list[Scene] = Field(default_factory=list)
    total_seconds: float = Field(default=0.0, gt=0.0)


# ----------------------------------------------------------------- stage 4: shots -


class Shot(StableModel):
    """One fully camera-designed shot."""

    id: int
    scene_id: int
    narration_block: ScriptBlockName
    duration_seconds: float = Field(..., gt=0.0)
    shot_type: str = Field(..., min_length=1)
    camera_angle: str = Field(..., min_length=1)
    lens: str = Field(..., min_length=1)
    camera_movement: str = Field(..., min_length=1)
    distance: str = Field(..., min_length=1)
    framing: str = Field(..., min_length=1)
    depth: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    focus: str = Field(..., min_length=1)
    motion: str = Field(..., min_length=1)
    transition: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    is_thumbnail: bool = False
    is_climax: bool = False
    is_hero: bool = False
    treatment: str = ""


class ShotPlanOutput(StageOutput):
    """Stage 4 output: the shot list with intentional camera language."""

    shots: list[Shot] = Field(default_factory=list)


# --------------------------------------------------------------- stage 5: director -


class PaletteColor(StableModel):
    """One role-bound color in the shot's engineering color language."""

    role: Literal[
        "background", "accent", "text", "success", "warning", "failure", "motion"
    ]
    hex: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    usage: str = Field(..., min_length=1)


class VisualStyleOutput(StageOutput):
    """Stage 5 output: the cinematic look applied to every shot."""

    lighting: str = Field(..., min_length=1)
    mood: str = Field(..., min_length=1)
    color_palette: list[PaletteColor] = Field(default_factory=list)
    atmosphere: str = Field(..., min_length=1)
    rendering_style: str = Field(..., min_length=1)
    contrast: str = Field(..., min_length=1)
    texture_richness: str = Field(..., min_length=1)
    realism_level: str = Field(..., min_length=1)
    storytelling_arc: str = Field(..., min_length=1)
    thumbnail_mode: bool = False


# -------------------------------------------------------- stage 6: consistency engine -


class CanonicalObject(StableModel):
    """A persistent object identity shared across every shot."""

    name: str = Field(..., min_length=1)
    canonical_descriptor: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    persistent: bool = True


class ShotConsistencyNote(StableModel):
    """Consistency constraints pinned to one shot."""

    shot_id: int
    anchors: list[str] = Field(default_factory=list)


class ConsistencyOutput(StageOutput):
    """Stage 6 output: the cross-shot consistency baseline."""

    object_registry: list[CanonicalObject] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    lighting_direction: str = Field(..., min_length=1)
    palette: list[PaletteColor] = Field(default_factory=list)
    perspective_convention: str = Field(..., min_length=1)
    environment: str = Field(..., min_length=1)
    scale_anchor: str = Field(..., min_length=1)
    camera_language: str = Field(..., min_length=1)
    lens_language: str = ""
    object_appearance: str = ""
    continuity_anchors: list[str] = Field(default_factory=list)
    shot_notes: list[ShotConsistencyNote] = Field(default_factory=list)


# ----------------------------------------------------------- stage 7: prompt composer -


class PromptFields(StableModel):
    """Structured prompt fields; the positive prompt is built from these."""

    subject: str = Field(..., min_length=1)
    environment: str = Field(..., min_length=1)
    composition: str = Field(..., min_length=1)
    camera: str = Field(..., min_length=1)
    lens: str = Field(..., min_length=1)
    lighting: str = Field(..., min_length=1)
    materials: str = Field(..., min_length=1)
    surface_detail: str = Field(..., min_length=1)
    physics: str = Field(..., min_length=1)
    scale: str = Field(..., min_length=1)
    atmosphere: str = Field(..., min_length=1)
    rendering_style: str = Field(..., min_length=1)
    engineering_detail: str = Field(..., min_length=1)
    visual_storytelling: str = Field(..., min_length=1)
    focus: str = Field(..., min_length=1)
    depth: str = Field(..., min_length=1)


class ComposedPrompt(StableModel):
    """One production-grade, ComfyUI-ready prompt for a single shot."""

    shot_id: int
    narration_block: ScriptBlockName
    fields: PromptFields
    positive_prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    quality_constraints: list[str] = Field(default_factory=list)
    is_thumbnail: bool = False


class PromptCompositionOutput(StageOutput):
    """Stage 7 output: one composed prompt per planned shot."""

    prompts: list[ComposedPrompt] = Field(default_factory=list)


# ---------------------------------------------------------- stage 8: prompt validator -


class CriterionScore(StableModel):
    """Score of one validation criterion."""

    name: str = Field(..., min_length=1)
    score: int = Field(..., ge=0)
    max: int = Field(..., ge=0)
    notes: str = ""


class ValidatedPrompt(StableModel):
    """A composed prompt plus its validation verdict."""

    shot_id: int
    score: int = Field(..., ge=0, le=100)
    status: Literal["passed", "regenerated", "rejected"]
    issues: list[str] = Field(default_factory=list)
    criteria: list[CriterionScore] = Field(default_factory=list)
    positive_prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)


class PromptValidationOutput(StageOutput):
    """Stage 8 output: scored prompts, all at or above the 95-point bar."""

    status: Literal["ok", "regenerated", "rejected"]
    attempts: int = Field(..., ge=1)
    prompts: list[ValidatedPrompt] = Field(default_factory=list)


# -------------------------------------------------------------- final deliverable -


class ComfyUIReady(StableModel):
    """A prompt packaged exactly for the existing ComfyUI workflow template."""

    shot_id: int
    positive_prompt: str = Field(..., min_length=1)
    negative_prompt: str = Field(..., min_length=1)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    seed: int = Field(..., ge=0, le=2**63 - 1)
    steps: int = Field(..., ge=1, le=150)
    cfg: float = Field(..., ge=0.0, le=20.0)
    sampler: str = Field(..., min_length=1)
    scheduler: str = Field(..., min_length=1)

    def to_comfyui_variables(self) -> dict[str, object]:
        """Return the variable dict consumed by ``ComfyUIProvider.render``.

        The keys match the placeholders of ``workflows/comfyui.json`` exactly,
        so the output can be rendered without touching the provider.
        """
        return {
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "steps": self.steps,
            "cfg": self.cfg,
            "sampler": self.sampler,
            "scheduler": self.scheduler,
        }


class VisualIntelligenceOutput(StageOutput):
    """The complete, auditable result of the eight-stage visual chain."""

    knowledge: KnowledgeOutput
    strategy: VisualizationStrategyOutput
    director: DirectorOutput
    scene_plan: ScenePlanOutput
    shot_plan: ShotPlanOutput
    visual_style: VisualStyleOutput
    consistency: ConsistencyOutput
    composition: PromptCompositionOutput
    validation: PromptValidationOutput
    comfyui_ready: list[ComfyUIReady] = Field(default_factory=list)
