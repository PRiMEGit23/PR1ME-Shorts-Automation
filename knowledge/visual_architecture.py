"""Knowledge Base V2 visual architecture: model-agnostic visual specification.

Defines WHAT exists in a scene (subjects, geometry, materials, manufacturing
detail) and HOW it is shot (camera, lighting, composition, motion). It stores
no rendering quality tokens, no model syntax, and no prompt strings. The
Prompt Compiler subsystem (knowledge/compiler) converts these specifications
into model-specific prompts (SDXL, FLUX, GPT Image, Qwen Image, future).

Fully additive: nothing in the V1 runtime (build_knowledge_csv.py,
validate_knowledge_csv.py, knowledge/schema.py) imports this module.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "2.0"
MIN_SCENES = 4
MAX_SCENES = 6
MAX_SECONDARY_SUBJECTS = 3
MAX_THUMBNAIL_CANDIDATES = 2


class EngineeringDomain(StrEnum):
    """Drives the engineering term registry that guards manufacturing accuracy."""

    FDM = "FDM"
    RESIN_AM = "resin AM"
    INDUSTRIAL_AM = "industrial AM"
    CNC_MACHINING = "CNC machining"
    INJECTION_MOLDING = "injection molding"
    SHEET_METAL = "sheet metal"
    ELECTRONICS = "electronics"
    MECHANISMS = "mechanisms"
    MATERIALS_SCIENCE = "materials science"
    THERMODYNAMICS = "thermodynamics"
    METROLOGY = "metrology"
    TOOLING = "tooling"
    DESIGN_CAD = "design CAD"
    FINISHING = "finishing"
    SAFETY = "safety"
    WORKSHOP = "workshop"


class Modality(StrEnum):
    """The image genre of a scene; the compiler maps it to model syntax."""

    PHOTOREAL = "photoreal"
    DIAGRAM = "diagram"
    MACRO_INSPECTION = "macro inspection"
    CROSS_SECTION = "cross-section"
    SCHEMATIC = "schematic"
    EXPLODED_VIEW = "exploded view"
    SPLIT_COMPARE = "split compare"


class CameraDistance(StrEnum):
    MACRO = "macro"
    CLOSE = "close-up"
    MEDIUM = "medium"
    WIDE = "wide"
    ESTABLISHING = "establishing"


class CameraAngle(StrEnum):
    EYE = "eye level"
    SLIGHTLY_LOW = "slightly low"
    LOW = "low"
    HIGH = "high"
    OVERHEAD = "overhead"
    DUTCH = "dutch"


class Lens(StrEnum):
    WIDE_24 = "24mm"
    STANDARD_35 = "35mm"
    PORTRAIT_50 = "50mm"
    TELE_85 = "85mm"
    MACRO_100 = "100mm macro"


class Framing(StrEnum):
    TIGHT = "tight"
    MEDIUM_FRAME = "medium"
    LOOSE = "loose"
    SUBJECT_CENTER = "subject centered"
    SUBJECT_LEFT = "subject left"
    SUBJECT_RIGHT = "subject right"
    CENTER_ROW = "center row"
    RULE_OF_THIRDS = "rule of thirds"


class CameraHeight(StrEnum):
    TABLE = "table"
    EYE_LEVEL = "eye level"
    OVERHEAD = "overhead"


class CompositionRule(StrEnum):
    RULE_OF_THIRDS = "rule of thirds"
    CENTERED = "centered"
    CENTER_ROW = "center row"
    LEFT_HEAVY = "left heavy"
    RIGHT_HEAVY = "right heavy"
    DIAGONAL = "diagonal"
    SYMMETRICAL = "symmetrical"


class NegativeSpace(StrEnum):
    NONE = "none"
    OVERLAY_TOP = "overlay top"
    OVERLAY_LEFT = "overlay left"
    OVERLAY_RIGHT = "overlay right"
    OVERLAY_BOTTOM = "overlay bottom"


class DepthOfField(StrEnum):
    SHALLOW = "shallow"
    MEDIUM = "medium"
    DEEP = "deep"
    FULL = "full"


class LightDirection(StrEnum):
    KEY = "key"
    SIDE = "side"
    RIM = "rim"
    BACK = "back"
    PRACTICAL = "practical"
    OVERHEAD_DIR = "overhead"
    MIXED = "mixed"


class LightingStyle(StrEnum):
    STUDIO = "studio"
    RAKING = "raking"
    TASK = "task"
    SOFTBOX = "softbox"
    HARD_KEY = "hard key"
    HIGH_BAY = "high bay"
    PRACTICAL_GLOW = "practical glow"
    GRADIENT = "gradient"


class Material(StrEnum):
    PLA = "PLA"
    ABS = "ABS"
    PETG = "PETG"
    NYLON = "nylon"
    TPU = "TPU"
    POLYCARBONATE = "polycarbonate"
    PEEK = "PEEK"
    RESIN = "resin"
    STAINLESS_STEEL = "stainless steel"
    ALUMINIUM = "aluminium"
    STEEL = "steel"
    BRASS = "brass"
    COPPER = "copper"
    TITANIUM = "titanium"
    CARBON_FIBER = "carbon fiber"
    GLASS = "glass"
    RUBBER = "rubber"
    WOOD = "wood"
    GRAPHITE = "graphite"
    CERAMIC = "ceramic"


class SurfaceFinish(StrEnum):
    SMOOTH = "smooth"
    MATTE = "matte"
    GLOSSY = "glossy"
    RIDGED = "ridged"
    MACHINED = "machined"
    ANODISED = "anodised"
    BRUSHED = "brushed"
    SANDED = "sanded"
    POWDER_COATED = "powder coated"
    LAYER_LINES = "layer lines"
    POLISHED = "polished"
    GALVANISED = "galvanised"


class Mood(StrEnum):
    CLINICAL = "clinical"
    PRECISE = "precise"
    DRAMATIC = "dramatic"
    COMPARATIVE = "comparative"
    METHODICAL = "methodical"
    INDUSTRIAL = "industrial"
    WARM = "warm"
    CALM = "calm"
    ROBUST = "robust"
    ENERGETIC = "energetic"
    METICULOUS = "meticulous"
    STARK = "stark"


class MotionType(StrEnum):
    STATIC = "static"
    PAN = "pan"
    PUSH_IN = "push-in"
    ORBIT = "orbit"
    ZOOM = "zoom"
    TILT = "tilt"
    TRACK = "track"
    TURNTABLE = "turntable"
    SWEEP = "sweep"


class MotionSpeed(StrEnum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class TransitionType(StrEnum):
    CUT = "cut"
    FADE = "fade"
    WIPE = "wipe"
    DISSOLVE = "dissolve"
    NONE = "none"


class TextPosition(StrEnum):
    UPPER_THIRD = "upper_third"
    CENTER = "center"
    LOWER_THIRD = "lower_third"


class Contrast(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"


class Subject(BaseModel):
    """What physically exists in the scene: entity, geometry, materials."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entity: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=400)
    state: str = Field(default="", max_length=200)
    materials: list[Material] = Field(default_factory=list)
    surface_finish: list[SurfaceFinish] = Field(default_factory=list)
    manufacturing_details: list[str] = Field(default_factory=list, max_length=8)
    visible_geometry: list[str] = Field(default_factory=list, max_length=8)


class Camera(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    distance: CameraDistance
    angle: CameraAngle
    lens: Lens
    framing: Framing
    height: CameraHeight = CameraHeight.TABLE


class Composition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: CompositionRule
    emphasis: str = Field(min_length=1, max_length=120)
    negative_space: NegativeSpace = NegativeSpace.NONE
    note: str = Field(default="", max_length=200)


class Depth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    foreground: str | None = None
    midground: str = Field(min_length=1, max_length=120)
    background: str = Field(min_length=1, max_length=120)
    dof: DepthOfField = DepthOfField.MEDIUM


class Lighting(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    direction: LightDirection
    style: LightingStyle
    practical_sources: list[str] = Field(default_factory=list)
    key_color: str = Field(default="", max_length=60)


class ColorPalette(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base: str = Field(min_length=1, max_length=60)
    accent: str = Field(default="", max_length=60)
    note: str = Field(default="", max_length=200)


class Motion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: MotionType = MotionType.STATIC
    path: str = Field(default="", max_length=200)
    speed: MotionSpeed = MotionSpeed.SLOW
    loop: bool = False


class ScaleReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity: str = Field(min_length=1, max_length=80)
    size: str = Field(min_length=1, max_length=40)
    placement: str = Field(default="", max_length=120)


class TransitionHint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: TransitionType = TransitionType.CUT
    direction: str | None = None


class SubjectHierarchy(BaseModel):
    """Explicit role assignment: nothing competes equally for attention."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    primary: str = Field(min_length=1, max_length=120)
    secondary: list[str] = Field(default_factory=list, max_length=3)
    background: str = Field(min_length=1, max_length=120)
    focus_object: str = Field(min_length=1, max_length=120)


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    modality: Modality
    primary_subject: Subject
    secondary_subjects: list[Subject] = Field(default_factory=list, max_length=MAX_SECONDARY_SUBJECTS)
    subject_hierarchy: SubjectHierarchy
    action: str = Field(default="", max_length=200)
    engineering_goal: str = Field(default="", max_length=120)
    teaching_goal: str = Field(default="", max_length=120)
    visual_focus: str = Field(min_length=1, max_length=120)
    camera: Camera
    composition: Composition
    depth: Depth
    environment: str = Field(default="", max_length=120)
    lighting: Lighting
    color_palette: ColorPalette
    mood: Mood
    motion: Motion = Field(default_factory=Motion)
    scale_reference: ScaleReference | None = None
    objects_to_avoid: list[str] = Field(default_factory=list, max_length=12)
    negative_elements: list[str] = Field(default_factory=list, max_length=12)
    consistency_tags: list[str] = Field(default_factory=list, max_length=12)
    branding_tags: list[str] = Field(default_factory=list, max_length=8)
    transition_hint: TransitionHint = Field(default_factory=TransitionHint)
    scene_importance: int = Field(default=3, ge=1, le=5)
    thumbnail_candidate: bool = False

    @model_validator(mode="after")
    def _hierarchy_must_match_subjects(self) -> Scene:
        hierarchy = self.subject_hierarchy
        if hierarchy.primary != self.primary_subject.entity:
            raise ValueError(
                f"hierarchy primary '{hierarchy.primary}' != primary subject entity "
                f"'{self.primary_subject.entity}'"
            )
        secondary_entities = {s.entity for s in self.secondary_subjects}
        if set(hierarchy.secondary) != secondary_entities:
            raise ValueError(
                f"hierarchy secondary {sorted(hierarchy.secondary)} != subject entities "
                f"{sorted(secondary_entities)}"
            )
        if hierarchy.focus_object not in {hierarchy.primary, *hierarchy.secondary}:
            raise ValueError(
                f"focus_object '{hierarchy.focus_object}' is not a primary or secondary subject"
            )
        return self


class TextSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    string: str = Field(min_length=1, max_length=60)
    position: TextPosition = TextPosition.UPPER_THIRD
    max_chars: int = Field(default=28, ge=1, le=60)
    contrast: Contrast = Contrast.HIGH


class Background(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: str = Field(min_length=1, max_length=120)
    depth: DepthOfField = DepthOfField.SHALLOW


class Thumbnail(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    modality: Modality
    primary_subject: Subject
    secondary_subjects: list[Subject] = Field(default_factory=list)
    background: Background
    focus_object: str = Field(min_length=1, max_length=120)
    composition: Composition
    text_slot: TextSlot
    camera: Camera
    lighting: Lighting
    color_palette: ColorPalette
    mood: Mood
    exclude: list[str] = Field(default_factory=list, max_length=12)
    consistency_tags: list[str] = Field(default_factory=list, max_length=12)
    branding_tags: list[str] = Field(default_factory=list, max_length=8)


class VisualArchitecture(BaseModel):
    """The model-agnostic visual specification for one curated topic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = SCHEMA_VERSION
    world_id: str = Field(min_length=1, max_length=60)
    engineering_domain: EngineeringDomain
    modality: Modality
    derived: bool = False
    scenes: list[Scene] = Field(min_length=MIN_SCENES, max_length=MAX_SCENES)
    thumbnail: Thumbnail

    @model_validator(mode="after")
    def _scenes_must_be_consecutive_and_unique(self) -> VisualArchitecture:
        ids = [s.scene_id for s in self.scenes]
        expected = [f"S{i}" for i in range(1, len(ids) + 1)]
        if ids != expected:
            raise ValueError(f"scene ids must be consecutive S1..S{len(ids)}, got {ids}")
        return self

    @model_validator(mode="after")
    def _thumbnail_candidates_limited(self) -> VisualArchitecture:
        candidates = [s for s in self.scenes if s.thumbnail_candidate]
        if len(candidates) > MAX_THUMBNAIL_CANDIDATES:
            raise ValueError(
                f"at most {MAX_THUMBNAIL_CANDIDATES} thumbnail candidates allowed, "
                f"got {len(candidates)}"
            )
        return self