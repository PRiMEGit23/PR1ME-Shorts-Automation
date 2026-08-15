"""Renderer contract and the deterministic simulated renderer.

The runtime never calls an LLM and, in this phase, never calls ComfyUI.
A Renderer turns a RenderRequest into a RenderResult: observed image
metadata (the vision pipeline's reading) plus the image bytes. Real
deployments implement this protocol with a live ComfyUI + vision client;
the SimulatedRenderer stands in with a fully deterministic defect model:

  quality(field) = base(seed, field)            (attempt 1)
  quality(field) = cured when the optimizer's
                   prescription is in the prompt (later attempts)

The base defect is derived from the session seed; the cure comes from
optimizer-produced tokens already present in the prompt or workflow. So a
broken first attempt only improves when the optimizer's prescriptions
actually land in the prompt - the loop closes for real, deterministically,
with no randomness and no model calls.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Protocol

from knowledge.image_qa.qa_models import GeneratedImageMetadata

from runtime.models import RenderRequest, RenderResult


class Renderer(Protocol):
    """Anything that can render one request deterministically."""

    def render(self, request: RenderRequest) -> RenderResult: ...


def _frac(seed: int, salt: str) -> float:
    digest = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / (2**64)


def _round(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 3)


def tiny_png(seed: int, attempt: int) -> bytes:
    """A deterministic 8x8 PNG (stdlib only) so every attempt has an image."""
    digest = hashlib.sha256(f"png:{seed}:{attempt}".encode()).digest()
    red, green, blue = digest[0], digest[1], digest[2]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    rows = b""
    for _ in range(8):
        rows += b"\x00" + bytes([red, green, blue]) * 8
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class SimulatedRenderer:
    """Deterministic ComfyUI stand-in; same request always renders identically."""

    def render(self, request: RenderRequest) -> RenderResult:
        prompt = request.prompt
        negative = request.negative_prompt or ""
        seed = request.seed
        scene_id = request.scene_id

        # --- clutter / clarity (before composition: the composition cure also clears) --
        clutter = _round(0.30 + 0.45 * _frac(seed, "clutter"))
        clarity = _round(0.50 + 0.40 * _frac(seed, "clarity"))

        # --- composition -----------------------------------------------------------
        composition_rule = _frac(seed, "composition_rule") >= 0.3
        composition_quality = _round(0.30 + 0.40 * _frac(seed, "composition_q"))
        if "focal point" in prompt or "dominating the frame" in prompt:
            composition_rule = True
            composition_quality = 0.92
            clutter = min(clutter, 0.50)

        if "clutter" in negative:
            clutter = 0.20
        if "background objects" in negative:
            clarity = 0.92

        # --- primary subject visibility -------------------------------------------
        prominence = _round(0.35 + 0.35 * _frac(seed, "prominence"))
        occluded = _frac(seed, "occluded") < 0.75
        if "dominating the frame" in prompt:
            occluded = False
        if "emphasize the primary subject" in prompt:
            prominence = 0.95

        # --- subject hierarchy -----------------------------------------------------
        hierarchy_clear = _frac(seed, "hierarchy") >= 0.3
        if "subject hierarchy" in prompt:
            hierarchy_clear = True

        # --- engineering accuracy ---------------------------------------------------
        accuracy = _round(0.30 + 0.40 * _frac(seed, "accuracy"))
        if "engineering visualization" in prompt:
            accuracy = 0.95

        # --- geometry ---------------------------------------------------------------
        geometry_correct = _frac(seed, "geometry") >= 0.3
        geometry_quality = _round(0.40 + 0.40 * _frac(seed, "geometry_q"))
        if "exact silhouettes" in prompt:
            geometry_correct = True
            geometry_quality = 0.95

        # --- material ---------------------------------------------------------------
        material_correct = _frac(seed, "material") >= 0.3
        material_quality = _round(0.40 + 0.40 * _frac(seed, "material_q"))
        if "planned material" in prompt:
            material_correct = True
            material_quality = 0.95

        # --- camera -------------------------------------------------------------------
        # The optimizer re-asserts the planned camera phrase, duplicating it.
        camera_distance = _frac(seed, "camera_distance") >= 0.25
        camera_angle = _frac(seed, "camera_angle") >= 0.25
        lens = _frac(seed, "lens") >= 0.25
        if prompt.count("100mm macro lens") >= 2:
            camera_distance = True
            camera_angle = True
            lens = True

        # --- lighting -------------------------------------------------------------------
        lighting_direction = _frac(seed, "light_direction") >= 0.25
        lighting_style = _frac(seed, "light_style") >= 0.25
        if prompt.count("key lighting") >= 2 or "hard key style" in prompt:
            lighting_direction = True
            lighting_style = True

        # --- educational -----------------------------------------------------------------
        method_implemented = _frac(seed, "method") >= 0.3
        annotations = _frac(seed, "annotations") >= 0.3
        annotation_quality = _round(0.40 + 0.40 * _frac(seed, "annotation_q"))
        if "engineering visualization" in prompt or "callouts" in prompt:
            method_implemented = True
            annotations = True
            annotation_quality = 0.90

        # --- thumbnail --------------------------------------------------------------------
        thumbnail_contrast = _round(0.40 + 0.40 * _frac(seed, "contrast"))
        thumbnail_focus = _round(0.40 + 0.40 * _frac(seed, "focus"))
        if "high-contrast" in prompt:
            thumbnail_contrast = 0.95
        if "focal point" in prompt:
            thumbnail_focus = 0.92

        # --- consistency -------------------------------------------------------------------
        consistency = _round(0.50 + 0.40 * _frac(seed, "consistency"))
        violations: list[str] = []
        if _frac(seed, "consistency") < 0.35:
            violations = ["palette drift from the planned scene"]
        if "inconsistent color" in negative:
            consistency = 0.95
            violations = []

        mismatches: list[str] = []
        if _frac(seed, "prompt_terms") < 0.2:
            mismatches = ["shot type not reflected in the render"]
        if "align prompt terms" in prompt:
            mismatches = []

        metadata = GeneratedImageMetadata(
            scene_id=scene_id,
            subject_present=True,
            subject_prominence=prominence,
            subject_occluded=occluded,
            hierarchy_clear=hierarchy_clear,
            engineering_accuracy=accuracy,
            geometry_correct=geometry_correct,
            geometry_quality=geometry_quality,
            material_correct=material_correct,
            material_quality=material_quality,
            camera_distance_matches=camera_distance,
            camera_angle_matches=camera_angle,
            lens_matches=lens,
            lighting_direction_matches=lighting_direction,
            lighting_style_matches=lighting_style,
            composition_rule_matches=composition_rule,
            composition_quality=composition_quality,
            clutter_level=clutter,
            visual_clarity=clarity,
            method_implemented=method_implemented,
            annotations_present=annotations,
            annotation_quality=annotation_quality,
            comparison_axis_present=True,
            thumbnail_contrast=thumbnail_contrast,
            thumbnail_focus=thumbnail_focus,
            thumbnail_negative_space=True,
            scene_consistency=consistency,
            consistency_violations=violations,
            prompt_term_mismatches=mismatches,
        )
        return RenderResult(
            metadata=metadata,
            image_bytes=tiny_png(seed, request.attempt_index),
        )