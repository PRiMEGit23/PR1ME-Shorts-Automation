"""Tests for the Knowledge Base V2 VisualArchitecture schema (knowledge/visual_architecture.py)."""

from __future__ import annotations

import pytest
from knowledge.visual_architecture import (
    Background,
    Camera,
    CameraAngle,
    CameraDistance,
    CameraHeight,
    ColorPalette,
    Composition,
    CompositionRule,
    Contrast,
    Depth,
    DepthOfField,
    EngineeringDomain,
    Framing,
    Lens,
    LightDirection,
    Lighting,
    LightingStyle,
    Material,
    Modality,
    Mood,
    Motion,
    NegativeSpace,
    ScaleReference,
    Scene,
    Subject,
    SubjectHierarchy,
    SurfaceFinish,
    TextPosition,
    TextSlot,
    Thumbnail,
    TransitionHint,
    TransitionType,
    VisualArchitecture,
)
from pydantic import ValidationError

CAMERA = Camera(
    distance=CameraDistance.MEDIUM,
    angle=CameraAngle.SLIGHTLY_LOW,
    lens=Lens.STANDARD_35,
    framing=Framing.SUBJECT_CENTER,
    height=CameraHeight.TABLE,
)
COMPOSITION = Composition(
    rule=CompositionRule.CENTERED,
    emphasis="the main subject",
    negative_space=NegativeSpace.OVERLAY_TOP,
)
LIGHTING = Lighting(
    direction=LightDirection.SIDE,
    style=LightingStyle.RAKING,
    practical_sources=["bench lamp"],
    key_color="neutral",
)
PALETTE = ColorPalette(base="dark slate", accent="natural PLA")


def subject(entity: str = "test part") -> Subject:
    return Subject(
        entity=entity,
        description="cut-open test part",
        materials=[Material.PLA],
        surface_finish=[SurfaceFinish.LAYER_LINES],
        manufacturing_details=["FDM extrusion", "0.4 mm brass nozzle"],
        visible_geometry=["smooth internal cells"],
    )


def scene(n: int, entity: str = "test part", **overrides: object) -> Scene:
    base: dict[str, object] = {
        "scene_id": f"S{n}",
        "modality": Modality.CROSS_SECTION,
        "primary_subject": subject(entity),
        "secondary_subjects": [],
        "subject_hierarchy": SubjectHierarchy(
            primary=entity,
            background="workbench",
            focus_object=entity,
        ),
        "engineering_goal": f"Goal {n}",
        "teaching_goal": f"Teaching {n}",
        "visual_focus": entity,
        "camera": CAMERA,
        "composition": COMPOSITION,
        "depth": Depth(
            foreground=None,
            midground=entity,
            background="workbench",
            dof=DepthOfField.MEDIUM,
        ),
        "lighting": LIGHTING,
        "color_palette": PALETTE,
        "mood": Mood.CLINICAL,
        "motion": Motion(type="static"),
        "transition_hint": TransitionHint(type=TransitionType.CUT),
        "scene_importance": 3,
    }
    base.update(overrides)
    return Scene(**base)


def thumbnail() -> Thumbnail:
    return Thumbnail(
        modality=Modality.PHOTOREAL,
        primary_subject=subject(),
        background=Background(environment="dark workshop blur", depth=DepthOfField.SHALLOW),
        focus_object="test part",
        composition=COMPOSITION,
        text_slot=TextSlot(
            string="TEST TITLE",
            position=TextPosition.UPPER_THIRD,
            max_chars=28,
            contrast=Contrast.HIGH,
        ),
        camera=CAMERA,
        lighting=LIGHTING,
        color_palette=PALETTE,
        mood=Mood.COMPARATIVE,
    )


def architecture(**overrides: object) -> VisualArchitecture:
    base: dict[str, object] = {
        "world_id": "pr1me_lab_v1",
        "engineering_domain": EngineeringDomain.FDM,
        "modality": Modality.PHOTOREAL,
        "scenes": [scene(1), scene(2), scene(3), scene(4)],
        "thumbnail": thumbnail(),
    }
    base.update(overrides)
    return VisualArchitecture(**base)


def test_json_round_trip_preserves_spec() -> None:
    arch = architecture()
    restored = VisualArchitecture.model_validate_json(arch.model_dump_json())
    assert restored == arch
    assert restored.version == "2.0"
    assert restored.derived is False


def test_unknown_enum_value_is_rejected() -> None:
    payload = architecture().model_dump()
    payload["scenes"][0]["modality"] = "hologram"
    with pytest.raises(ValidationError):
        VisualArchitecture(**payload)


def test_unknown_fields_are_rejected() -> None:
    payload = architecture().model_dump()
    payload["scenes"][0]["prompt"] = "sneaky sdxl prompt"
    with pytest.raises(ValidationError):
        VisualArchitecture(**payload)


def test_hierarchy_primary_must_match_subject() -> None:
    with pytest.raises(ValidationError, match="primary"):
        scene(1, entity="part A", subject_hierarchy=SubjectHierarchy(
            primary="part B",
            background="workbench",
            focus_object="part B",
        ))


def test_hierarchy_secondary_must_match_subjects() -> None:
    s = subject("part B")
    with pytest.raises(ValidationError, match="secondary"):
        scene(
            1,
            entity="part A",
            secondary_subjects=[s],
            subject_hierarchy=SubjectHierarchy(
                primary="part A",
                secondary=[],
                background="workbench",
                focus_object="part A",
            ),
        )


def test_focus_object_must_exist_in_hierarchy() -> None:
    with pytest.raises(ValidationError, match="focus_object"):
        scene(1, entity="part A", subject_hierarchy=SubjectHierarchy(
            primary="part A",
            background="workbench",
            focus_object="part C",
        ))


def test_more_than_three_secondary_subjects_rejected() -> None:
    extras = [subject(f"part {i}") for i in range(4)]
    with pytest.raises(ValidationError):
        scene(
            1,
            secondary_subjects=extras,
            subject_hierarchy=SubjectHierarchy(
                primary="test part",
                secondary=[s.entity for s in extras],
                background="workbench",
                focus_object="test part",
            ),
        )


def test_scene_count_bounds() -> None:
    with pytest.raises(ValidationError):
        architecture(scenes=[scene(1), scene(2), scene(3)])
    with pytest.raises(ValidationError):
        architecture(scenes=[scene(i) for i in range(1, 8)])


def test_scene_ids_must_be_consecutive() -> None:
    with pytest.raises(ValidationError, match="consecutive"):
        architecture(scenes=[scene(1), scene(1), scene(2), scene(3)])


def test_at_most_two_thumbnail_candidates() -> None:
    with pytest.raises(ValidationError, match="thumbnail"):
        architecture(
            scenes=[
                scene(1, thumbnail_candidate=True),
                scene(2, thumbnail_candidate=True),
                scene(3, thumbnail_candidate=True),
                scene(4),
            ]
        )


def test_scale_reference_is_optional() -> None:
    arch = architecture()
    assert all(s.scale_reference is None for s in arch.scenes)
    with_reference = scene(1, scale_reference=ScaleReference(entity="US quarter", size="25 mm"))
    assert with_reference.scale_reference is not None


def test_material_enum_covers_channel_needs() -> None:
    names = {m.value for m in Material}
    for expected in ("PLA", "PETG", "nylon", "stainless steel", "aluminium", "carbon fiber"):
        assert expected in names
