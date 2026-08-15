"""Backend adapter contract (Phase 10).

Every backend adapter implements the same interface: turn the compiled
prompt, the render profile, and the Model Director's SceneModelPlan into
the canonical BackendWorkflow. The workflow dict is a strict superset of
the legacy Phase-6 shape (workflow_version, profile, sampler, steps, cfg,
resolution, loras, negative_tokens, positive_prompt, negative_prompt,
nodes), so render requests, fingerprints, and the renderer protocol need
no changes - new models only add keys.

No backend-specific string lives outside the adapters and the knowledge
model_director tables.
"""

from __future__ import annotations

from typing import Protocol

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer.render_profiles import RenderProfile
from pydantic import BaseModel, ConfigDict, Field

from runtime.models import WORKFLOW_VERSION


class BackendWorkflow(BaseModel):
    """The canonical, backend-annotated workflow payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_version: str = WORKFLOW_VERSION
    backend: str = Field(min_length=1, max_length=40)
    profile: str = Field(min_length=1, max_length=40)
    sampler: str = Field(min_length=1, max_length=40)
    scheduler: str = Field(min_length=1, max_length=40)
    steps: int = Field(ge=1, le=80)
    cfg: float = Field(ge=1.0, le=15.0)
    resolution: str = Field(min_length=1, max_length=40)
    aspect_ratio: str = Field(min_length=1, max_length=16)
    vae: str = Field(min_length=1, max_length=80)
    loras: tuple[str, ...] = Field(default_factory=tuple, max_length=4)
    negative_tokens: tuple[str, ...] = Field(default_factory=tuple, max_length=12)
    positive_prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    controlnet: str = Field(default="none", max_length=40)
    ip_adapter: str = Field(default="none", max_length=40)
    depth_strategy: str = Field(default="none", max_length=40)
    segmentation_strategy: str = Field(default="none", max_length=40)
    upscaler: str = Field(default="none", max_length=40)
    refiner: str = Field(default="none", max_length=40)
    animation_backend: str = Field(default="none", max_length=40)
    quality_target: str = Field(default="balanced", max_length=40)
    nodes: dict[str, str] = Field(default_factory=dict, max_length=8)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class BackendAdapter(Protocol):
    """One backend adapter: SceneModelPlan + prompt -> canonical workflow."""

    backend: str

    def adapt(
        self,
        prompt: CompiledPrompt,
        profile: RenderProfile,
        plan: SceneModelPlan,
    ) -> BackendWorkflow: ...
