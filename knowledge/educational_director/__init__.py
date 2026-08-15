"""Educational Director: the creative brain above the Visual Intelligence engine.

Decides HOW a topic is best TAUGHT - the teaching strategy, visual methods,
cognitive sequence, retention, analogy, comparison, animation needs, and the
likely failure mode - before any storyboard exists. Fully deterministic,
strongly typed, and disconnected from the runtime below it.
"""

from knowledge.educational_director.cognitive_flow import CognitiveFlowBuilder
from knowledge.educational_director.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import (
    EDUCATIONAL_PLAN_VERSION,
    AnimationRequirement,
    CognitiveStep,
    CoreMisconception,
    DifficultyLevel,
    EducationalPlan,
    EngineeringDomainHint,
    FailureMode,
    KnowledgeDirectorResult,
    KnowledgeFlowStep,
    LearningObjective,
    RetentionMethod,
    TeachingStrategy,
    VisualTeachingMethod,
)
from knowledge.educational_director.knowledge_director import KnowledgeDirector, infer_domain
from knowledge.educational_director.learning_objectives import derive_learning_objective
from knowledge.educational_director.strategy_selector import StrategySelector
from knowledge.educational_director.visual_method_selector import VisualMethodSelector

__all__ = [
    "EDUCATIONAL_PLAN_VERSION",
    "AnimationRequirement",
    "CognitiveFlowBuilder",
    "CognitiveStep",
    "CoreMisconception",
    "DifficultyLevel",
    "EducationalDirector",
    "EducationalPlan",
    "EngineeringDomainHint",
    "FailureMode",
    "KnowledgeDirector",
    "KnowledgeDirectorResult",
    "KnowledgeFlowStep",
    "LearningObjective",
    "RetentionMethod",
    "StrategySelector",
    "TeachingStrategy",
    "VisualMethodSelector",
    "VisualTeachingMethod",
    "derive_learning_objective",
    "infer_domain",
]