"""Model Director (Phase 10): the deterministic multi-model decision engine.

Sits between the AI Director and the Prompt Compiler / Workflow Builder.
Consumes a DirectorOutput (the creative brief) and emits a ModelOutput:
the best image model, video model, VAE, sampler, scheduler, CFG,
resolution, aspect ratio, render profile, LoRA set, ControlNet /
IPAdapter / depth / segmentation strategy, upscaler, refiner, animation
backend, and the per-scene predictions (VRAM, time, QA, success
probability, retry count) - before any prompt is generated.

Not an LLM: every decision is a pure function of the brief, the registry
capabilities, and the backend-rule tables. No model-specific string lives
outside the registry, the backend rules, and the runtime adapters.
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import (
    BACKEND_RULES,
    QUALITY_TARGETS,
    BackendParams,
    QualityTarget,
    backend_params,
    default_animation_backend,
    default_aspect_ratio,
    default_cfg,
    default_model_key,
    default_resolution,
    default_sampler,
    default_scheduler,
    default_vae,
    family_of,
)
from knowledge.model_director.compatibility import (
    CompatibilityReport,
    check_model,
    compatibility_matrix,
    compatible_model_for,
    spec_for,
)
from knowledge.model_director.controlnet_selector import (
    select_controlnet,
    select_depth_strategy,
    select_ip_adapter,
    select_segmentation_strategy,
)
from knowledge.model_director.fallback_strategy import (
    MIN_IMPROVEMENT,
    SWITCH_AFTER_ATTEMPTS,
    chain_exhausted,
    fallback_chain,
    next_fallback,
    should_switch_model,
)
from knowledge.model_director.lora_selector import select_loras
from knowledge.model_director.model_profiles import (
    MODEL_DIRECTOR_VERSION,
    ModelOutput,
    ModelProfile,
    SceneModelPlan,
)
from knowledge.model_director.model_registry import (
    DEFAULT_MODEL_KEY,
    DEFAULT_VIDEO_MODEL_KEY,
    MODELS,
    REGISTRY,
    ModelKind,
    ModelRegistry,
    ModelSpec,
    model_count,
)
from knowledge.model_director.model_selector import ModelDirector, replan_for_model
from knowledge.model_director.performance_predictor import (
    estimated_time_seconds,
    expected_vram_mb,
)
from knowledge.model_director.quality_predictor import (
    expected_qa_score,
    expected_retry_count,
    expected_success_probability,
    expected_video_quality,
)
from knowledge.model_director.render_profile_selector import (
    quality_target_for,
    select_render_profile,
    target_settings,
)
from knowledge.model_director.sampler_selector import (
    preferred_samplers,
    select_sampler,
)
from knowledge.model_director.scheduler_selector import (
    select_scheduler,
    select_vae,
)

__all__ = [
    "BACKEND_RULES",
    "BackendParams",
    "CompatibilityReport",
    "DEFAULT_MODEL_KEY",
    "DEFAULT_VIDEO_MODEL_KEY",
    "MIN_IMPROVEMENT",
    "MODELS",
    "MODEL_DIRECTOR_VERSION",
    "ModelDirector",
    "ModelKind",
    "ModelOutput",
    "ModelProfile",
    "ModelRegistry",
    "ModelSpec",
    "QUALITY_TARGETS",
    "QualityTarget",
    "REGISTRY",
    "SWITCH_AFTER_ATTEMPTS",
    "SceneModelPlan",
    "backend_params",
    "chain_exhausted",
    "check_model",
    "compatibility_matrix",
    "compatible_model_for",
    "default_animation_backend",
    "default_aspect_ratio",
    "default_cfg",
    "default_model_key",
    "default_resolution",
    "default_sampler",
    "default_scheduler",
    "default_vae",
    "estimated_time_seconds",
    "expected_qa_score",
    "expected_retry_count",
    "expected_success_probability",
    "expected_video_quality",
    "expected_vram_mb",
    "fallback_chain",
    "family_of",
    "model_count",
    "next_fallback",
    "preferred_samplers",
    "quality_target_for",
    "replan_for_model",
    "select_controlnet",
    "select_depth_strategy",
    "select_ip_adapter",
    "select_loras",
    "select_render_profile",
    "select_sampler",
    "select_scheduler",
    "select_segmentation_strategy",
    "select_vae",
    "should_switch_model",
    "spec_for",
    "target_settings",
]
