"""Model selector: the Model Director orchestrator (Phase 10).

Picks the best image model, video model, and the complete compiled
backend profile for every scene - a pure deterministic function of the
AI Director's brief, the registry's capability records, and the backend
rules' parameter tables. The pipeline changes only the compiled profile
to generate the same film on any supported model family.

The orchestrator holds no rules: every decision lives in the selector
modules it calls (``render_profile_selector``, ``sampler_selector``,
``scheduler_selector``, ``lora_selector``, ``controlnet_selector``,
``quality_predictor``, ``performance_predictor``, ``backend_rules``).
"""

from __future__ import annotations

from knowledge.ai_director.director_models import DirectorOutput, SceneDirective
from knowledge.model_director.backend_rules import (
    QualityTarget,
    backend_params,
    default_animation_backend,
    default_cfg,
    default_resolution,
)
from knowledge.model_director.compatibility import check_model
from knowledge.model_director.controlnet_selector import (
    select_controlnet,
    select_depth_strategy,
    select_ip_adapter,
    select_segmentation_strategy,
)
from knowledge.model_director.lora_selector import select_loras
from knowledge.model_director.model_profiles import (
    MODEL_DIRECTOR_VERSION,
    ModelOutput,
    ModelProfile,
    SceneModelPlan,
)
from knowledge.model_director.model_registry import REGISTRY, ModelKind, ModelRegistry, ModelSpec
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
from knowledge.model_director.sampler_selector import select_sampler
from knowledge.model_director.scheduler_selector import select_scheduler, select_vae
from knowledge.render_optimizer.render_profiles import (
    RenderProfileKey,
    profile_for,
)


class ModelDirector:
    """Deterministic per-scene model and backend-profile selection."""

    def __init__(self, registry: ModelRegistry = REGISTRY) -> None:
        self._registry = registry

    def direct(
        self,
        director_output: DirectorOutput,
        *,
        preferred_model: str | None = None,
        vram_budget_mb: int | None = None,
        quality_target: QualityTarget | None = None,
    ) -> ModelOutput:
        """Compile the per-scene model plans for one creative brief."""
        plans: list[SceneModelPlan] = []
        for directive in director_output.scene_directives:
            plans.append(
                self._plan_scene(
                    directive,
                    preferred_model=preferred_model,
                    vram_budget_mb=vram_budget_mb,
                    quality_target=quality_target,
                )
            )
        image_models = {plan.model_profile.image_model for plan in plans}
        video_models = {plan.model_profile.video_model for plan in plans}
        summary = (
            f"{len(plans)} scenes; image {', '.join(sorted(image_models))}; "
            f"video {', '.join(sorted(video_models))}; "
            f"predicted QA {min(p.expected_qa_score for p in plans):.0f}-"
            f"{max(p.expected_qa_score for p in plans):.0f}, "
            f"retries {min(p.expected_retry_count for p in plans)}-"
            f"{max(p.expected_retry_count for p in plans)}"
        )
        return ModelOutput(
            version=MODEL_DIRECTOR_VERSION,
            topic=director_output.topic,
            scene_count=len(plans),
            scene_plans=plans,
            summary=summary,
        )

    # ------------------------------------------------------------ internals --

    def _plan_scene(
        self,
        directive: SceneDirective,
        *,
        preferred_model: str | None,
        vram_budget_mb: int | None,
        quality_target: QualityTarget | None,
    ) -> SceneModelPlan:
        visualization_type = (
            directive.engineering_visualizations[0].type
            if directive.engineering_visualizations
            else None
        )
        profile, profile_reason = select_render_profile(
            directive.shot_type, visualization_type
        )
        image_model = self._best_image_model(
            directive,
            preferred=preferred_model,
            vram_budget_mb=vram_budget_mb,
        )
        video_model = self._best_video_model()
        target, target_reason = quality_target_for(
            is_hero=directive.is_hero,
            is_thumbnail=directive.is_thumbnail,
            importance=directive.importance,
            visual_budget=directive.visual_budget,
            quality_target=quality_target,
        )
        return self._compile_plan(
            directive,
            image_model=image_model,
            video_model=video_model,
            profile=profile,
            vram_budget_mb=vram_budget_mb,
            rationale=f"{profile_reason}; {target_reason}",
            target=target,
        )

    def _best_image_model(
        self,
        directive: SceneDirective,
        *,
        preferred: str | None,
        vram_budget_mb: int | None,
    ) -> str:
        """Best model by quality-weighted score, VRAM-filtered.

        Tie-breaks: the preferred model wins exact ties, then registry
        order. Preference only breaks ties - a clearly better model is
        never overruled by the default.
        """
        candidates = [
            spec
            for spec in self._registry.of_kind(ModelKind.IMAGE)
            if self._fits_vram_budget(spec, vram_budget_mb)
        ]

        def score(spec: ModelSpec) -> float:
            qa = expected_qa_score(spec.key, directive.shot_type)
            return qa * (1.0 + 0.04 * (directive.importance - 3))

        def key(spec: ModelSpec) -> tuple[float, int, int]:
            order = candidates.index(spec)
            return (score(spec), 1 if spec.key == preferred else 0, -order)

        return max(candidates, key=key).key

    def _best_video_model(self) -> str:
        candidates = self._registry.of_kind(ModelKind.VIDEO)
        return max(candidates, key=lambda spec: (expected_video_quality(spec.key),)).key

    @staticmethod
    def _fits_vram_budget(
        spec: ModelSpec, vram_budget_mb: int | None
    ) -> bool:
        if vram_budget_mb is None:
            return True
        return any(
            expected_vram_mb(spec.key, resolution) <= vram_budget_mb
            for resolution in spec.supported_resolutions
        )

    @staticmethod
    def _compile_plan(
        directive: SceneDirective,
        *,
        image_model: str,
        video_model: str,
        profile: RenderProfileKey,
        vram_budget_mb: int | None,
        rationale: str,
        target: QualityTarget,
    ) -> SceneModelPlan:
        spec = REGISTRY.get(image_model)
        steps_multiplier, upscaler, refiner = target_settings(target, image_model)
        raw_steps = int(spec.steps_range[1] * steps_multiplier)
        steps = min(max(raw_steps, spec.steps_range[0]), 80)

        resolution = _choose_resolution(spec, vram_budget_mb)
        cfg = _cfg_for(image_model, profile)
        sampler = select_sampler(image_model, profile)
        scheduler = select_scheduler(image_model, sampler)
        vae = select_vae(image_model)
        loras = select_loras(image_model, profile)
        controlnet = select_controlnet(image_model, directive.shot_type)
        ip_adapter = select_ip_adapter(image_model, is_hero=directive.is_hero)
        depth = select_depth_strategy(image_model, directive.shot_type)
        segmentation = select_segmentation_strategy(image_model)
        negative_tokens = tuple(profile_for(profile).negative_tokens)
        animation_backend = default_animation_backend(video_model)

        report = check_model(
            image_model,
            sampler=sampler,
            scheduler=scheduler,
            vae=vae,
            resolution=resolution,
            aspect_ratio=backend_params(image_model).aspect_ratio,
            controlnet=controlnet,
            ip_adapter=ip_adapter,
            depth=depth,
            segmentation=segmentation,
            upscaler=upscaler,
            refiner=refiner,
        )
        assert report.compatible, f"{image_model}: {report.violations}"

        qa = expected_qa_score(image_model, directive.shot_type)
        probability = expected_success_probability(qa, spec.reliability)
        vram = expected_vram_mb(image_model, resolution)
        seconds = estimated_time_seconds(image_model, steps, resolution)

        model_profile = ModelProfile(
            image_model=image_model,
            video_model=video_model,
            animation_backend=animation_backend,
            vae=vae,
            sampler=sampler,
            scheduler=scheduler,
            cfg=cfg,
            steps=steps,
            resolution=resolution,
            aspect_ratio=backend_params(image_model).aspect_ratio,
            render_profile=profile,
            loras=loras,
            controlnet=controlnet,
            ip_adapter=ip_adapter,
            depth_strategy=depth,
            segmentation_strategy=segmentation,
            upscaler=upscaler,
            refiner=refiner,
            quality_target=target.value,
            negative_tokens=negative_tokens,
            rationale=rationale,
        )
        return SceneModelPlan(
            scene_index=directive.scene_index,
            scene_id=directive.scene_id,
            shot_type=directive.shot_type,
            is_hero=directive.is_hero,
            model_profile=model_profile,
            workflow_profile=profile,
            quality_target=target.value,
            expected_vram_mb=vram,
            estimated_time_seconds=seconds,
            expected_qa_score=qa,
            expected_success_probability=probability,
            expected_retry_count=expected_retry_count(qa, spec.reliability),
        )


def replan_for_model(plan: SceneModelPlan, model_key: str) -> SceneModelPlan:
    """Recompile a plan for a different image model (deterministic).

    The mission's "same film on another model family" translation: the
    genre (render profile), quality target, and scene identity stay; every
    backend parameter and prediction is recompiled for the new model. This
    is what the render loop uses when the fallback strategy switches
    models after repeated QA failures.
    """
    old = plan.model_profile
    profile = old.render_profile
    target = QualityTarget(old.quality_target)
    spec = REGISTRY.get(model_key)
    steps_multiplier, upscaler, refiner = target_settings(target, model_key)
    raw_steps = int(spec.steps_range[1] * steps_multiplier)
    steps = min(max(raw_steps, spec.steps_range[0]), 80)

    resolution = _choose_resolution(spec, None)
    cfg = _cfg_for(model_key, profile)
    sampler = select_sampler(model_key, profile)
    scheduler = select_scheduler(model_key, sampler)
    vae = select_vae(model_key)
    loras = select_loras(model_key, profile)
    controlnet = select_controlnet(model_key, plan.shot_type)
    ip_adapter = select_ip_adapter(model_key, is_hero=plan.is_hero)
    depth = select_depth_strategy(model_key, plan.shot_type)
    segmentation = select_segmentation_strategy(model_key)

    report = check_model(
        model_key,
        sampler=sampler,
        scheduler=scheduler,
        vae=vae,
        resolution=resolution,
        aspect_ratio=backend_params(model_key).aspect_ratio,
        controlnet=controlnet,
        ip_adapter=ip_adapter,
        depth=depth,
        segmentation=segmentation,
        upscaler=upscaler,
        refiner=refiner,
    )
    assert report.compatible, f"{model_key}: {report.violations}"

    qa = expected_qa_score(model_key, plan.shot_type)
    probability = expected_success_probability(qa, spec.reliability)
    vram = expected_vram_mb(model_key, resolution)
    seconds = estimated_time_seconds(model_key, steps, resolution)

    model_profile = ModelProfile(
        image_model=model_key,
        video_model=old.video_model,
        animation_backend=default_animation_backend(old.video_model),
        vae=vae,
        sampler=sampler,
        scheduler=scheduler,
        cfg=cfg,
        steps=steps,
        resolution=resolution,
        aspect_ratio=backend_params(model_key).aspect_ratio,
        render_profile=profile,
        loras=loras,
        controlnet=controlnet,
        ip_adapter=ip_adapter,
        depth_strategy=depth,
        segmentation_strategy=segmentation,
        upscaler=upscaler,
        refiner=refiner,
        quality_target=old.quality_target,
        negative_tokens=old.negative_tokens,
        rationale=f"{old.rationale}; fallback recompile for {model_key}",
    )
    return SceneModelPlan(
        scene_index=plan.scene_index,
        scene_id=plan.scene_id,
        shot_type=plan.shot_type,
        is_hero=plan.is_hero,
        model_profile=model_profile,
        workflow_profile=profile,
        quality_target=old.quality_target,
        expected_vram_mb=vram,
        estimated_time_seconds=seconds,
        expected_qa_score=qa,
        expected_success_probability=probability,
        expected_retry_count=expected_retry_count(qa, spec.reliability),
    )


def _area_of(resolution: str) -> int:
    width, height = (int(part) for part in resolution.lower().split("x"))
    return width * height


def _choose_resolution(spec: ModelSpec, vram_budget_mb: int | None) -> str:
    """The model's default resolution, shrunk to fit a VRAM budget."""
    default = default_resolution(spec.key)
    if vram_budget_mb is None or expected_vram_mb(spec.key, default) <= vram_budget_mb:
        return default
    for resolution in sorted(spec.supported_resolutions, key=_area_of):
        if expected_vram_mb(spec.key, resolution) <= vram_budget_mb:
            return resolution
    return min(spec.supported_resolutions, key=_area_of)


def _cfg_for(model_key: str, profile: RenderProfileKey) -> float:
    """CFG: the render profile owns the SDXL family value; the backend
    rules own every other family's default."""
    if REGISTRY.get(model_key).family == "sdxl":
        return profile_for(profile).cfg
    return default_cfg(model_key)
