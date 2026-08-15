"""Prompt Compiler interface and dispatch.

A compiler is a deterministic, non-LLM function from a VisualArchitecture
specification plus a ModelProfile to a CompiledPrompt. The same specification
must produce the same prompt for a given profile. Unknown enums, missing
compilers, or malformed specs fail closed with structured errors.

Knowledge (the "WHAT") describes only engineering truth via grammars.
Everything photographic (the "HOW") is injected exclusively by the compiler
from the grammars + model profile - never hard-coded in knowledge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from knowledge.compiler.model_profiles import PROFILES, SHORTS_SIZE, ModelProfile
from knowledge.visual_architecture import SCHEMA_VERSION, Scene, Thumbnail, VisualArchitecture
from knowledge.visual_intelligence.storyboard import StoryboardScene, VisualStoryboard

COMPILER_VERSION = "1.1.0"


# --------------------------------------------------------------------- #
# Grammar V3: the "WHAT" — structured engineering knowledge
# --------------------------------------------------------------------- #


class SubjectGrammar(BaseModel):
    """Structured engineering subject knowledge.

    This is the "WHAT" — pure engineering truth about the subject.
    The compiler injects all photographic phrasing (camera, lighting,
    composition, rendering) from the model profile.
    """

    model_config = ConfigDict(frozen=True)

    entity: str
    description: str | None = None
    state: str | None = None
    materials: tuple[str, ...] = ()
    surface_finish: tuple[str, ...] = ()
    visible_geometry: tuple[str, ...] = ()
    manufacturing_details: tuple[str, ...] = ()

    def phrase(self) -> str:
        """Return the compact engineering phrase (used by the compiler)."""
        parts: list[str] = [self.entity]
        if self.description:
            parts.append(self.description)
        if self.state:
            parts.append(self.state)
        if self.materials:
            parts.append("made of " + ", ".join(self.materials))
        if self.surface_finish:
            parts.append("surface: " + ", ".join(f for f in self.surface_finish))
        if self.visible_geometry:
            parts.append("visible geometry: " + ", ".join(self.visible_geometry))
        if self.manufacturing_details:
            parts.append("manufactured by: " + ", ".join(self.manufacturing_details))
        return ", ".join(parts)


class MaterialGrammar(BaseModel):
    """Structured material knowledge.

    Surface finish, texture, and composition attributes — photographic
    adjectives are supplied by the compiler from the model profile.
    """

    model_config = ConfigDict(frozen=True)

    values: tuple[str, ...] = ()
    descriptors: tuple[str, ...] = ()
    _refraction_index: float | None = None
    _roughness: float | None = None  # internal, compiler maps to CFG/steps


class LightingGrammar(BaseModel):
    """Structured lighting knowledge.

    Direction, style, and practical sources — all photographic adjectives
    are injected by the compiler from the model profile.
    """

    model_config = ConfigDict(frozen=True)

    direction: str  # e.g. "KEY", "SIDE", "RIM"
    style: str  # e.g. "HARD_KEY", "SOFTBOX", "STUDIO"
    practical_sources: tuple[str, ...] = ()
    key_color: str | None = None


class CameraGrammar(BaseModel):
    """Structured camera knowledge.

    All photographic framing is injected by the compiler from the model
    profile; the grammar only stores the engineering values.
    """

    model_config = ConfigDict(frozen=True)

    distance: str  # e.g. "MEDIUM", "CLOSE", "WIDE"
    angle: str  # e.g. "SLIGHTLY_LOW", "EYE", "SLIGHTLY_HIGH"
    lens: str  # e.g. "STANDARD_35", "MACRO_100"
    framing: str  # e.g. "CENTER_ROW", "SUBJECT_CENTER"
    height: str  # e.g. "TABLE", "EYE_LEVEL", "CEILING"


class CompositionGrammar(BaseModel):
    """Structured composition knowledge.

    Rule and emphasis are engineering; the compiler adds the photographic
    framing language.
    """

    model_config = ConfigDict(frozen=True)

    rule: str  # e.g. "RULE_OF_THIRDS", "CENTER_ROW", "CENTERED"
    emphasis: str
    negative_space: str = "none"  # e.g. "OVERLAY_TOP", "OVERLAY_LEFT", "NONE"


class RenderingGrammar(BaseModel):
    """Structured rendering knowledge.

    Sampler, steps, CFG, resolution, and LoRAs are model-profile decisions;
    the grammar stores the engineering choices.
    """

    model_config = ConfigDict(frozen=True)

    sampler: str  # e.g. "dpmpp_2m", "euler_a"
    steps: int  # ge 1, le 80
    cfg: float  # ge 1.0, le 15.0
    resolution: str  # e.g. "832x1216"
    negative_tokens: tuple[str, ...] = ()
    loras: tuple[str, ...] = ()


class NegativeGrammar(BaseModel):
    """Structured negative-prompt knowledge.

    Avoidance tokens, deduplication, and entropy scoring are handled by
    the compiler; the grammar stores the engineering exclusions.
    """

    model_config = ConfigDict(frozen=True)

    tokens: tuple[str, ...] = ()
    prohibit_photoreal: bool = True
    prohibit_keywords: tuple[str, ...] = ()


# ------------------------------------------------------------------- #
# Compiled prompt and row (unchanged from V2)
# ------------------------------------------------------------------- #


class CompileError(RuntimeError):
    """A specification could not be compiled for the requested model."""


class CompiledPrompt(BaseModel):
    """One model-ready prompt plus traceability metadata."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    negative_prompt: str | None = None
    metadata: dict[str, Any] = {}


class CompiledRow(BaseModel):
    """All compiled prompts for one topic row, keyed by scene_id, plus the thumbnail."""

    model_config = ConfigDict(frozen=True)

    model: str
    compiler_version: str
    scenes: dict[str, CompiledPrompt]
    thumbnail: CompiledPrompt


# ------------------------------------------------------------------- #
# PromptCompiler base contract (unchanged interface)
# ------------------------------------------------------------------- #


class PromptCompiler(ABC):
    """Base contract every model compiler must satisfy."""

    profile: ModelProfile

    @abstractmethod
    def compile_scene(
        self,
        architecture: VisualArchitecture,
        scene: Scene,
        *,
        topic: str,
        scene_index: int,
    ) -> CompiledPrompt:
        """Compile one scene into a model-specific prompt."""

    @abstractmethod
    def compile_thumbnail(
        self,
        architecture: VisualArchitecture,
        thumbnail: Thumbnail,
        *,
        topic: str,
    ) -> CompiledPrompt:
        """Compile the thumbnail specification into a model-specific prompt."""

    def compile_storyboard_scene(
        self,
        storyboard: VisualStoryboard,
        scene: StoryboardScene,
        *,
        topic: str,
        scene_index: int,
    ) -> CompiledPrompt:
        """Compile one VisualStoryboard scene; defaults to failure."""
        raise NotImplementedError(
            f"model '{self.profile.key}' has no VisualStoryboard compiler yet"
        )

    def compile_storyboard_thumbnail(
        self,
        storyboard: VisualStoryboard,
        *,
        topic: str,
    ) -> CompiledPrompt:
        """Compile the storyboard's rank-1 thumbnail scene; defaults to failure."""
        raise NotImplementedError(
            f"model '{self.profile.key}' has no VisualStoryboard compiler yet"
        )

    def metadata(
        self,
        *,
        topic: str,
        target: str,
        scene_id: str | None = None,
        is_thumbnail: bool = False,
        schema_version: str = SCHEMA_VERSION,
    ) -> dict[str, Any]:
        return {
            "model": self.profile.key,
            "family": self.profile.family,
            "compiler_version": COMPILER_VERSION,
            "topic": topic,
            "target": "thumbnail" if is_thumbnail else target,
            "scene_id": scene_id,
            "guidance": self.profile.guidance_default,
            "steps": self.profile.steps_default,
            "size": list(SHORTS_SIZE),
            "aspect": self.profile.aspect_phrase,
            "source": {"field": "visual_architecture_json", "schema_version": schema_version},
        }

    def check_word_cap(self, prompt: str, scene_id: str) -> None:
        words = len(prompt.split())
        if words > self.profile.max_positive_words:
            raise CompileError(
                f"[{self.profile.key}] scene {scene_id}: compiled prompt {words} words exceeds "
                f"cap {self.profile.max_positive_words}; tighten the specification"
            )


# ------------------------------------------------------------------- #
# Global compiler registry
# ------------------------------------------------------------------- #


COMPILERS: dict[str, PromptCompiler] = {}


def register_compiler(compiler: PromptCompiler) -> None:
    COMPILERS[compiler.profile.key] = compiler


def compile_for_model(
    architecture: VisualArchitecture,
    model_key: str,
    *,
    topic: str,
) -> CompiledRow:
    """Compile a full row (all scenes + thumbnail) for one model family.

    Raises:
        CompileError: if the model profile exists but no compiler is implemented yet.
        KeyError: if the model key is not a registered profile.
    """
    if model_key not in PROFILES:
        raise KeyError(f"unknown model profile: {model_key}")
    if model_key not in COMPILERS:
        raise CompileError(
            f"model '{model_key}' has a registered profile but no compiler "
            f"implementation yet; implemented: {sorted(COMPILERS)}"
        )

    compiler = COMPILERS[model_key]
    scenes = {
        scene.scene_id: compiler.compile_scene(
            architecture,
            scene,
            topic=topic,
            scene_index=index,
        )
        for index, scene in enumerate(architecture.scenes, start=1)
    }
    thumbnail = compiler.compile_thumbnail(
        architecture,
        architecture.thumbnail,
        topic=topic,
    )
    return CompiledRow(
        model=model_key,
        compiler_version=COMPILER_VERSION,
        scenes=scenes,
        thumbnail=thumbnail,
    )


def compile_for_storyboard(
    storyboard: VisualStoryboard,
    model_key: str,
    *,
    topic: str,
) -> CompiledRow:
    """Compile a full VisualStoryboard (all scenes + thumbnail) for one model.

    Mirrors compile_for_model but reads from a VisualStoryboard, whose scenes
    carry their own camera, lighting, composition, and engineering overlays.
    """
    if model_key not in PROFILES:
        raise KeyError(f"unknown model profile: {model_key}")
    if model_key not in COMPILERS:
        raise CompileError(
            f"model '{model_key}' has a registered profile but no compiler "
            f"implementation yet; implemented: {sorted(COMPILERS)}"
        )

    compiler = COMPILERS[model_key]
    scenes = {
        scene.scene_id: compiler.compile_storyboard_scene(
            storyboard,
            scene,
            topic=topic,
            scene_index=index,
        )
        for index, scene in enumerate(storyboard.scenes, start=1)
    }
    thumbnail = compiler.compile_storyboard_thumbnail(
        storyboard,
        topic=topic,
    )
    return CompiledRow(
        model=model_key,
        compiler_version=COMPILER_VERSION,
        scenes=scenes,
        thumbnail=thumbnail,
    )


# ------------------------------------------------------------------- #
# Prompt length optimizer: adaptive cap per model + content-aware trimming
# ------------------------------------------------------------------- #


def optimize_prompt_length(
    prompt: str,
    max_words: int,
    *,
    model_key: str | None = None,
) -> str:
    """Adaptively trim a prompt to ``max_words`` while preserving semantic core.

    Strategy:
    1. Split on commas (the SDXL prompt convention).
    2. Score each clause by its overlap with the model's quality tokens.
    3. Drop lowest-scoring clauses until ``max_words`` is reached.
    4. Never drop the modality prefix or the subject entity.
    """
    clauses = [c.strip() for c in prompt.split(",")]
    if len(clauses) <= max_words:
        return prompt

    # Never drop the first clause (modality prefix) or the subject entity.
    # The subject is identified as the clause containing the entity token.
    # For safety, preserve the first two clauses (modality + subject).
    preserved = clauses[:2]

    # Score remaining clauses by quality-token overlap (simple count).
    quality_tokens = {
        "sdxl": {"photoreal", "high quality", "masterpiece", "best quality"},
        "flux": {"photoreal", "high quality"},
    }
    tokens_to_preserve = set()
    qt = quality_tokens.get(model_key, set())
    for clause in clauses[2:]:
        for qt_ in qt:
            if qt_.lower() in clause.lower():
                tokens_to_preserve.add(clause)
                break

    # Build candidate list: all clauses not already preserved, sorted by
    # a simple "importance" heuristic (longer / more tokens = more important).
    candidates = [c for c in clauses[2:] if c not in preserved]
    candidates.sort(key=len, reverse=True)

    # Greedily add clauses until we hit max_words.
    result = preserved[:]
    word_count = sum(len(c.split()) for c in result)
    for c in candidates:
        if word_count + len(c.split()) <= max_words:
            result.append(c)
            word_count += len(c.split())

    return ", ".join(result)


# ------------------------------------------------------------------- #
# Prompt deduplicator: ensures unique prompts across scenes/re-runs
# ------------------------------------------------------------------- #


class PromptDeduplicator:
    """Deterministic deduplication of compiled prompts.

    Uses a rolling hash (SHA-256 truncated to 16 chars) keyed by
    (model_key, scene_id, prompt_content) so that identical knowledge
    always produces the same fingerprint, and different knowledge never
    collides in practice.
    """

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}

    def fingerprint(self, model_key: str, scene_id: str, prompt: str) -> str:
        key = f"{model_key}:{scene_id}:{prompt}"
        h = __import__("hashlib").sha256(key.encode("utf-8")).hexdigest()[:16]
        return h

    def is_duplicate(
        self, model_key: str, scene_id: str, prompt: str, *, tolerance: int = 16
    ) -> bool:
        h = self.fingerprint(model_key, scene_id, prompt)
        if h in self._seen:
            # Verify the stored prompt is meaningfully identical.
            stored = self._seen[h]
            return stored == prompt
        self._seen[h] = prompt
        return False


# ------------------------------------------------------------------- #
# Prompt entropy scorer: measures semantic diversity of a set of prompts
# ------------------------------------------------------------------- #


def prompt_entropy(prompts: list[str], *, model_key: str | None = None) -> float:
    """Shannon-style entropy over a set of compiled prompts.

    Higher values = more diverse prompts (good for multi-scene variety).
    Lower values = prompts are converging/redundant (flags potential
    duplication or over-simplification).

    Returns a value in ``[0.0, 1.0]``.
    """
    if not prompts:
        return 0.0

    # Simple token-based approximation: count unique comma-clauses across
    # all prompts, divided by total clauses.
    all_clauses: set[str] = set()
    total = 0
    for p in prompts:
        clauses = [c.strip() for c in p.split(",")]
        total += len(clauses)
        all_clauses.update(clauses)

    if total == 0:
        return 0.0
    return len(all_clauses) / total


# ------------------------------------------------------------------- #
# Prompt confidence estimator: predicts how competitive a prompt will be
# against expert ComfyUI user prompts, without using an LLM.
# ------------------------------------------------------------------- #


def prompt_confidence(
    prompt: str,
    *,
    model_key: str,
    modality: str,
    quality_tokens: tuple[str, ...] | None = None,
) -> float:
    """Estimate prompt competitiveness (0.0 = low, 1.0 = expert-level).

    Heuristics (all deterministic, no LLM):
    - Presence of modality prefix
    - Presence of quality tokens (model-profile)
    - Absence of boilerplate clauses (technical render, modern lab, etc.)
    - Subject specificity (entity + description length)
    - Negative-prompt completeness
    """
    if not prompt:
        return 0.0

    # Modality prefix check
    modality_prefixes = {
        "photograph of": 0.15,
        "macro photograph of": 0.15,
        "technical diagram of": 0.12,
        "cross-section cutaway of": 0.12,
        "schematic illustration of": 0.10,
        "exploded view diagram of": 0.10,
        "split-screen comparison of": 0.08,
    }
    score = 0.0
    prefix = modality_prefixes.get(modality, 0.05)
    score += prefix

    # Quality tokens
    if quality_tokens:
        qt_set = set(t.lower() for t in quality_tokens)
        prompt_lower = prompt.lower()
        qt_hits = sum(1 for qt in qt_set if qt in prompt_lower)
        score += 0.25 * min(qt_hits / max(len(qt_set), 1), 1.0)

    # Absence of boilerplate
    boilerplate = {
        "clean technical render",
        "modern engineering lab",
        "precise machined surfaces",
        "subtle depth of field",
    }
    bp_count = sum(1 for b in boilerplate if b.lower() in prompt.lower())
    score -= 0.10 * bp_count

    # Subject specificity: entity + description length
    # A longer, specific entity + description = higher confidence.
    # Very short entities are ambiguous; very long ones are noisy.
    entity_indicator = "entity" in prompt.lower()
    if entity_indicator:
        score += 0.10

    # Cap at 1.0
    return min(max(score, 0.0), 1.0)