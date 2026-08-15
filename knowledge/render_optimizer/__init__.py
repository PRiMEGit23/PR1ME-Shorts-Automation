"""Render optimizer: turn a QA rejection into a deterministic fix plan.

Stage 5 of the pipeline: Image QA (stage 4) rejects an image; this stage
prescribes exactly what to change - storyboard camera/lighting/composition,
engineering visualization, workflow profile, and prompt phrases - plus a
deterministic projection of the scores after the fixes. Nothing renders
anything; the plan is instructions a future stage or a human executes.
"""

from knowledge.render_optimizer.optimization_engine import (
    MAX_ROUNDS,
    OptimizationEngine,
)
from knowledge.render_optimizer.optimization_models import (
    MAX_GAIN_PER_ROUND,
    MAX_SCORE,
    OPTIMIZER_VERSION,
    CameraChange,
    CompositionChange,
    ExpectedScoreImprovement,
    LightingChange,
    MutationKind,
    OptimizationAction,
    OptimizationActionKind,
    OptimizedRenderPlan,
    PromptMutation,
    VisualizationChange,
    WorkflowChange,
)
from knowledge.render_optimizer.optimization_rules import (
    MIN_TRIGGER_SEVERITY,
    OPTIMIZATION_FLOOR,
    OPTIMIZATION_RULES,
    SCORE_FIELDS,
    ActionTemplate,
    OptimizationRule,
    rule_for,
)
from knowledge.render_optimizer.optimizer import SCORE_WEIGHTS, RenderOptimizer
from knowledge.render_optimizer.prompt_mutator import (
    apply,
    build_prompt,
    camera_mutations,
    composition_mutations,
    lighting_mutations,
    negative_mutations,
    visualization_mutations,
)
from knowledge.render_optimizer.render_profiles import (
    RENDER_PROFILES,
    RenderProfile,
    RenderProfileKey,
    profile_for,
)
from knowledge.render_optimizer.workflow_selector import (
    SHOT_PROFILES,
    VISUALIZATION_PROFILES,
    select_workflow_profile,
)

__all__ = [
    "MAX_GAIN_PER_ROUND",
    "MAX_ROUNDS",
    "MAX_SCORE",
    "MIN_TRIGGER_SEVERITY",
    "OPTIMIZATION_FLOOR",
    "OPTIMIZATION_RULES",
    "OPTIMIZER_VERSION",
    "RENDER_PROFILES",
    "SCORE_FIELDS",
    "SCORE_WEIGHTS",
    "SHOT_PROFILES",
    "VISUALIZATION_PROFILES",
    "ActionTemplate",
    "CameraChange",
    "CompositionChange",
    "ExpectedScoreImprovement",
    "LightingChange",
    "MutationKind",
    "OptimizationAction",
    "OptimizationActionKind",
    "OptimizationEngine",
    "OptimizationRule",
    "OptimizedRenderPlan",
    "PromptMutation",
    "RenderOptimizer",
    "RenderProfile",
    "RenderProfileKey",
    "VisualizationChange",
    "WorkflowChange",
    "apply",
    "build_prompt",
    "camera_mutations",
    "composition_mutations",
    "lighting_mutations",
    "negative_mutations",
    "profile_for",
    "rule_for",
    "select_workflow_profile",
    "visualization_mutations",
]