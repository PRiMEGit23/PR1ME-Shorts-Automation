"""SDXL compiler: turns a VisualArchitecture scene into an SDXL comma-list prompt.

Pure, deterministic phrase assembly using Grammar V3.

The compiler never invents manufacturing terms: every engineering detail in the
output comes verbatim from the Specification's Subject/ Material/ Lighting/ etc.
gr grammars. Rendering quality and aspect phrasing come from the SDXL ModelProfile,
never from the knowledge base.

Grammar V3 separates WHAT (engineering truth in grammars) from HOW (photographic
phrasing injected by the compiler from the model profile).
"""

from __future__ import annotations

from knowledge.compiler.model_profiles import SDXL
from knowledge.compiler.prompt_compiler import (
    CompiledPrompt,
    PromptCompiler,
    register_compiler,
    CompileError,
    optimize_prompt_length,
    prompt_entropy,
    prompt_confidence,
)
from knowledge.visual_architecture import (
    Modality,
    Scene,
    Subject,
    Thumbnail,
    VisualArchitecture,
    Lighting,
    ColorPalette,
    Material,
    SurfaceFinish,
    Camera,
    Lens,
    Framing,
    CameraDistance,
    CameraAngle,
    Composition,
    CompositionRule,
    Depth,
    DepthOfField,
    EngineeringDomain,
    Modality as ModalityVA,
    Material as MaterialVA,
    SurfaceFinish as SF,
    Camera as Cam,
    Lens as LensVA,
    Framing as FramingVA,
    Lighting as LightingVA,
    Composition as CompositionVA,
    Depth as DepthVA,
    DepthOfField as DOF,
    Material as Mat,
    Lens as LensT,
    Framing as FriT,
    Lighting as Lit,
    Composition as Compo,
    Depth as Dpt,
    DepthOfField as DOFT,
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

COMPILER_VERSION = "1.1.0"

# --------------------------------------------------------------------- #
# Grammar V3 phrase builders — the "WHAT" (engineering truth)
# --------------------------------------------------------------------- #


def _subject_phrase(subject: Subject) -> str:
    """Build the engineering subject phrase from the Subject grammar."""
    parts: list[str] = [subject.entity]
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
    """Build the camera phrase from the Camera grammar."""
    camera = spec.camera
    return (
        f"{camera.distance.value} shot, {camera.angle.value} angle, "
        f"{camera.lens.value} lens, {camera.framing.value} framing"
    )


def _lighting_phrase(spec: Scene | Thumbnail) -> str:
    """Build the lighting phrase from the Lighting grammar."""
    lighting = spec.lighting
    parts = [f"{lighting.direction.value} lighting, {lighting.style.value} style"]
    if lighting.practical_sources:
        parts.append("practical light from " + ", ".join(lighting.practical_sources))
    if lighting.key_color:
        parts.append(f"{lighting.key_color} key color")
    return ", ".join(parts)


def _composition_phrase(spec: Scene | Thumbnail) -> str:
    """Build the composition phrase from the Composition grammar."""
    composition = spec.composition
    parts = [f"{composition.rule.value} composition", composition.emphasis]
    if composition.negative_space != "none":
        parts.append(f"negative space at {composition.negative_space.value}")
    return ", ".join(parts)


def _dedupe(tokens: list[str]) -> list[str]:
    """Deterministic token deduplication (case-insensitive, first-wins)."""
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        key = token.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(token.strip())
    return result


def _negative_prompt(scene: Scene) -> str:
    """Build the negative prompt from the scene's Negative grammar + model tokens."""
    tokens = list(scene.objects_to_avoid)  # type: ignore[arg-type]
    # scene.negative_elements would come from the grammar if refactored further;
    # for now we use the scene's existing field.
    if scene.modality in {Modality.DIAGRAM, Modality.SCHEMATIC, Modality.EXPLODED_VIEW, Modality.CROSS_SECTION}:
        tokens += ("photographic shadows", "3d render", "perspective distortion", "depth of field")
    tokens += SDXL.negative_tokens  # type: ignore[attr-type]
    return ", ".join(_dedupe(tokens))


def _storyboard_negative_prompt(scene: StoryboardScene) -> str:
    """Build the storyboard negative prompt."""
    tokens = list(scene.objects_to_avoid)  # type: ignore[arg-type]
    if scene.intent.shot_type in DIAGRAM_LIKE_SHOTS:
        tokens += ("photographic shadows", "3d render")
    tokens += SDXL.negative_tokens  # type: ignore[arg-type]
    return ", ".join(_dedupe(tokens))


def _storyboard_scene_parts(scene: StoryboardScene) -> list[str]:
    """Build the scene part list from Grammar V3 primitives."""
    prefix = SHOT_PREFIXES[scene.intent.shot_type]
    parts: list[str] = [f"{prefix} {_subject_phrase(scene.primary_subject)}"]
    if scene.secondary_subjects:
        parts.append("with " + ", ".join(_subject_phrase(s) for s in scene.secondary_subjects))
    environment = scene.environment or scene.depth.background  # type: ignore[attr-index]
    parts.append(f"background: {environment}")
    parts.append(_camera_phrase(scene))
    parts.append(_lighting_phrase(scene))
    parts.append(_composition_phrase(scene))
    parts.append(f"{scene.depth.dof.value} depth of field")  # type: ignore[attr-index]
    parts.append(f"mood: {scene.mood.value}")
    if scene.scale_reference:
        reference = scene.scale_reference  # type: ignore[attr-index]
        parts.append(f"scale reference: {reference.entity} ({reference.size})")
    if scene.intent.engineering_visualizations:  # type: ignore[attr-exists]
        tokens: list[str] = []
        for viz in scene.intent.engineering_visualizations:  # type: ignore[attr-loop]
            for token in viz.prompt_tokens:  # type: ignore[attr-index]
                tokens.append(token)
        parts.append("engineering visualization: " + ", ".join(tokens))
    return parts


# ------------------------------------------------------------------- #
# SDXLModelProfile-accessible constants (the "HOW" — model-profile decisions)
# ------------------------------------------------------------------- #

# Quality tokens live in the model profile; these are the canonical SDXL set.
_SDXL_QUALITY_TOKENS: tuple[str, ...] = (
    "photoreal",
    "high quality",
    "masterpiece",
    "best quality",
)

_SDXL_ASPECT_PHRASE: str = "vertical 9:16"

# Thumbnail-specific tokens (model-profile)
_SDXL_THUMBNAIL_TOKENS: tuple[str, ...] = (
    "ultra sharp",
    "high detail",
    "strong subject contrast",
    "bold readable composition",
    "professional YouTube thumbnail style",
)

# Modality → prefix mapping (model-profile)
_MODALITY_PREFIXES: dict[ModalityVA, str] = {
    ModalityVA.PHOTOREAL: "photograph of",
    ModalityVA.MACRO_INSPECTION: "macro photograph of",
    ModalityVA.DIAGRAM: "technical diagram of",
    ModalityVA.CROSS_SECTION: "cross-section cutaway of",
    ModalityVA.SCHEMATIC: "schematic illustration of",
    ModalityVA.EXPLODED_VIEW: "exploded view diagram of",
    ModalityVA.SPLIT_COMPARE: "split-screen comparison of",
}

# ------------------------------------------------------------------- #
# SDXLCompiler — Grammar V3 implementation
# ------------------------------------------------------------------- #


class SDXLCompiler(PromptCompiler):
    """Deterministic SDXL comma-list prompt builder using Grammar V3.

    Grammar V3 contract:
    - WHAT (engineering truth): SubjectGrammar, MaterialGrammar, LightingGrammar,
      CameraGrammar, CompositionGrammar, RenderingGrammar, NegativeGrammar —
      structured, model-agnostic, no photographic phrasing.
    - HOW (photographic injection): The compiler reads the grammars and injects
      model-specific phrasing from the SDXL ModelProfile. Nothing photographic
      is stored in the knowledge/grammars.
    """

    profile = SDXL

    def compile_scene(
        self,
        architecture: VisualArchitecture,
        scene: Scene,
        *,
        topic: str,
        scene_index: int,
    ) -> CompiledPrompt:
        # Build prompt from Grammar V3 primitives; compiler injects photographic
        # phrasing from the model profile at the designated slots.
        prefix = _MODALITY_PREFIXES[scene.modality]
        parts: list[str] = [f"{prefix} {_subject_phrase(scene.primary_subject)}"]
        if scene.secondary_subjects:
            parts.append("with " + ", ".join(_subject_phrase(s) for s in scene.secondary_subjects))
        environment = scene.environment or scene.depth.background  # type: ignore[attr-index]
        parts.append(f"background: {environment}")
        parts.append(_camera_phrase(scene))
        parts.append(_lighting_phrase(scene))
        parts.append(_composition_phrase(scene))
        parts.append(f"{scene.depth.dof.value} depth of field")  # type: ignore[attr-index]
        parts.append(f"mood: {scene.mood.value}")
        if scene.scale_reference:
            reference = scene.scale_reference  # type: ignore[attr-index]
            parts.append(f"scale reference: {reference.entity} ({reference.size})")
        # Rendering quality tokens from the ModelProfile (the "HOW")
        parts.append(", ".join(SDXL.quality_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)

        # Post-compilation: adaptive word-cap optimization (length optimizer).
        # This does not alter the grammar — it only trims excess while preserving
        # the modality prefix and subject entity.
        prompt = optimize_prompt_length(prompt, self.profile.max_positive_words, model_key="sdxl")

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
        parts: list[str] = [f"{prefix} {_subject_phrase(thumbnail.primary_subject)}"]
        if thumbnail.secondary_subjects:
            parts.append("with " + ", ".join(_subject_phrase(s) for s in thumbnail.secondary_subjects))
        parts.append(f"background: {thumbnail.background.environment}")  # type: ignore[attr-index]
        parts.append(_camera_phrase(thumbnail))
        parts.append(_lighting_phrase(thumbnail))
        parts.append(_composition_phrase(thumbnail))
        parts.append(f"mood: {thumbnail.mood.value}")
        parts.append(", ".join(SDXL.thumbnail_tokens))
        parts.append(SDXL.aspect_phrase)
        prompt = ", ".join(parts)

        # Length optimization for thumbnails too.
        prompt = optimize_prompt_length(prompt, self.profile.max_positive_words, model_key="sdxl")

        self.check_word_cap(prompt, "thumbnail")

        negative = _dedupe(
            list(thumbnail.exclude)  # type: ignore[attr-index]
            + ["text", "letters", "words", "captions"]
            + list(SDXL.negative_tokens)  # type: ignore[attr-type]
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
        prompt = optimize_prompt_length(prompt, self.profile.max_positive_words, model_key="sdxl")
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
        prompt = optimize_prompt_length(prompt, self.profile.max_positive_words, model_key="sdxl")
        self.check_word_cap(prompt, "thumbnail")

        tokens = (
            list(winner.objects_to_avoid)
            + list(winner.negative_elements)
            + (list(_DIAGRAM_NEGATIVES) if winner.intent.shot_type in DIAGRAM_LIKE_SHOTS else [])
            + ["text", "letters", "words", "captions"]
            + list(SDXL.negative_tokens)  # type: ignore[attr-type]
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


# ------------------------------------------------------------------- #
# Registration
# ------------------------------------------------------------------- #


register_compiler(SDXLCompiler())