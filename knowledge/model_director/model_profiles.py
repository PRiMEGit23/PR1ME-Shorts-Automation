"""Model profiles: the compiled backend profile and per-scene plans.

The Model Director's contract (Phase 10). One ``SceneModelPlan`` per
scene answers the mission's per-scene output list:

- the chosen image model, video model, and animation backend
- the compiled backend profile: VAE, sampler, scheduler, CFG, resolution,
  aspect ratio, LoRA set, ControlNet / IPAdapter / depth / segmentation
  strategy, upscaler, refiner, workflow (render) profile
- the predictions: quality target, expected VRAM, estimated time,
  expected QA score, expected success probability, expected retry count

Everything is frozen and JSON-serializable so the plans flow through the
pipeline checkpoints and fingerprints unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from knowledge.render_optimizer.render_profiles import RenderProfileKey
from knowledge.visual_intelligence.storyboard import ShotType

MODEL_DIRECTOR_VERSION = "10.0.0"


class ModelProfile(BaseModel):
    """One compiled backend profile: every backend parameter, resolved."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    image_model: str = Field(min_length=1, max_length=40)
    video_model: str = Field(min_length=1, max_length=40)
    animation_backend: str = Field(min_length=1, max_length=40)
    vae: str = Field(min_length=1, max_length=80)
    sampler: str = Field(min_length=1, max_length=40)
    scheduler: str = Field(min_length=1, max_length=40)
    cfg: float = Field(ge=1.0, le=15.0)
    steps: int = Field(ge=1, le=80)
    resolution: str = Field(min_length=1, max_length=40)
    aspect_ratio: str = Field(min_length=1, max_length=16)
    render_profile: RenderProfileKey
    loras: tuple[str, ...] = Field(default_factory=tuple, max_length=4)
    controlnet: str = Field(default="none", max_length=40)
    ip_adapter: str = Field(default="none", max_length=40)
    depth_strategy: str = Field(default="none", max_length=40)
    segmentation_strategy: str = Field(default="none", max_length=40)
    upscaler: str = Field(default="none", max_length=40)
    refiner: str = Field(default="none", max_length=40)
    quality_target: str = Field(min_length=1, max_length=40)
    negative_tokens: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    rationale: str = Field(default="", max_length=400)


class SceneModelPlan(BaseModel):
    """The complete Model Director decision for one scene."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_index: int = Field(ge=1)
    scene_id: str = Field(pattern=r"^S[1-9][0-9]*$")
    shot_type: ShotType
    is_hero: bool = False
    model_profile: ModelProfile
    workflow_profile: RenderProfileKey
    quality_target: str = Field(min_length=1, max_length=40)
    expected_vram_mb: int = Field(ge=512)
    estimated_time_seconds: float = Field(gt=0.0)
    expected_qa_score: float = Field(ge=0.0, le=100.0)
    expected_success_probability: float = Field(ge=0.0, le=1.0)
    expected_retry_count: int = Field(ge=1, le=10)


class ModelOutput(BaseModel):
    """The complete Model Director brief for one film."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = MODEL_DIRECTOR_VERSION
    topic: str = Field(min_length=1, max_length=200)
    scene_count: int = Field(ge=1, le=10)
    scene_plans: list[SceneModelPlan]
    summary: str = Field(default="", max_length=400)

    def plan_for(self, scene_id: str) -> SceneModelPlan:
        """The plan for one scene, failing loudly on unknown ids."""
        for plan in self.scene_plans:
            if plan.scene_id == scene_id:
                return plan
        raise KeyError(f"no model plan for scene {scene_id!r}")
