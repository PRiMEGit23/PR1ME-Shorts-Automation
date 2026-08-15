"""Tests for the Visual Architecture subsystem."""

from __future__ import annotations

import asyncio

import pydantic
import pytest

from pr1me.visual_architecture import (
    VisualArchitecture,
    VisualArchitectureInput,
)
from pr1me.visual_architecture.contracts import (
    ComfyUIReady,
    KnowledgeOutput,
    PromptCompositionOutput,
    PromptValidationOutput,
    ScenePlanOutput,
    ShotPlanOutput,
    VisualIntelligenceOutput,
    VisualizationStrategyOutput,
)


def _payload(**overrides: object) -> VisualArchitectureInput:
    base = dict(
        topic="First-Layer Squish",
        hook="Why does the first layer lift?",
        explanation="Bed leveling and the right z offset let the extruder lay down a squished "
        "layer that grips the build plate, while poor squish leaves gaps.",
        practical_insight="Level the bed and drop the nozzle until the first layer is visibly "
        "squished.",
        ending="A perfect first layer means perfect adhesion and a clean print.",
        word_count=45,
    )
    base.update(overrides)
    return VisualArchitectureInput(**base)


def _run(payload: VisualArchitectureInput) -> VisualIntelligenceOutput:
    return asyncio.run(VisualArchitecture().run(payload))


def test_payload_validation_rejects_missing_fields() -> None:
    with pytest.raises(pydantic.ValidationError):
        VisualArchitectureInput(topic="", hook="", explanation="", word_count=45)


def test_end_to_end_produces_all_outputs() -> None:
    out = _run(_payload())
    assert isinstance(out, VisualIntelligenceOutput)
    assert isinstance(out.knowledge, KnowledgeOutput)
    assert isinstance(out.strategy, VisualizationStrategyOutput)
    assert isinstance(out.scene_plan, ScenePlanOutput)
    assert isinstance(out.shot_plan, ShotPlanOutput)
    assert isinstance(out.composition, PromptCompositionOutput)
    assert isinstance(out.validation, PromptValidationOutput)
    assert len(out.comfyui_ready) == len(out.shot_plan.shots)


def test_scene_plan_uses_four_act_structure() -> None:
    out = _run(_payload())
    expected = ("hook", "explanation", "practical_insight", "ending")
    acts = [scene.narration_block for scene in out.scene_plan.scenes]
    assert acts == list(expected)


def test_shot_plan_has_eight_shots_with_required_fields() -> None:
    out = _run(_payload())
    shots = out.shot_plan.shots
    assert len(shots) == 8
    assert all(shot.narration_block for shot in shots)
    assert all(shot.focus and shot.depth and shot.lens and shot.composition for shot in shots)
    assert [shot.narration_block for shot in shots] == [
        "hook",
        "hook",
        "explanation",
        "explanation",
        "practical_insight",
        "practical_insight",
        "ending",
        "ending",
    ]


def test_knowledge_extractor_discovers_mechanism_and_materials() -> None:
    out = _run(_payload())
    assert out.knowledge.primary_concept() == "bed leveling"
    assert any("build plate" in name.lower() for name in out.knowledge.objects)
    assert out.knowledge.mechanisms
    assert isinstance(out.knowledge.materials, list)


def test_knowledge_extractor_detects_explicit_materials() -> None:
    out = _run(
        _payload(
            explanation="A glass bed with a PLA filament print keeps the first layer flat and "
            "adhered while brass nozzle friction drags the squished line along."
        )
    )
    assert any("glass" in material.lower() for material in out.knowledge.materials)
    assert any("pla" == material.lower() for material in out.knowledge.materials)
    assert any("brass" in material.lower() for material in out.knowledge.materials)


def test_visual_style_has_brand_attributes() -> None:
    out = _run(_payload())
    assert out.visual_style.lighting
    assert out.visual_style.mood
    assert out.visual_style.color_palette
    assert out.visual_style.rendering_style
    assert out.visual_style.realism_level
    roles = {color.role for color in out.visual_style.color_palette}
    assert {"background", "accent"}.issubset(roles)
    for color in out.visual_style.color_palette:
        assert color.hex.startswith("#")


def test_strategy_is_deterministic_for_same_input() -> None:
    first = _run(_payload())
    second = _run(_payload())
    assert first.strategy.style == second.strategy.style
    assert first.strategy.rationale == second.strategy.rationale


def test_consistency_keeps_single_environment_and_subject() -> None:
    out = _run(_payload())
    assert out.consistency.environment
    assert out.consistency.object_registry
    descriptor = out.consistency.object_registry[0].canonical_descriptor
    assert out.composition.prompts[0].fields.subject == descriptor


def test_composed_prompt_has_all_required_components() -> None:
    out = _run(_payload())
    for prompt in out.composition.prompts:
        positive = prompt.positive_prompt
        assert prompt.fields.subject in positive
        assert prompt.fields.environment in positive
        assert prompt.fields.lighting in positive
        assert prompt.fields.rendering_style in positive
        assert prompt.fields.physics in positive
        assert prompt.fields.focus in positive
        assert prompt.fields.depth in positive
        assert prompt.negative_prompt
        assert prompt.is_thumbnail == (prompt.shot_id == 1)


def test_thumbnail_prompt_differs_from_body_shots() -> None:
    out = _run(_payload())
    thumbnail = next(p for p in out.composition.prompts if p.is_thumbnail)
    body = next(p for p in out.composition.prompts if not p.is_thumbnail)
    assert "high contrast" in thumbnail.positive_prompt
    assert thumbnail.positive_prompt != body.positive_prompt


def test_validation_passes_every_shot_above_threshold() -> None:
    out = _run(_payload())
    assert out.validation.status == "ok"
    assert all(prompt.score >= 95 for prompt in out.validation.prompts)
    assert len(out.validation.prompts) == 8
    for prompt in out.validation.prompts:
        assert prompt.criteria
        assert prompt.status in ("passed", "regenerated")


def test_comfyui_ready_packages_variables() -> None:
    out = _run(_payload())
    assert len(out.comfyui_ready) == 8
    assert all(isinstance(item, ComfyUIReady) for item in out.comfyui_ready)
    variables = out.comfyui_ready[0].to_comfyui_variables()
    for key in ("positive_prompt", "negative_prompt", "width", "height", "seed", "steps", "cfg"):
        assert key in variables
    assert variables["width"] == 1080
    assert variables["height"] == 1920
    assert out.comfyui_ready[0].positive_prompt


def test_run_is_deterministic_end_to_end() -> None:
    first = _run(_payload())
    second = _run(_payload())
    assert [p.positive_prompt for p in first.composition.prompts] == [
        p.positive_prompt for p in second.composition.prompts
    ]
    assert [p.negative_prompt for p in first.composition.prompts] == [
        p.negative_prompt for p in second.composition.prompts
    ]
    assert [item.seed for item in first.comfyui_ready] == [
        item.seed for item in second.comfyui_ready
    ]
