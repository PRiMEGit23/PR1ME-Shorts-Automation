"""The Asset Engine's ingestion collector (Phase 12, worked examples).

The collector turns one real ``FilmRun`` (Phase 11's production-stack
drive) into indexed assets - images, QA reports, optimization histories,
workflow JSONs, prompt packs, camera paths, transitions, and the
visualization artifacts (cross-sections, diagrams, animations) the shots
call for. Every fingerprint comes from the artifact itself (image hash,
canonical JSON, prompt bytes), so identical artifacts always index
identically - no timestamps, no randomness.
"""

from __future__ import annotations

import json
from typing import Any

from knowledge.asset_engine import AssetEngine, AssetType, create_fingerprint
from knowledge.learning_engine.examples._collector import SOURCE_ROWS, FilmRun
from knowledge.visual_intelligence.storyboard import EngineeringVisualizationType, StoryboardScene
from runtime.models import RenderSessionResult

#: Visualization types that produce dedicated, indexable artifacts.
_CROSS_SECTION_TYPES = {EngineeringVisualizationType.CROSS_SECTION}

#: Visual methods (from the educational plan) that produce artifacts.
_DIAGRAM_METHODS = frozenset({"diagram", "schematic", "exploded view", "infographic"})
_ANIMATION_METHODS = frozenset({"animation", "assembly sequence", "timeline"})


def ingest_run(
    engine: AssetEngine, run: FilmRun, *, run_index: int
) -> dict[str, tuple[str, ...]]:
    """Index every artifact of one film run; returns scene -> asset ids."""
    row = SOURCE_ROWS[_key_from_run_id(run.run_id)]
    keywords = json.loads(row["keywords"])
    visual_methods = {
        step.visual_method.value
        for step in run.plan.knowledge_flow
        if step.visual_method is not None
    }
    engineering_category = run.engineering_domain.value
    educational_category = row["category"]
    per_scene: dict[str, tuple[str, ...]] = {}
    for scene in run.storyboard.scenes:
        result = run.sessions[scene.scene_id]
        if result.winner is None:
            continue
        per_scene[scene.scene_id] = _ingest_scene(
            engine,
            run=run,
            row_keywords=keywords,
            scene=scene,
            result=result,
            engineering_category=engineering_category,
            educational_category=educational_category,
            visual_methods=visual_methods,
        )
    return per_scene


def ingest_films(
    engine: AssetEngine, films: tuple[FilmRun, ...]
) -> dict[str, dict[str, tuple[str, ...]]]:
    """Index every artifact of several film runs (deterministic order)."""
    indexed: dict[str, dict[str, tuple[str, ...]]] = {}
    for run_index, run in enumerate(films):
        indexed[run.run_id] = ingest_run(engine, run, run_index=run_index)
    return indexed


def _ingest_scene(
    engine: AssetEngine,
    *,
    run: FilmRun,
    row_keywords: list[str],
    scene: StoryboardScene,
    result: RenderSessionResult,
    engineering_category: str,
    educational_category: str,
    visual_methods: set[str],
) -> tuple[str, ...]:
    """Index one scene's artifacts; returns the registered asset ids."""
    winner = result.winner
    if winner is None:
        return ()
    qa = winner.qa_report.overall_score if winner.qa_report else 0.0
    materials = tuple(sorted(_scene_materials(scene)))
    visualizations = {
        visualization.type for visualization in scene.intent.engineering_visualizations
    }
    camera = _camera_label(scene)
    lighting = _lighting_label(scene)
    model = winner.image_model or ""
    workflow_version = winner.workflow_profile.value
    retention = run.directives[scene.scene_id].retention_score
    optimization_count = sum(
        len(attempt.optimization_report.optimization_actions)
        for attempt in result.attempts
        if attempt.optimization_report is not None
    )
    semantic_tags = tuple(
        sorted(set(row_keywords) | set(materials) | {engineering_category})
    )
    base: dict[str, Any] = dict(
        source_topic=run.plan.topic,
        educational_category=educational_category,
        engineering_category=engineering_category,
        objects=tuple(sorted(set(row_keywords))),
        materials=materials,
        model_used=model,
        workflow_version=workflow_version,
        retention_prediction=retention,
        optimization_count=optimization_count,
        run_id=run.run_id,
        scene_id=scene.scene_id,
    )
    asset_ids: list[str] = []

    image = engine.register(
        asset_type=AssetType.IMAGE,
        fingerprint=winner.image_sha256,
        quality_score=qa,
        camera=camera,
        lighting=lighting,
        visual_tags=tuple(
            sorted(
                {visualization.value for visualization in visualizations}
                | {run.modality.value}
            )
        ),
        semantic_tags=semantic_tags,
        **base,
    )
    asset_ids.append(image.asset_id)

    if winner.qa_report is not None:
        qa_report = engine.register(
            asset_type=AssetType.QA_REPORT,
            fingerprint=create_fingerprint(winner.qa_report.model_dump_json()),
            quality_score=qa,
            semantic_tags=semantic_tags,
            **base,
        )
        asset_ids.append(qa_report.asset_id)
        engine.add_dependency(
            dependent=image.asset_id,
            dependency=qa_report.asset_id,
            kind="validates",
            reason="winner QA report",
        )
    if winner.optimization_report is not None:
        history = engine.register(
            asset_type=AssetType.OPTIMIZATION_HISTORY,
            fingerprint=create_fingerprint(winner.optimization_report.model_dump_json()),
            quality_score=qa,
            semantic_tags=semantic_tags,
            **base,
        )
        asset_ids.append(history.asset_id)
        engine.add_dependency(
            dependent=image.asset_id,
            dependency=history.asset_id,
            kind="optimizes",
            reason="winner optimization history",
        )

    workflow = engine.register(
        asset_type=AssetType.WORKFLOW_JSON,
        fingerprint=create_fingerprint(json.dumps(winner.workflow, sort_keys=True)),
        quality_score=qa,
        camera=camera,
        lighting=lighting,
        semantic_tags=semantic_tags,
        **base,
    )
    asset_ids.append(workflow.asset_id)
    engine.add_dependency(
        dependent=image.asset_id,
        dependency=workflow.asset_id,
        kind="uses",
        reason="winner workflow",
    )

    prompt_pack = engine.register(
        asset_type=AssetType.PROMPT_PACK,
        fingerprint=create_fingerprint(f"{winner.prompt}\n{winner.negative_prompt}"),
        quality_score=qa,
        semantic_tags=semantic_tags,
        **base,
    )
    asset_ids.append(prompt_pack.asset_id)
    engine.add_dependency(
        dependent=image.asset_id,
        dependency=prompt_pack.asset_id,
        kind="uses",
        reason="winner prompt",
    )

    camera_path = engine.register(
        asset_type=AssetType.CAMERA_PATH,
        fingerprint=create_fingerprint(camera),
        quality_score=qa,
        camera=camera,
        lighting=lighting,
        semantic_tags=semantic_tags,
        **base,
    )
    asset_ids.append(camera_path.asset_id)
    engine.add_dependency(
        dependent=image.asset_id,
        dependency=camera_path.asset_id,
        kind="uses",
        reason="scene camera path",
    )

    transition = engine.register(
        asset_type=AssetType.TRANSITION,
        fingerprint=create_fingerprint(f"{run.run_id}/{scene.scene_id}/{scene.transition.type.value}"),
        quality_score=qa,
        semantic_tags=semantic_tags,
        **base,
    )
    asset_ids.append(transition.asset_id)

    if visualizations & _CROSS_SECTION_TYPES:
        cross = engine.register(
            asset_type=AssetType.CROSS_SECTION,
            fingerprint=create_fingerprint(f"{run.run_id}/{scene.scene_id}/cross-section"),
            quality_score=qa,
            semantic_tags=semantic_tags,
            **base,
        )
        asset_ids.append(cross.asset_id)
    if visual_methods & _DIAGRAM_METHODS:
        diagram = engine.register(
            asset_type=AssetType.ENGINEERING_DIAGRAM,
            fingerprint=create_fingerprint(f"{run.run_id}/{scene.scene_id}/diagram"),
            quality_score=qa,
            semantic_tags=semantic_tags,
            **base,
        )
        asset_ids.append(diagram.asset_id)
    if visual_methods & _ANIMATION_METHODS:
        animation = engine.register(
            asset_type=AssetType.ANIMATION,
            fingerprint=create_fingerprint(f"{run.run_id}/{scene.scene_id}/animation"),
            quality_score=qa,
            semantic_tags=semantic_tags,
            **base,
        )
        asset_ids.append(animation.asset_id)

    return tuple(asset_ids)


def _key_from_run_id(run_id: str) -> str:
    """The film key out of a run id like ``run-gyroid-42``."""
    return run_id.split("-")[1]


def _scene_materials(scene: StoryboardScene) -> list[str]:
    materials = list(scene.primary_subject.materials)
    for subject in scene.secondary_subjects:
        materials.extend(subject.materials)
    return [material for material in materials if material]


def _camera_label(scene: StoryboardScene) -> str:
    camera = scene.camera
    return f"{camera.angle.value} {camera.distance.value} {camera.lens.value}"


def _lighting_label(scene: StoryboardScene) -> str:
    lighting = scene.lighting
    return f"{lighting.direction.value} {lighting.style.value}"
