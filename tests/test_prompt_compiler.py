"""Tests for the Prompt Compiler (knowledge/compiler): SDXL compilation,
profile registry, determinism, negatives, and the gyroid conversion example."""

from __future__ import annotations

import pytest
from knowledge.compiler import (
    PROFILES,
    CompiledRow,
    CompileError,
    compile_for_model,
)
from knowledge.compiler.examples.gyroid_v2 import (
    LEGACY_PROMPTS,
    LEGACY_THUMBNAIL,
    TOPIC,
    build_gyroid_architecture,
)
from knowledge.compiler.prompt_compiler import COMPILER_VERSION
from knowledge.visual_architecture import Modality

from test_knowledge_visual_architecture import architecture


def test_sdxl_compilation_is_deterministic() -> None:
    arch = architecture()
    first = compile_for_model(arch, "sdxl", topic="Test Topic")
    second = compile_for_model(arch, "sdxl", topic="Test Topic")
    assert first == second
    assert first.scenes["S1"].prompt == second.scenes["S1"].prompt


def test_compile_row_shape() -> None:
    row = compile_for_model(architecture(), "sdxl", topic="Test Topic")
    assert isinstance(row, CompiledRow)
    assert row.model == "sdxl"
    assert row.compiler_version == COMPILER_VERSION
    assert set(row.scenes) == {"S1", "S2", "S3", "S4"}
    assert row.thumbnail.prompt


@pytest.mark.parametrize(
    ("modality", "expected_prefix"),
    [
        (Modality.PHOTOREAL, "photograph of"),
        (Modality.MACRO_INSPECTION, "macro photograph of"),
        (Modality.DIAGRAM, "technical diagram of"),
        (Modality.CROSS_SECTION, "cross-section cutaway of"),
        (Modality.SCHEMATIC, "schematic illustration of"),
        (Modality.EXPLODED_VIEW, "exploded view diagram of"),
        (Modality.SPLIT_COMPARE, "split-screen comparison of"),
    ],
)
def test_modality_prefix_selection(modality: Modality, expected_prefix: str) -> None:
    arch = architecture()
    scenes = [s.model_copy(update={"modality": modality}) for s in arch.scenes]
    arch = arch.model_copy(update={"scenes": scenes})
    prompt = compile_for_model(arch, "sdxl", topic="Test Topic").scenes["S1"].prompt
    assert prompt.startswith(expected_prefix)


def test_subject_engineering_detail_survives_compilation() -> None:
    row = compile_for_model(architecture(), "sdxl", topic="Test Topic")
    prompt = row.scenes["S1"].prompt
    assert "cut-open test part" in prompt
    assert "made of PLA" in prompt
    assert "surface: layer lines" in prompt
    assert "manufactured by: FDM extrusion, 0.4 mm brass nozzle" in prompt
    assert "visible geometry: smooth internal cells" in prompt


def test_negative_merges_excludes_and_profile_tokens_deduped() -> None:
    arch = architecture()
    scene_with_excludes = arch.scenes[0].model_copy(
        update={"objects_to_avoid": ["people", "HANDS", "fused infill"]}
    )
    arch = arch.model_copy(
        update={"scenes": [scene_with_excludes, *arch.scenes[1:]]}
    )
    negative = compile_for_model(arch, "sdxl", topic="Test Topic").scenes["S1"].negative_prompt
    assert negative is not None
    tokens = [t.strip() for t in negative.split(",")]
    assert tokens.count("people") == 1
    assert sum(1 for t in tokens if t.lower() == "hands") == 1
    assert "fused infill" in tokens
    assert "blurry" in tokens


def test_diagram_modality_adds_diagram_negatives() -> None:
    arch = architecture()
    scenes = [s.model_copy(update={"modality": Modality.DIAGRAM}) for s in arch.scenes]
    arch = arch.model_copy(update={"scenes": scenes})
    negative = compile_for_model(arch, "sdxl", topic="Test Topic").scenes["S1"].negative_prompt
    assert negative is not None
    assert "photographic shadows" in negative
    assert "3d render" in negative
    assert "depth of field" in negative


def test_metadata_is_traceable() -> None:
    row = compile_for_model(architecture(), "sdxl", topic="Test Topic")
    meta = row.scenes["S2"].metadata
    assert meta["model"] == "sdxl"
    assert meta["topic"] == "Test Topic"
    assert meta["scene_id"] == "S2"
    assert meta["scene_index"] == 2
    assert meta["size"] == [1080, 1920]
    assert meta["guidance"] == 7.0
    assert meta["source"] == {"field": "visual_architecture_json", "schema_version": "2.0"}
    assert row.thumbnail.metadata["target"] == "thumbnail"


def test_thumbnail_compiles_without_text_slot_in_prompt() -> None:
    row = compile_for_model(architecture(), "sdxl", topic="Test Topic")
    thumb = row.thumbnail
    assert "TEST TITLE" not in thumb.prompt
    assert "high contrast" in thumb.prompt
    assert "bold readable composition" in thumb.prompt
    assert thumb.negative_prompt is not None
    assert "text" in thumb.negative_prompt


def test_unknown_model_key_raises_key_error() -> None:
    with pytest.raises(KeyError):
        compile_for_model(architecture(), "not_a_model", topic="Test Topic")


def test_registered_profiles_without_compilers_fail_closed() -> None:
    for key in ("flux", "gpt_image", "qwen_image"):
        assert key in PROFILES
        with pytest.raises(CompileError, match="no compiler"):
            compile_for_model(architecture(), key, topic="Test Topic")


def test_word_cap_fails_closed() -> None:
    arch = architecture()
    long_entity = " ".join(f"word{i}" for i in range(160))
    verbose = arch.scenes[0].model_copy(
        update={"primary_subject": arch.scenes[0].primary_subject.model_copy(
            update={"description": long_entity}
        )}
    )
    arch = arch.model_copy(update={"scenes": [verbose, *arch.scenes[1:]]})
    with pytest.raises(CompileError, match="exceeds cap"):
        compile_for_model(arch, "sdxl", topic="Test Topic")


def test_gyroid_generated_prompt_differs_from_legacy() -> None:
    arch = build_gyroid_architecture()
    row = compile_for_model(arch, "sdxl", topic=TOPIC)
    generated = row.scenes["S1"].prompt
    legacy = LEGACY_PROMPTS["S1"]
    assert generated != legacy
    assert legacy not in generated
    assert generated != row.scenes["S4"].prompt


def test_gyroid_generated_prompt_carries_engineering_spec() -> None:
    row = compile_for_model(build_gyroid_architecture(), "sdxl", topic=TOPIC)
    prompt = row.scenes["S1"].prompt
    assert "continuous gyroid lattice with smooth interconnected internal cells" in prompt
    assert "made of PLA" in prompt
    assert "FDM extrusion" in prompt
    assert "scale reference: US quarter coin (25 mm)" in prompt


def test_gyroid_generated_prompt_drops_v1_boilerplate() -> None:
    row = compile_for_model(build_gyroid_architecture(), "sdxl", topic=TOPIC)
    prompt = row.scenes["S1"].prompt
    for boilerplate in (
        "clean technical render, modern engineering lab, precise machined surfaces",
        "Centered subject, rule of thirds for screen elements, generous negative space for overlays",
        "photograph of a diagram",
    ):
        assert boilerplate not in prompt
    clauses = [c.strip() for c in prompt.split(",")]
    assert len(clauses) == len(set(c.lower() for c in clauses))


def test_gyroid_diagram_scenes_use_diagram_modality() -> None:
    row = compile_for_model(build_gyroid_architecture(), "sdxl", topic=TOPIC)
    assert row.scenes["S2"].prompt.startswith("technical diagram of")
    assert row.scenes["S1"].prompt.startswith("cross-section cutaway of")
    assert row.scenes["S5"].prompt.startswith("photograph of")
    assert row.thumbnail.prompt != LEGACY_THUMBNAIL