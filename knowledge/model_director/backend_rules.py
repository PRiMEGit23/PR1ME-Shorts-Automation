"""Backend rules: the per-model-family parameter tables (Phase 10).

Everything that is model-specific and *not* a capability of the model
itself lives here: the default VAE, the default CFG / guidance, the
default scheduler, the default upscaler / refiner, the animation backend,
and the cost facts the performance predictor needs (seconds per step).

The single source of truth for *which parameters a model supports* is the
registry (``model_registry.py``); this module decides which supported
values the director *chooses by default*.

No model-specific string may live outside this module and the backend
adapters (``runtime/backends``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from knowledge.model_director.model_registry import DEFAULT_MODEL_KEY, REGISTRY


class QualityTarget(StrEnum):
    """The deterministic quality tiers the director may aim at."""

    FAST = "fast"
    BALANCED = "balanced"
    PREMIUM = "premium"


#: How a quality target changes the render: step multiplier, upscaler,
#: refiner, and whether to attempt the extra pass.
QUALITY_TARGETS: dict[QualityTarget, dict[str, Any]] = {
    QualityTarget.FAST: {
        "steps_multiplier": 0.5,
        "upscaler": "none",
        "refiner": "none",
    },
    QualityTarget.BALANCED: {
        "steps_multiplier": 1.0,
        "upscaler": "esrgan",
        "refiner": "none",
    },
    QualityTarget.PREMIUM: {
        "steps_multiplier": 1.5,
        "upscaler": "4x_ultrasharp",
        "refiner": "sdxl-refiner",
    },
}


class BackendParams(BaseModel):
    """The director's chosen defaults for one model family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: str = Field(min_length=1, max_length=40)
    vae: str = Field(min_length=1, max_length=80)
    sampler: str = Field(min_length=1, max_length=40)
    scheduler: str = Field(min_length=1, max_length=40)
    cfg: float = Field(ge=1.0, le=15.0)
    resolution: str = Field(min_length=1, max_length=40)
    aspect_ratio: str = Field(min_length=1, max_length=16)
    upscaler: str = Field(min_length=1, max_length=40)
    refiner: str = Field(min_length=1, max_length=40)
    animation_backend: str = Field(min_length=1, max_length=40)
    time_per_step_seconds: float = Field(gt=0.0)


#: Per-family defaults. The SDXL family keeps the render-profile's own
#: sampler / cfg / resolution as its single source (see
#: ``render_profile_selector``); the values here are overridden for SDXL by
#: the profile the scene's genre selected.
BACKEND_RULES: dict[str, BackendParams] = {
    "flux": BackendParams(
        family="flux",
        vae="flux-vae",
        sampler="euler",
        scheduler="flow_matching",
        cfg=3.5,
        resolution="832x1216",
        aspect_ratio="9:16",
        upscaler="4x_ultrasharp",
        refiner="none",
        animation_backend="flux",
        time_per_step_seconds=0.50,
    ),
    "sdxl": BackendParams(
        family="sdxl",
        vae="sdxl-vae-fp16-fix",
        sampler="dpmpp_2m",
        scheduler="karras",
        cfg=7.0,
        resolution="832x1216",
        aspect_ratio="9:16",
        upscaler="esrgan",
        refiner="sdxl-refiner",
        animation_backend="animatediff",
        time_per_step_seconds=0.35,
    ),
    "qwen": BackendParams(
        family="qwen",
        vae="qwen-vae",
        sampler="dpmpp_2m",
        scheduler="flow_matching",
        cfg=4.5,
        resolution="1024x1792",
        aspect_ratio="9:16",
        upscaler="4x_ultrasharp",
        refiner="none",
        animation_backend="qwen",
        time_per_step_seconds=0.80,
    ),
    "gpt_image": BackendParams(
        family="gpt_image",
        vae="gpt-image-vae",
        sampler="dpmpp_2m",
        scheduler="normal",
        cfg=4.0,
        resolution="1024x1792",
        aspect_ratio="9:16",
        upscaler="4x_ultrasharp",
        refiner="none",
        animation_backend="gpt_image",
        time_per_step_seconds=1.10,
    ),
    "hiredream": BackendParams(
        family="hiredream",
        vae="hiredream-vae",
        sampler="euler",
        scheduler="euler_ancestral",
        cfg=5.0,
        resolution="832x1216",
        aspect_ratio="9:16",
        upscaler="4x_ultrasharp",
        refiner="none",
        animation_backend="hiredream",
        time_per_step_seconds=0.70,
    ),
    "wan": BackendParams(
        family="wan",
        vae="wan-vae",
        sampler="euler",
        scheduler="flow_matching",
        cfg=5.0,
        resolution="832x1216",
        aspect_ratio="9:16",
        upscaler="4x_ultrasharp",
        refiner="none",
        animation_backend="wan_video_2.2",
        time_per_step_seconds=1.20,
    ),
    "ltx": BackendParams(
        family="ltx",
        vae="ltx-vae",
        sampler="dpmpp_2m",
        scheduler="flow_matching",
        cfg=4.5,
        resolution="768x1280",
        aspect_ratio="9:16",
        upscaler="none",
        refiner="none",
        animation_backend="ltx_video",
        time_per_step_seconds=0.60,
    ),
    "hunyuan": BackendParams(
        family="hunyuan",
        vae="hyvideo-vae",
        sampler="euler",
        scheduler="flow_matching",
        cfg=5.5,
        resolution="848x1512",
        aspect_ratio="9:16",
        upscaler="none",
        refiner="none",
        animation_backend="hunyuan_video",
        time_per_step_seconds=1.60,
    ),
    "cogvideo": BackendParams(
        family="cogvideo",
        vae="cogvideox-vae",
        sampler="euler",
        scheduler="flow_matching",
        cfg=6.0,
        resolution="832x1216",
        aspect_ratio="9:16",
        upscaler="none",
        refiner="none",
        animation_backend="cogvideox",
        time_per_step_seconds=0.90,
    ),
    "animatediff": BackendParams(
        family="animatediff",
        vae="sdxl-vae-fp16-fix",
        sampler="dpmpp_2m",
        scheduler="karras",
        cfg=7.0,
        resolution="512x896",
        aspect_ratio="9:16",
        upscaler="none",
        refiner="none",
        animation_backend="animatediff",
        time_per_step_seconds=0.25,
    ),
}


def backend_params(model_key: str) -> BackendParams:
    """The default parameters for a model's family, failing loudly."""
    spec = REGISTRY.get(model_key)
    try:
        return BACKEND_RULES[spec.family]
    except KeyError as exc:
        raise KeyError(f"no backend rules for family {spec.family!r}") from exc


def family_of(model_key: str) -> str:
    return REGISTRY.get(model_key).family


def default_cfg(model_key: str) -> float:
    """The model's default CFG / guidance value."""
    return backend_params(model_key).cfg


def default_resolution(model_key: str) -> str:
    """The model's default resolution (clamped into its supported set)."""
    return backend_params(model_key).resolution


def default_aspect_ratio(model_key: str) -> str:
    return backend_params(model_key).aspect_ratio


def default_sampler(model_key: str) -> str:
    return backend_params(model_key).sampler


def default_scheduler(model_key: str) -> str:
    return backend_params(model_key).scheduler


def default_vae(model_key: str) -> str:
    return backend_params(model_key).vae


def default_animation_backend(model_key: str) -> str:
    return backend_params(model_key).animation_backend


def default_model_key() -> str:
    """The default image model when nothing is requested."""
    return DEFAULT_MODEL_KEY
