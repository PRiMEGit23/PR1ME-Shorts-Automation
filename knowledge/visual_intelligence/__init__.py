"""Visual Intelligence Engine: deterministic, goal-driven shot planning.

Converts a Knowledge Base row plus a VisualArchitecture V2 specification into
a VisualStoryboard: visual goals per scene, shot types, camera / lighting /
composition plans, engineering visualizations, transitions, and a ranked
thumbnail pick. Purely deterministic; never calls a model and never writes
prompts.
"""

from knowledge.visual_intelligence.shot_director import ShotDirector
from knowledge.visual_intelligence.storyboard import (
    STORYBOARD_VERSION,
    CameraPlan,
    CompositionPlan,
    EngineeringVisualization,
    EngineeringVisualizationType,
    LightingPlan,
    SceneIntent,
    ShotType,
    StoryboardScene,
    ThumbnailPriority,
    Transition,
    VisualStoryboard,
)
from knowledge.visual_intelligence.thumbnail_director import (
    pick_thumbnail_scene,
    rank_thumbnail_candidates,
)
from knowledge.visual_intelligence.visual_goal import VisualGoal, classify_visual_goal
from knowledge.visual_intelligence.visual_intelligence import (
    KnowledgeBaseRow,
    VisualIntelligenceEngine,
)

__all__ = [
    "STORYBOARD_VERSION",
    "CameraPlan",
    "CompositionPlan",
    "EngineeringVisualization",
    "EngineeringVisualizationType",
    "KnowledgeBaseRow",
    "LightingPlan",
    "SceneIntent",
    "ShotDirector",
    "ShotType",
    "StoryboardScene",
    "ThumbnailPriority",
    "Transition",
    "VisualGoal",
    "VisualIntelligenceEngine",
    "VisualStoryboard",
    "classify_visual_goal",
    "pick_thumbnail_scene",
    "rank_thumbnail_candidates",
]