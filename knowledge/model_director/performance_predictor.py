"""Performance predictor: expected VRAM and wall-clock time (Phase 10).

Pure deterministic estimates from the registry's resource facts and the
backend rules' per-family cost tables:

- VRAM scales with the resolution's area against the model's base VRAM.
- Time is steps x seconds-per-step x a resolution factor.

The estimates drive the Model Director's selection constraints (VRAM
budget) and the per-scene plan the runtime reports.
"""

from __future__ import annotations

from knowledge.model_director.backend_rules import backend_params
from knowledge.model_director.model_registry import REGISTRY


def _area(resolution: str) -> int:
    width, height = (int(part) for part in resolution.lower().split("x"))
    return width * height


_BASE_RESOLUTION_AREA = _area("832x1216")  # 1,011,712 px


def expected_vram_mb(model_key: str, resolution: str) -> int:
    """Expected VRAM (MiB): the model's base VRAM scaled by resolution."""
    spec = REGISTRY.get(model_key)
    factor = 0.75 + 0.25 * (_area(resolution) / _BASE_RESOLUTION_AREA)
    return round(spec.vram_mb * factor)


def estimated_time_seconds(
    model_key: str,
    steps: int,
    resolution: str,
) -> float:
    """Estimated render seconds: steps x per-step cost x resolution factor."""
    per_step = backend_params(model_key).time_per_step_seconds
    factor = 0.6 + 0.4 * (_area(resolution) / _BASE_RESOLUTION_AREA)
    return round(steps * per_step * factor, 1)
