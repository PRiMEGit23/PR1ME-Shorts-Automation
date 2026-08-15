"""AI Director (Phase 8): the deterministic creative decision engine.

Sits between the Educational Director and Visual Intelligence. Consumes an
EducationalPlan and emits a DirectorOutput: the complete creative brief
(arc, per-scene budgets and cinematic plans, hero / thumbnail / recap,
reveal / pacing / emotion profiles, predicted attention and retention)
that every downstream module consumes instead of using fixed heuristics.

The director is not an LLM: every decision is a pure deterministic
function of the plan. Knowledge stays declarative; the runtime API does
not change.
"""

from __future__ import annotations

from knowledge.ai_director.attention_model import AttentionModel
from knowledge.ai_director.comparison_strategy import ComparisonStrategy
from knowledge.ai_director.director_engine import AIDirector
from knowledge.ai_director.director_models import (
    AI_DIRECTOR_VERSION,
    DirectorOutput,
    SceneDirective,
)
from knowledge.ai_director.director_rules import (
    COMPARISON_STRATEGIES,
    DIAGRAM_PREFERRED_STRATEGIES,
    EMOTION_BY_STAGE,
    MACRO_REQUIRED_STRATEGIES,
    REVEAL_STRATEGIES,
    SHOT_FOR_METHOD,
    SPLIT_STRATEGIES,
    attention_raw,
    camera_for,
    clamp,
    composition_for,
    decide_scene_count,
    lighting_for,
    mood_for,
    motion_for,
    retention_score,
    shot_for_method,
    thumbnail_score,
    transition_between,
    visualization_for,
)
from knowledge.ai_director.emotion_curve import EmotionCurve
from knowledge.ai_director.hero_scene_selector import HeroSceneSelector
from knowledge.ai_director.pacing_planner import PacingPlanner
from knowledge.ai_director.reveal_planner import RevealPlanner
from knowledge.ai_director.scene_prioritizer import ScenePrioritizer
from knowledge.ai_director.thumbnail_strategy import ThumbnailStrategy
from knowledge.ai_director.transition_planner import TransitionPlanner
from knowledge.ai_director.visual_budget import VisualBudgetAllocator

__all__ = [
    "AI_DIRECTOR_VERSION",
    "AIDirector",
    "AttentionModel",
    "COMPARISON_STRATEGIES",
    "ComparisonStrategy",
    "DIAGRAM_PREFERRED_STRATEGIES",
    "DirectorOutput",
    "EMOTION_BY_STAGE",
    "EmotionCurve",
    "HeroSceneSelector",
    "MACRO_REQUIRED_STRATEGIES",
    "PacingPlanner",
    "REVEAL_STRATEGIES",
    "RevealPlanner",
    "SPLIT_STRATEGIES",
    "SceneDirective",
    "ScenePrioritizer",
    "SHOT_FOR_METHOD",
    "ThumbnailStrategy",
    "TransitionPlanner",
    "VisualBudgetAllocator",
    "attention_raw",
    "camera_for",
    "clamp",
    "composition_for",
    "decide_scene_count",
    "lighting_for",
    "mood_for",
    "motion_for",
    "retention_score",
    "shot_for_method",
    "thumbnail_score",
    "transition_between",
    "visualization_for",
]
