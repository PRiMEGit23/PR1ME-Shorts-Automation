"""Learning Engine rules: every constant, threshold, and mapping (Phase 11).

The single source of truth for the learning engine's numbers: pattern
thresholds, confidence formula parameters, leaderboard definitions,
proposal caps, and the dimension -> module mapping used to say which
knowledge module a proposal would touch. No learning logic duplicates a
number that lives here.
"""

from __future__ import annotations

# ------------------------------------------------------------- thresholds --

#: Scenes in a group before the group may win a pattern.
MIN_GROUP_SAMPLES = 3
#: Mean-QA lead required for a QA pattern (winner vs the rest).
MIN_DELTA_QA = 2.0
#: Mean-retention lead required for a retention pattern.
MIN_DELTA_RETENTION = 1.0
#: Mean-attempts lead (fewer is better) required for an attempts pattern.
MIN_DELTA_ATTEMPTS = 0.4
#: Minimum confidence for a pattern to produce a proposal.
MIN_CONFIDENCE = 0.5
#: Scenes a proposal cites as evidence at most.
MAX_EVIDENCE_SCENES = 6
#: QA lead required before a model recommendation is generated.
MIN_MODEL_DELTA_QA = 1.5
#: |observed - predicted| QA gap that triggers a calibration proposal.
MIN_CALIBRATION_DELTA_QA = 2.0
#: Minimum failed scenes before an optimizer recommendation is generated.
MIN_FAILED_FOR_OPTIMIZER = 3
#: Cap on emitted patterns and proposals (sorted, deterministic).
MAX_PATTERNS = 12
MAX_PROPOSALS = 12

#: Calibration adjustments propose half of the observed gap (no overfit).
CALIBRATION_ATTENUATION = 0.5

#: Confidence formula: base + per-sample bonus + delta bonus.
CONFIDENCE_BASE = 0.5
CONFIDENCE_PER_SAMPLE = 0.05
CONFIDENCE_SAMPLE_CAP = 0.25
CONFIDENCE_DELTA_CAP = 0.15
CONFIDENCE_MAX = 0.95
CONFIDENCE_DELTA_SCALE_QA = 40.0
CONFIDENCE_DELTA_SCALE_ATTEMPTS = 8.0
CONFIDENCE_DELTA_SCALE_RETENTION = 20.0

#: The fallback switch constants the optimizer proposals may reference.
SWITCH_AFTER_ATTEMPTS = 2
MIN_IMPROVEMENT = 3.0

#: Runs in the trend-report comparison windows.
TREND_WINDOW = 5

# ------------------------------------------------------------- dimensions --

#: The eight leaderboards: (name, observation dimension).
LEADERBOARD_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("model", "image_model"),
    ("workflow", "render_profile"),
    ("prompt", "negative_tokens"),
    ("qa", "scene_id"),
    ("render", "video_model"),
    ("topic", "topic"),
    ("visual_strategy", "shot_type"),
    ("engineering_visualization", "visualization_type"),
)

#: Pattern dimensions per metric: which groups compete on which metric.
#: qa and retention: higher is better. attempts: lower is better.
PATTERN_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "qa": (
        "shot_type",
        "image_model",
        "lens",
        "light_direction",
        "visualization_type",
        "render_profile",
        "camera_distance",
        "camera_angle",
        "framing",
        "topic",
        "negative_tokens",
    ),
    "retention": ("transition_type",),
    "attempts": ("image_model", "shot_type"),
}

#: The affected knowledge modules per pattern dimension (proposal targets).
AFFECTED_MODULES: dict[str, tuple[str, ...]] = {
    "shot_type": ("knowledge/ai_director/director_rules.py",),
    "image_model": (
        "knowledge/model_director/model_registry.py",
        "knowledge/model_director/model_selector.py",
    ),
    "video_model": (
        "knowledge/model_director/model_registry.py",
        "knowledge/model_director/model_selector.py",
    ),
    "lens": ("knowledge/ai_director/director_rules.py",),
    "light_direction": (
        "knowledge/ai_director/director_rules.py",
        "knowledge/visual_intelligence/lighting_planner.py",
    ),
    "transition_type": ("knowledge/ai_director/transition_planner.py",),
    "visualization_type": (
        "knowledge/ai_director/director_rules.py",
        "knowledge/visual_intelligence/engineering_visuals.py",
    ),
    "render_profile": ("knowledge/render_optimizer/workflow_selector.py",),
    "camera_distance": ("knowledge/ai_director/director_rules.py",),
    "camera_angle": ("knowledge/ai_director/director_rules.py",),
    "framing": ("knowledge/ai_director/director_rules.py",),
    "negative_tokens": ("knowledge/compiler/compilers/sdxl.py",),
    "topic": ("assets/knowledge_base.csv",),
}

#: Deterministic suggestion texts for optimizer proposals.
OPTIMIZER_SUGGESTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "switches_did_not_rescue",
        "raise the deterministic switch bar",
        "increase MIN_IMPROVEMENT: model switches did not rescue QA",
    ),
    (
        "never_switched",
        "extend the fallback chain",
        "extend the fallback chain: repeated failures with no switch available",
    ),
)

#: Why the knowledge base stays immutable (mirrored in the docs).
IMMUTABILITY_STATEMENT = (
    "The Learning Engine never modifies source knowledge; every "
    "improvement is a reviewable proposal with supporting evidence."
)
