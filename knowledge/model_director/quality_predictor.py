"""Quality predictor: the expected QA score per model and scene (Phase 10).

The expected score is a pure function of the model's capability axes and
the scene's genre requirements (which axes the scene leans on), scaled by
the model's reliability. No randomness, no LLM - the same scene and model
always produce the same prediction, and the prediction is what the
fallback strategy uses to decide a model switch.
"""

from __future__ import annotations

from knowledge.ai_director.director_models import SceneDirective
from knowledge.model_director.model_registry import REGISTRY, ModelKind, ModelSpec
from knowledge.visual_intelligence.storyboard import ShotType

#: Shot type -> (axis, weight) the scene leans on, in addition to the
#: universal prompt-adherence axis.
_SHOT_AXES: dict[ShotType, tuple[str, float]] = {
    ShotType.MACRO: ("macro_detail", 0.6),
    ShotType.EXTREME_MACRO: ("macro_detail", 0.6),
    ShotType.MICROSCOPE: ("macro_detail", 0.6),
    ShotType.HERO: ("photoreal", 0.6),
    ShotType.CROSS_SECTION: ("engineering", 0.6),
    ShotType.CUTAWAY: ("engineering", 0.6),
    ShotType.TRANSPARENT: ("engineering", 0.6),
    ShotType.EXPLODED_VIEW: ("engineering", 0.6),
    ShotType.CAD_RENDER: ("engineering", 0.6),
    ShotType.ISOMETRIC: ("engineering", 0.6),
    ShotType.ORTHOGRAPHIC: ("engineering", 0.6),
    ShotType.BLUEPRINT: ("diagram", 0.6),
    ShotType.ANNOTATED_DIAGRAM: ("diagram", 0.6),
    ShotType.WIREFRAME_OVERLAY: ("diagram", 0.6),
    ShotType.MANUFACTURING_SEQUENCE: ("diagram", 0.6),
    ShotType.PROCESS_SEQUENCE: ("diagram", 0.6),
    ShotType.COMPARISON_SPLIT: ("engineering", 0.4),
    ShotType.BEFORE_AFTER: ("engineering", 0.4),
}

_BASE_WEIGHT = 1.0


def _axis_score(spec: ModelSpec, axis: str) -> float:
    return {
        "photoreal": spec.photoreal,
        "diagram": spec.diagram,
        "macro_detail": spec.macro_detail,
        "engineering": spec.engineering,
        "adherence": spec.adherence,
    }[axis]


def expected_qa_score(model_key: str, shot_type: ShotType) -> float:
    """The predicted QA score (0-100) of a model for a scene's shot.

    The scene leans on one genre axis (plus universal adherence); the
    weighted capability average is scaled by the model's reliability.
    """
    spec = REGISTRY.get(model_key)
    weight = _BASE_WEIGHT
    total = _axis_score(spec, "adherence") * _BASE_WEIGHT
    axis, axis_weight = _SHOT_AXES.get(shot_type, ("adherence", 0.0))
    if axis_weight > 0.0:
        total += _axis_score(spec, axis) * axis_weight
        weight += axis_weight
    raw = total / weight
    return round(raw * (0.85 + 0.15 * spec.reliability), 1)


def expected_video_quality(model_key: str) -> float:
    """The predicted motion quality (0-100) of a video model."""
    spec = REGISTRY.get(model_key)
    if spec.kind is not ModelKind.VIDEO:
        raise ValueError(f"{model_key!r} is not a video model")
    return round(
        (spec.motion_quality * 0.8 + spec.adherence * 0.2)
        * (0.85 + 0.15 * spec.reliability),
        1,
    )


def expected_success_probability(expected_qa: float, reliability: float) -> float:
    """Predicted probability of passing QA on the first attempt (0-1)."""
    if expected_qa >= 85.0:
        base = 0.90
    elif expected_qa >= 75.0:
        base = 0.75
    elif expected_qa >= 60.0:
        base = 0.60
    else:
        base = 0.40
    return round(base * (0.9 + 0.1 * reliability), 3)


def expected_retry_count(expected_qa: float, reliability: float) -> int:
    """Predicted attempts needed to pass QA (deterministic tier table)."""
    probability = expected_success_probability(expected_qa, reliability)
    if probability >= 0.85:
        return 1
    if probability >= 0.70:
        return 2
    if probability >= 0.50:
        return 3
    return 4


def scene_axes(directive: SceneDirective) -> tuple[ShotType, str, float]:
    """The shot type and its dominant axis - the predictor's inputs."""
    return directive.shot_type, *_SHOT_AXES.get(directive.shot_type, ("adherence", 0.0))


def axis_for_shot(shot_type: ShotType) -> str:
    """The capability axis a shot leans on (the single shot->axis mapping)."""
    return _SHOT_AXES.get(shot_type, ("adherence", 0.0))[0]
