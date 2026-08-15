"""Camera planning: deterministic camera decisions per shot archetype.

The goal already picked the shot archetype; this module turns it into a
CameraPlan whose field names mirror VisualArchitecture.Camera so the existing
SDXL phrase builders apply unchanged. Two goals (scale, motion) override the
shot's default camera because they need specific optics.
"""

from __future__ import annotations

from knowledge.visual_architecture import (
    CameraAngle,
    CameraDistance,
    CameraHeight,
    Framing,
    Lens,
    Scene,
)
from knowledge.visual_intelligence.storyboard import CameraPlan, ShotType
from knowledge.visual_intelligence.visual_goal import VisualGoal

_MACRO_CAMERA = CameraPlan(
    distance=CameraDistance.MACRO,
    angle=CameraAngle.EYE,
    lens=Lens.MACRO_100,
    framing=Framing.TIGHT,
    height=CameraHeight.TABLE,
    note="close inspection geometry, macro optics",
)

_HERO_CAMERA = CameraPlan(
    distance=CameraDistance.WIDE,
    angle=CameraAngle.SLIGHTLY_LOW,
    lens=Lens.STANDARD_35,
    framing=Framing.LOOSE,
    height=CameraHeight.EYE_LEVEL,
    note="hero framing with room for the subject to lead",
)

_CLOSE_CAMERA = CameraPlan(
    distance=CameraDistance.CLOSE,
    angle=CameraAngle.EYE,
    lens=Lens.STANDARD_35,
    framing=Framing.SUBJECT_CENTER,
    height=CameraHeight.TABLE,
    note="tight, centered read of the geometry",
)

_MEDIUM_CAMERA = CameraPlan(
    distance=CameraDistance.MEDIUM,
    angle=CameraAngle.SLIGHTLY_LOW,
    lens=Lens.STANDARD_35,
    framing=Framing.SUBJECT_CENTER,
    height=CameraHeight.TABLE,
    note="three-quarter view keeps volume readable",
)

_FLAT_CAMERA = CameraPlan(
    distance=CameraDistance.MEDIUM,
    angle=CameraAngle.EYE,
    lens=Lens.STANDARD_35,
    framing=Framing.SUBJECT_CENTER,
    height=CameraHeight.EYE_LEVEL,
    note="orthogonal view for blueprint-style reads",
)

_ROW_CAMERA = CameraPlan(
    distance=CameraDistance.MEDIUM,
    angle=CameraAngle.EYE,
    lens=Lens.STANDARD_35,
    framing=Framing.CENTER_ROW,
    height=CameraHeight.TABLE,
    note="options aligned in a single row for comparison",
)

_OVERHEAD_CAMERA = CameraPlan(
    distance=CameraDistance.WIDE,
    angle=CameraAngle.HIGH,
    lens=Lens.WIDE_24,
    framing=Framing.LOOSE,
    height=CameraHeight.OVERHEAD,
    note="overhead wide shows scale and context",
)

_ANGLED_CLOSE_CAMERA = CameraPlan(
    distance=CameraDistance.CLOSE,
    angle=CameraAngle.SLIGHTLY_LOW,
    lens=Lens.STANDARD_35,
    framing=Framing.SUBJECT_CENTER,
    height=CameraHeight.TABLE,
    note="slight dutch-free low angle reads volume on a closed view",
)

_SHOT_CAMERA_TABLE: dict[ShotType, CameraPlan] = {
    ShotType.MACRO: _MACRO_CAMERA,
    ShotType.EXTREME_MACRO: _MACRO_CAMERA,
    ShotType.MICROSCOPE: _MACRO_CAMERA,
    ShotType.HERO: _HERO_CAMERA,
    ShotType.CROSS_SECTION: _CLOSE_CAMERA,
    ShotType.CUTAWAY: _CLOSE_CAMERA,
    ShotType.XRAY: _CLOSE_CAMERA,
    ShotType.WIREFRAME_OVERLAY: _ANGLED_CLOSE_CAMERA,
    ShotType.ANNOTATED_DIAGRAM: _CLOSE_CAMERA,
    ShotType.TRANSPARENT: _MEDIUM_CAMERA,
    ShotType.EXPLODED_VIEW: _MEDIUM_CAMERA,
    ShotType.ISOMETRIC: _MEDIUM_CAMERA,
    ShotType.CAD_RENDER: _MEDIUM_CAMERA,
    ShotType.ORTHOGRAPHIC: _FLAT_CAMERA,
    ShotType.BLUEPRINT: _FLAT_CAMERA,
    ShotType.TIME_LAPSE: _OVERHEAD_CAMERA,
    ShotType.SLOW_MOTION: CameraPlan(
        distance=CameraDistance.CLOSE,
        angle=CameraAngle.EYE,
        lens=Lens.TELE_85,
        framing=Framing.MEDIUM_FRAME,
        height=CameraHeight.TABLE,
        note="telephoto isolates the motion path",
    ),
    ShotType.PROCESS_SEQUENCE: _ROW_CAMERA,
    ShotType.MANUFACTURING_SEQUENCE: _ROW_CAMERA,
    ShotType.BEFORE_AFTER: _ROW_CAMERA,
    ShotType.COMPARISON_SPLIT: _ROW_CAMERA,
}


def plan_camera(goal: VisualGoal, shot: ShotType, scene: Scene) -> CameraPlan:
    """Choose the camera plan for one scene, deterministically."""
    if goal is VisualGoal.EXPLAIN_SCALE:
        return _OVERHEAD_CAMERA
    if goal is VisualGoal.EXPLAIN_MOTION:
        return _SHOT_CAMERA_TABLE[ShotType.SLOW_MOTION]
    return _SHOT_CAMERA_TABLE[shot]