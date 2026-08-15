"""Compatibility: check any model against a proposed parameter set.

The compatibility checker is the guardrail between the directors and the
adapters: it verifies that a proposed sampler / scheduler / VAE /
resolution / aspect ratio / ControlNet / IPAdapter / depth / segmentation /
upscaler / refiner / animation backend combination is supported by the
chosen model. Every selector clamps through it; nothing reaches an adapter
with an incompatible parameter.

Rules come only from the registry's capability records - there is no
duplicated capability table anywhere else.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from knowledge.model_director.model_registry import REGISTRY, ModelSpec


class CompatibilityReport(BaseModel):
    """The verdict for one model against one proposed parameter set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_key: str
    compatible: bool
    violations: tuple[str, ...] = ()


def check_model(
    model_key: str,
    *,
    sampler: str | None = None,
    scheduler: str | None = None,
    vae: str | None = None,
    resolution: str | None = None,
    aspect_ratio: str | None = None,
    controlnet: str | None = None,
    ip_adapter: str | None = None,
    depth: str | None = None,
    segmentation: str | None = None,
    upscaler: str | None = None,
    refiner: str | None = None,
    animation_backend: str | None = None,
) -> CompatibilityReport:
    """Report every violation; None parameters are not checked."""
    spec = REGISTRY.get(model_key)
    violations: list[str] = []

    def _check(value: str | None, supported: tuple[str, ...], label: str) -> None:
        if value is None or value == "none":
            return
        if value not in supported:
            supported_text = ", ".join(sorted(supported)) if supported else "none"
            violations.append(f"{label} {value!r} not supported (supports: {supported_text})")

    _check(sampler, spec.supported_samplers, "sampler")
    _check(scheduler, spec.supported_schedulers, "scheduler")
    _check(vae, spec.supported_vaes, "vae")
    _check(resolution, spec.supported_resolutions, "resolution")
    _check(aspect_ratio, spec.supported_aspect_ratios, "aspect ratio")
    _check(controlnet, spec.supported_controlnet, "controlnet")
    _check(ip_adapter, spec.supported_ip_adapters, "ip adapter")
    _check(depth, spec.supported_depth, "depth")
    _check(segmentation, spec.supported_segmentation, "segmentation")
    _check(upscaler, spec.supported_upscalers, "upscaler")
    _check(refiner, spec.supported_refiners, "refiner")
    _check(animation_backend, spec.supported_animation_backends, "animation backend")

    return CompatibilityReport(
        model_key=model_key,
        compatible=not violations,
        violations=tuple(violations),
    )


def compatibility_matrix() -> dict[str, dict[str, bool]]:
    """The deterministic compatibility matrix for the architecture docs.

    One row per model; each cell says whether the parameter *family* is
    supported (any value other than none) by that model.
    """
    axis: list[tuple[str, str]] = [
        ("samplers", "supported_samplers"),
        ("schedulers", "supported_schedulers"),
        ("vaes", "supported_vaes"),
        ("resolutions", "supported_resolutions"),
        ("aspect_ratios", "supported_aspect_ratios"),
        ("controlnet", "supported_controlnet"),
        ("ip_adapter", "supported_ip_adapters"),
        ("depth", "supported_depth"),
        ("segmentation", "supported_segmentation"),
        ("upscalers", "supported_upscalers"),
        ("refiners", "supported_refiners"),
        ("animation_backends", "supported_animation_backends"),
    ]
    matrix: dict[str, dict[str, bool]] = {}
    for spec in REGISTRY.all():
        row: dict[str, bool] = {}
        for label, attribute in axis:
            row[label] = bool(getattr(spec, attribute))
        matrix[spec.key] = row
    return matrix


def compatible_model_for(
    model_key: str, params: dict[str, Any]
) -> CompatibilityReport:
    """Compatibility report for a partially filled parameter dict."""
    return check_model(model_key, **params)


def spec_for(model_key: str) -> ModelSpec:
    return REGISTRY.get(model_key)
