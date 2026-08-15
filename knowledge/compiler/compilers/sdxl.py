"""SDXL compiler: turns a VisualArchitecture scene into an SDXL comma-list prompt.

Pure, deterministic phrase assembly. The compiler never invents manufacturing
terms: every engineering detail in the output comes verbatim from the
specification's Subject fields. Rendering quality and aspect phrasing come
from the SDXL ModelProfile, never from the knowledge base.
"""

from __future__ import annotations

from knowledge.compiler.model_profiles import SDXL
from knowledge.compiler.prompt_compiler import CompiledPrompt, PromptCompiler, register_compiler
from knowledge.visual_architecture import (
    Modality,
    Scene,
    Subject,
    Thumbnail,
    VisualArchitecture,
)
from knowledge.visual_intelligence.shot_selector import (
    DIAGRAM_LIKE_SHOTS,
    SHOT_PREFIXES,
)
from knowledge.visual_intelligence.storyboard import (
    STORYBOARD_VERSION,
    StoryboardScene,
    VisualStoryboard,
)

_DIAGRAM_LIKE = {Modality.DIAGRAM, Modality.SCHEMATIC, Modality.EXPLODED_VIEW, Modality.CROSS_SECTION}

_DIAGRAM_NEGATIVES = (
    "photographic shadows",
    "3d render",
    "perspective distortion",
    "depth of field",
)

_MODALITY_PREFIXES: dict[Modality, str] = {
    Modality.PHOTOREAL: "photograph of",
    Modality.MACRO_INSPECTION: "macro photograph of",
    Modality.DIAGRAM: "technical diagram of",
    Modality.CROSS_SECTION: "cross-section cutaway of",
    Modality.SCHEMATIC: "schematic illustration of",
    Modality.EXPLODED_VIEW: "exploded view diagram of",
    Modality.SPLIT_COMPARE: "split-screen comparison of",
}


def _subject_phrase(subject: Subject) -> str:
    parts = [subject.entity]
    if subject.description:
        parts.append(subject.description)
    if subject.state:
        parts.append(subject.state)
    if subject.materials:
        parts.append("made of " + ", ".join(m.value for m in subject.materials))
    if subject.surface_finish:
        parts.append("surface: " + ", ".join(f.value for f in subject.surface_finish))
    if subject.visible_geometry:
        parts.append("visible geometry: " + ", ".join(subject.visible_geometry))
    if subject.manufacturing_details:
        parts.append("manufactured by: " + ", ".join(subject.manufacturing_details))
    return ", ".join(parts)


def _camera_phrase(spec: Scene | Thumbnail) -> str:
    camera = spec.camera
    return (
        f"{camera.distance.value} shot, {camera.angle.value} angle, "
        f"{camera.lens.value} lens, {camera.framing.value} framing"
    )


def _lighting_phrase(spec: Scene | Thumbnail) -> str:
    lighting = spec.lighting
    parts = [f"{lighting.direction.value} lighting, {lighting.style.value} style"]
    if lighting.practical_sources:
        parts.append("practical light from " + ", ".join(lighting.practical_sources))
    if lighting.key_color:
        parts.append(f"{lighting.key_color} key color")
    return ", ".join(parts)


def _composition_phrase(spec: Scene | Thumbnail) -> str:
    composition = spec.composition
    parts = [f"{composition.rule.value} composition", composition.emphasis]
    if composition.negative_space != "none":
        parts.append(f"negative space at {composition.negative_space.value}")
    return ", ".join(parts)


def _dedupe(tokens: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        key = token.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(token.strip())
    return result


def _negative_prompt(scene: Scene) -> str:
    tokens = list(scene.objects_to_avoid) + list(scene.negative_elements)
    if scene.modality in _DIAGRAM_LIKE:
        tokens.extend(_DIAGRAM_NEGATIVES)
    tokens.extend(SDXL.negative_tokens)
    return ", ".join(_dedupe(tokens))


def _storyboard_negative_prompt(scene: StoryboardScene) -> str:
    tokens = list(scene.objects_to_avoid) + list(scene.negative_elements)
    if scene.intent.shot_type in DIAGRAM_LIKE_SHOTS:
        tokens.extend(_DIAGRAM_NEGATIVES)
    tokens.extend(SDXL.negative_tokens)
    return ", ".join(_dedupe(tokens))


def _storyboard_scene_parts(scene: StoryboardScene) -> list[str]:
    prefix = SHOT_PREFIXES[scene.intent.shot_type]
    parts = [f"{prefix} {_subject_phrase(scene.primary_subject)}"]
    if scene.secondary_subjects:
        parts.append("with " + ", ".join(_subject_phrase(s) for s in scene.secondary_subjects))
    parts.append(f"background: {scene.environment or scene.depth.background}")
    parts.append(_camera_phrase(scene))
    parts.append(_lighting_phrase(scene))
    parts.append(_composition_phrase(scene))
    parts.append(f"{scene.depth.dof.value} depth of field")
    parts.append(f"mood: {scene.mood.value}")
    if scene.scale_reference:
        reference = scene.scale_reference
        parts.append(f"scale reference: {reference.entity} ({reference.size})")
    if scene.intent.engineering_visualizations:
        tokens = [
            token
            for viz in scene.intent.engineering_visualizations
            for token in viz.prompt_tokens
        ]
        parts.append("engineering visualization: " + ", ".join(tokens))
    return parts


class SDXLCompiler(PromptCompiler):
    """Deterministic SDXL comma-list prompt builder."""

    profile = SDXL

    def compile_scene(
        self,
        architecture: VisualArchitecture,
        scene: Scene,
        *,
        topic: str,
        scene_index: int,
    ) -> CompiledPrompt:
        prefix = _MODALITY_PREFIXES[scene.modality]
        parts = [f"{prefix} {_subject_phrase(scene.primary_subject)}"]
        if scene.secondary_subjects:
            parts.append("with " + ", ".join(_subject_phrase(s) for s in scene.secondary_subjects))
        environment = scene.environment or scene.depth.background
        parts.append(f"background: {environment}")
        parts.append(_camera_phrase(scene))
        parts.append(_lighting_phrase(scene))
        parts.append(_composition_phrase(scene))
        parts.append(f"{scene.depth.dof.value} depth of field")
        parts.append(f"mood: {scene.mood.value}")
        if scene.scale_reference:
            reference = scene.scale_reference
            parts.append(f"scale reference: {reference.entity} ({reference.size})")
        parts.append(", ".join(SDXL.quality_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)
        self.check_word_cap(prompt, scene.scene_id)
        metadata = self.metadata(
            topic=topic,
            target="scene",
            scene_id=scene.scene_id,
            schema_version=architecture.version,
        )
        metadata["scene_index"] = scene_index
        return CompiledPrompt(
            prompt=prompt,
            negative_prompt=_negative_prompt(scene),
            metadata=metadata,
        )

    def compile_thumbnail(
        self,
        architecture: VisualArchitecture,
        thumbnail: Thumbnail,
        *,
        topic: str,
    ) -> CompiledPrompt:
        prefix = _MODALITY_PREFIXES[thumbnail.modality]
        parts = [f"{prefix} {_subject_phrase(thumbnail.primary_subject)}"]
        if thumbnail.secondary_subjects:
            parts.append("with " + ", ".join(_subject_phrase(s) for s in thumbnail.secondary_subjects))
        parts.append(f"background: {thumbnail.background.environment}")
        parts.append(_camera_phrase(thumbnail))
        parts.append(_lighting_phrase(thumbnail))
        parts.append(_composition_phrase(thumbnail))
        parts.append(f"mood: {thumbnail.mood.value}")
        parts.append(", ".join(SDXL.thumbnail_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)
        self.check_word_cap(prompt, "thumbnail")
        negative = _dedupe(
            list(thumbnail.exclude)
            + ["text", "letters", "words", "captions"]
            + list(SDXL.negative_tokens)
        )
        return CompiledPrompt(
            prompt=prompt,
            negative_prompt=", ".join(negative),
            metadata=self.metadata(
                topic=topic,
                target="thumbnail",
                is_thumbnail=True,
                schema_version=architecture.version,
            ),
        )

    def compile_storyboard_scene(
        self,
        storyboard: VisualStoryboard,
        scene: StoryboardScene,
        *,
        topic: str,
        scene_index: int,
    ) -> CompiledPrompt:
        parts = _storyboard_scene_parts(scene)
        parts.append(", ".join(SDXL.quality_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)
        self.check_word_cap(prompt, scene.scene_id)
        metadata = self.metadata(
            topic=topic,
            target="storyboard_scene",
            scene_id=scene.scene_id,
            schema_version=STORYBOARD_VERSION,
        )
        metadata["source"] = {"field": "visual_storyboard_json", "schema_version": STORYBOARD_VERSION}
        metadata["scene_index"] = scene_index
        metadata["visual_goal"] = scene.intent.goal.value
        metadata["shot_type"] = scene.intent.shot_type.value
        return CompiledPrompt(
            prompt=prompt,
            negative_prompt=_storyboard_negative_prompt(scene),
            metadata=metadata,
        )

    def compile_storyboard_thumbnail(
        self,
        storyboard: VisualStoryboard,
        *,
        topic: str,
    ) -> CompiledPrompt:
        winner = next(
            scene for scene in storyboard.scenes if scene.thumbnail_priority.rank == 1
        )
        parts = _storyboard_scene_parts(winner)
        parts.append(", ".join(SDXL.thumbnail_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)
        self.check_word_cap(prompt, "thumbnail")
        tokens = (
            list(winner.objects_to_avoid)
            + list(winner.negative_elements)
            + (list(_DIAGRAM_NEGATIVES) if winner.intent.shot_type in DIAGRAM_LIKE_SHOTS else [])
            + ["text", "letters", "words", "captions"]
            + list(SDXL.negative_tokens)
        )
        metadata = self.metadata(
            topic=topic,
            target="storyboard_thumbnail",
            scene_id=winner.scene_id,
            schema_version=STORYBOARD_VERSION,
        )
        metadata["source"] = {"field": "visual_storyboard_json", "schema_version": STORYBOARD_VERSION}
        metadata["thumbnail_score"] = winner.thumbnail_priority.score
        metadata["visual_goal"] = winner.intent.goal.value
        metadata["shot_type"] = winner.intent.shot_type.value
        return CompiledPrompt(
            prompt=prompt,
            negative_prompt=", ".join(_dedupe(tokens)),
            metadata=metadata,
        )


register_compiler(SDXLCompiler())