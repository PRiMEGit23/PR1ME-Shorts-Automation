"""Educational Plan schema: how a topic is best TAUGHT, before any storyboard.

The Educational Director answers "what is the most effective visual strategy
for teaching this concept in under 30 seconds?" Everything in this module is
pure data: enums are the teaching/visual/cognitive taxonomies, and models are
frozen and reject unknown fields, matching the rest of the knowledge base.

No prompt strings, no render syntax, no scene plans: a downstream subsystem
(Visual Intelligence, Phase 2) will later translate this plan into shots.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

EDUCATIONAL_PLAN_VERSION = "1.0.0"


class TeachingStrategy(StrEnum):
    """Extensible taxonomy of how humans best acquire this concept."""

    COMPARISON = "comparison"
    BEFORE_AFTER = "before/after"
    CAUSE_EFFECT = "cause to effect"
    PROBLEM_SOLUTION = "problem to solution"
    QUESTION_ANSWER = "question to answer"
    LAYER_BY_LAYER_REVEAL = "layer-by-layer reveal"
    HIDDEN_GEOMETRY = "hidden geometry"
    FAILURE_ANALYSIS = "failure analysis"
    MECHANICAL_BREAKDOWN = "mechanical breakdown"
    ANIMATION_FIRST = "animation first"
    DIAGRAM_FIRST = "diagram first"
    SCALE_COMPARISON = "scale comparison"
    PROGRESSIVE_DISCLOSURE = "progressive disclosure"
    MYTH_BUSTING = "myth busting"
    REAL_WORLD_EXAMPLE = "real-world example"
    SIMULATION = "simulation"
    PROCESS_TIMELINE = "process timeline"
    MANUFACTURING_SEQUENCE = "manufacturing sequence"
    FORCE_FLOW = "force flow"
    ENERGY_FLOW = "energy flow"
    MATERIAL_TRANSFORMATION = "material transformation"


class VisualTeachingMethod(StrEnum):
    """The dominant visual genres the director may deploy."""

    DIAGRAM = "diagram"
    ANIMATION = "animation"
    CAD = "CAD"
    EXPLODED_VIEW = "exploded view"
    CROSS_SECTION = "cross section"
    TRANSPARENT_HOUSING = "transparent housing"
    STRESS_VISUALIZATION = "stress visualization"
    THERMAL_VISUALIZATION = "thermal visualization"
    MOTION_VISUALIZATION = "motion visualization"
    ASSEMBLY_SEQUENCE = "assembly sequence"
    SECTION_VIEW = "section view"
    INFOGRAPHIC = "infographic"
    TIMELINE = "timeline"
    MACRO = "macro"
    MICROSCOPE = "microscope"
    XRAY = "X-ray"
    CUTAWAY = "cutaway"
    COMPARISON_BOARD = "comparison board"


class CognitiveStep(StrEnum):
    """One stage of the learning arc inside a 30-second explanation."""

    HOOK = "hook"
    QUESTION = "question"
    PROBLEM = "problem"
    REVEAL = "reveal"
    EXPLANATION = "explanation"
    EVIDENCE = "evidence"
    COMPARISON = "comparison"
    FAILURE = "failure"
    ROOT_CAUSE = "root cause"
    SOLUTION = "solution"
    MYTH = "myth"
    DEFINITION = "definition"
    EXAMPLE = "example"
    DEMONSTRATION = "demonstration"
    CONCLUSION = "conclusion"


class RetentionMethod(StrEnum):
    """How the takeaway is anchored so it survives the 30 seconds."""

    VISUAL_ANCHOR = "visual anchor"
    CONCRETE_REFERENCE = "concrete reference"
    MENTAL_MODEL = "mental model"
    RECAP = "recap"
    CHUNKING = "chunking"
    MNEMONIC = "mnemonic"


class DifficultyLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AnimationRequirement(StrEnum):
    YES = "yes"
    NO = "no"
    PARTIAL = "partial"


class FailureMode(StrEnum):
    """The most likely way a 30-second explanation of THIS topic fails."""

    ABSTRACT_CONCEPT_WITHOUT_ANCHOR = "abstract concept without an anchor"
    NO_STAKES = "no stakes"
    MISCONCEPTION_UNCHALLENGED = "misconception left unchallenged"
    OVERLOAD = "cognitive overload"
    WRONG_SEQUENCE = "wrong sequence"
    TERMS_BEFORE_INTUITION = "terms before intuition"
    MISSING_SCALE = "missing scale"
    COMPARISON_WITHOUT_CONTEXT = "comparison without context"


class EngineeringDomainHint(StrEnum):
    """Coarse domain the Knowledge Director infers for a curated row."""

    FDM_PRINTING = "FDM printing"
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


class LearningObjective(BaseModel):
    """A measurable, viewer-facing outcome of the 30 seconds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=400)
    verbs: list[str] = Field(default_factory=list, max_length=6)
    success_criteria: str = Field(default="", max_length=300)


class CoreMisconception(BaseModel):
    """The belief most likely to be wrong in the viewer's head."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=400)
    why_common: str = Field(default="", max_length=300)
    why_dangerous: str = Field(default="", max_length=300)
    refutation: str = Field(default="", max_length=300)


class KnowledgeDirectorResult(BaseModel):
    """What the Knowledge Director extracted from a curated Knowledge Base row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topic: str
    domain_hint: EngineeringDomainHint
    most_important_concept: str
    common_misconception: str
    difficult_visualization: str
    key_phenomenon: str
    primary_objective: str
    critical_takeaway: str
    required_prior_knowledge: list[str] = Field(default_factory=list, max_length=6)
    category: str = Field(default="", max_length=120)
    subcategory: str = Field(default="", max_length=120)
    viewer_level: str = Field(default="", max_length=60)


class KnowledgeFlowStep(BaseModel):
    """One beat of the taught knowledge: what, why, and how it is shown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: int = Field(ge=1)
    stage: CognitiveStep
    concept: str = Field(min_length=1, max_length=300)
    visual_method: VisualTeachingMethod | None = None
    justification: str = Field(default="", max_length=300)


class EducationalPlan(BaseModel):
    """The complete directorial brief for teaching one topic in under 30 seconds.

    Produced entirely deterministically from a KnowledgeBaseRow. Carries the
    learning objective, misconception, strategy, visual methods, cognitive
    flow, retention, analogy, comparison, animation needs, failure mode, and
    the final takeaway - everything a downstream visual director needs, and
    nothing about rendering.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = EDUCATIONAL_PLAN_VERSION
    topic: str = Field(min_length=1, max_length=200)
    learning_objective: LearningObjective
    core_misconception: CoreMisconception
    teaching_strategy: TeachingStrategy
    strategy_rationale: str = Field(default="", max_length=400)
    visual_teaching_method: list[VisualTeachingMethod] = Field(
        min_length=1, max_length=6
    )
    method_rationale: str = Field(default="", max_length=400)
    cognitive_sequence: list[CognitiveStep] = Field(min_length=3, max_length=10)
    cognitive_flow_rationale: str = Field(default="", max_length=400)
    attention_hook: str = Field(min_length=1, max_length=300)
    knowledge_flow: list[KnowledgeFlowStep] = Field(min_length=3, max_length=10)
    retention_method: RetentionMethod
    retention_rationale: str = Field(default="", max_length=300)
    difficulty_level: DifficultyLevel
    expected_mental_model: str = Field(min_length=1, max_length=400)
    comparison_strategy: str = Field(default="", max_length=400)
    analogy_strategy: str = Field(default="", max_length=400)
    animation_requirement: AnimationRequirement
    animation_rationale: str = Field(default="", max_length=300)
    visualization_priority: list[VisualTeachingMethod] = Field(
        min_length=1, max_length=6
    )
    failure_mode: FailureMode
    failure_mode_rationale: str = Field(default="", max_length=300)
    final_takeaway: str = Field(min_length=1, max_length=400)
    prior_knowledge: list[str] = Field(default_factory=list, max_length=6)