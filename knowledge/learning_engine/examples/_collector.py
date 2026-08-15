"""The Learning Engine's data collector (Phase 11, worked examples).

The collector drives the *production stack* directly - the same components
the fifteen-stage pipeline binds:

    EducationalDirector -> AIDirector -> ModelDirector ->
    StoryboardBuilder -> RenderLoop (SimulatedRenderer, Model Director
    directive active)

and records every scene outcome as a ``SceneObservation``; one film run
becomes one ``ProjectRecord``. Everything here is deterministic, and the
recorded observations are exactly what the pipeline produced for that
row and seed - no fabricated numbers, no timestamps.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge.ai_director import AIDirector
from knowledge.ai_director.director_models import SceneDirective
from knowledge.educational_director import EducationalDirector
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.educational_director.examples.gyroid import GYROID_ROW
from knowledge.educational_director.examples.injection_molding import INJECTION_ROW
from knowledge.educational_director.examples.planetary_gear import PLANETARY_ROW
from knowledge.learning_engine.learning_models import (
    PipelineHistory,
    ProjectRecord,
    SceneObservation,
)
from knowledge.model_director import ModelDirector
from knowledge.model_director.model_profiles import ModelOutput, SceneModelPlan
from knowledge.visual_architecture import EngineeringDomain, Modality
from knowledge.visual_intelligence.storyboard import StoryboardScene, VisualStoryboard
from runtime.models import AttemptStatus, RenderSessionResult, SessionConfig
from runtime.render_loop import RenderLoop
from runtime.renderer import SimulatedRenderer
from runtime.storyboard_builder import StoryboardBuilder

#: The three worked-example films (the canonical engineering shorts).
SOURCE_ROWS: dict[str, dict[str, str]] = {
    "gyroid": GYROID_ROW,
    "planetary_gear": PLANETARY_ROW,
    "injection_molding": INJECTION_ROW,
}


@dataclass(frozen=True)
class FilmRun:
    """One real run of one film, with every artifact a studio can index.

    ``record`` is the learnable ProjectRecord (Phase 11); the sessions,
    storyboard, model output, plan, and directives expose the underlying
    artifacts (winner images, workflows, prompts, QA reports) for the
    Asset Engine's ingestion (Phase 12).
    """

    run_id: str
    record: ProjectRecord
    sessions: dict[str, RenderSessionResult]
    storyboard: VisualStoryboard
    model_output: ModelOutput
    plan: EducationalPlan
    directives: dict[str, SceneDirective]
    engineering_domain: EngineeringDomain
    modality: Modality


def collect_film_run(
    *,
    key: str,
    seed: int,
    run_index: int,
    preferred_model: str = "gpt-image",
    max_attempts: int = 3,
    engineering_domain: EngineeringDomain = EngineeringDomain.FDM,
    modality: Modality = Modality.PHOTOREAL,
) -> FilmRun:
    """One real run of one film; returns the record and every artifact."""
    if key not in SOURCE_ROWS:
        raise ValueError(f"unknown film {key!r}; known: {sorted(SOURCE_ROWS)}")
    row = SOURCE_ROWS[key]
    run_id = f"run-{key}-{seed:02d}"

    ed = EducationalDirector().direct_from_csv(row)
    ad = AIDirector().direct(ed)
    md = ModelDirector().direct(ad)
    storyboard = StoryboardBuilder().build(
        ed, engineering_domain=engineering_domain, modality=modality, director=ad
    )
    directives = {d.scene_id: d for d in ad.scene_directives}

    loop = RenderLoop(renderer=SimulatedRenderer())
    observations: list[SceneObservation] = []
    sessions: dict[str, RenderSessionResult] = {}
    total_duration_ms = 0.0
    for index, scene in enumerate(storyboard.scenes):
        scene_seed = seed + index
        result = loop.run(
            plan=ed,
            storyboard=storyboard,
            scene=scene,
            topic=ed.topic,
            seed=scene_seed,
            config=SessionConfig(
                #: The legacy prompt compiler only implements sdxl; the Model
                #: Director directive (below) is what carries the real model.
                model_key="sdxl",
                max_attempts=max_attempts,
                save_artifacts=False,
            ),
            directive=md.plan_for(scene.scene_id),
        )
        sessions[scene.scene_id] = result
        observations.append(
            _observe(run_id, scene, result, ed, directives[scene.scene_id],
                     md.plan_for(scene.scene_id))
        )
        total_duration_ms += _duration_ms(md.plan_for(scene.scene_id))

    record = ProjectRecord(
        run_id=run_id,
        run_index=run_index,
        topic=ed.topic,
        seed=seed,
        status="complete",
        total_duration_ms=round(total_duration_ms, 3),
        scenes=tuple(observations),
    )
    return FilmRun(
        run_id=run_id,
        record=record,
        sessions=sessions,
        storyboard=storyboard,
        model_output=md,
        plan=ed,
        directives=directives,
        engineering_domain=engineering_domain,
        modality=modality,
    )


def collect_film(
    *,
    key: str,
    seed: int,
    run_index: int,
    preferred_model: str = "gpt-image",
    max_attempts: int = 3,
    engineering_domain: EngineeringDomain = EngineeringDomain.FDM,
    modality: Modality = Modality.PHOTOREAL,
) -> ProjectRecord:
    """One real run of one film, recorded as a learnable ProjectRecord."""
    return collect_film_run(
        key=key,
        seed=seed,
        run_index=run_index,
        preferred_model=preferred_model,
        max_attempts=max_attempts,
        engineering_domain=engineering_domain,
        modality=modality,
    ).record


def collect_history(
    seeds: tuple[int, ...] = (42, 43, 44),
    *,
    preferred_model: str = "gpt-image",
    max_attempts: int = 3,
) -> PipelineHistory:
    """Every worked-example film at every seed, as one history."""
    projects: list[ProjectRecord] = []
    run_index = 0
    for key in sorted(SOURCE_ROWS):
        for seed in seeds:
            projects.append(
                collect_film(
                    key=key,
                    seed=seed,
                    run_index=run_index,
                    preferred_model=preferred_model,
                    max_attempts=max_attempts,
                )
            )
            run_index += 1
    return PipelineHistory(projects=tuple(projects))


def _observe(
    run_id: str,
    scene: StoryboardScene,
    result: RenderSessionResult,
    plan: EducationalPlan,
    directive: SceneDirective,
    scene_plan: SceneModelPlan,
) -> SceneObservation:
    """The learning record of one completed scene."""
    profile = scene_plan.model_profile
    winner = result.winner
    attempts = result.attempts
    prompt_mutations = sum(
        len(a.optimization_report.prompt_mutations)
        for a in attempts
        if a.optimization_report is not None
    )
    optimization_actions = sum(
        len(a.optimization_report.optimization_actions)
        for a in attempts
        if a.optimization_report is not None
    )
    visualizations = scene.intent.engineering_visualizations
    return SceneObservation(
        run_id=run_id,
        scene_id=scene.scene_id,
        scene_index=scene.scene_index,
        seed=result.seed,
        topic=plan.topic,
        cognitive_step=_cognitive_step(plan, scene.scene_index),
        shot_type=scene.intent.shot_type,
        camera_distance=scene.camera.distance,
        camera_angle=scene.camera.angle,
        lens=scene.camera.lens,
        framing=scene.camera.framing,
        light_direction=scene.lighting.direction,
        lighting_style=scene.lighting.style,
        transition_type=scene.transition.type,
        visualization_type=(
            visualizations[0].type if visualizations else None
        ),
        image_model=profile.image_model,
        video_model=profile.video_model,
        render_profile=profile.render_profile.value,
        quality_target=scene_plan.quality_target,
        predicted_qa=scene_plan.expected_qa_score,
        qa_score=(
            winner.qa_report.overall_score if winner and winner.qa_report else 0.0
        ),
        educational_score=(
            winner.qa_report.educational_score if winner and winner.qa_report else 0.0
        ),
        retention_prediction=directive.retention_score,
        thumbnail_priority=scene.thumbnail_priority.score,
        attempts=result.attempts_used,
        failed_attempts=(
            max(0, result.attempts_used - 1) if result.passed else result.attempts_used
        ),
        model_switches=sum(
            1 for a in attempts if a.status is AttemptStatus.MODEL_SWITCHED
        ),
        prompt_mutations=prompt_mutations,
        optimization_actions=optimization_actions,
        render_duration_ms=_duration_ms(scene_plan),
        vram_mb=scene_plan.expected_vram_mb,
        negative_tokens=tuple(profile.negative_tokens),
        passed=result.passed,
    )


def _cognitive_step(plan: EducationalPlan, scene_index: int) -> str:
    """The plan's cognitive concept for this scene position, if one lines up."""
    steps = [step for step in plan.knowledge_flow if step.concept]
    if steps and len(steps) >= scene_index:
        return steps[scene_index - 1].concept[:60]
    return ""


def _duration_ms(scene_plan: SceneModelPlan) -> float:
    """The planned render duration (the simulator has no wall-clock time)."""
    return round(scene_plan.estimated_time_seconds * 1000.0, 1)
