"""Shot director: turns a VisualArchitecture spec into a directed storyboard.

The director is the orchestrator of the Visual Intelligence Engine: it
classifies each scene's VisualGoal, dedupes consecutive explanatory goals into
highlight-difference reveals, selects shot types, plans camera/lighting/
composition/transitions, selects engineering visualizations, and hands the
scenes to the ThumbnailDirector for priority ranking. Everything is
deterministic and never touches prompts.
"""

from __future__ import annotations

from collections.abc import Sequence

from knowledge.visual_architecture import EngineeringDomain, VisualArchitecture
from knowledge.visual_intelligence.camera_planner import plan_camera
from knowledge.visual_intelligence.composition_planner import plan_composition
from knowledge.visual_intelligence.engineering_visuals import select_engineering_visualizations
from knowledge.visual_intelligence.lighting_planner import plan_lighting
from knowledge.visual_intelligence.shot_selector import select_shot_type
from knowledge.visual_intelligence.storyboard import (
    SceneIntent,
    StoryboardScene,
    ThumbnailPriority,
    VisualStoryboard,
)
from knowledge.visual_intelligence.thumbnail_director import rank_thumbnail_candidates
from knowledge.visual_intelligence.transition_planner import plan_transitions
from knowledge.visual_intelligence.visual_goal import VisualGoal, classify_visual_goal

_EXPLAIN_GOALS = frozenset(
    goal
    for goal in VisualGoal
    if goal.value.startswith("explain_") or goal is VisualGoal.REVEAL_INTERNAL_GEOMETRY
)


class ShotDirector:
    """Stateless orchestrator; safe to share and to call many times."""

    def classify_goals(
        self,
        architecture: VisualArchitecture,
        *,
        keywords: Sequence[str] = (),
        summary: str = "",
    ) -> list[VisualGoal]:
        """Classify every scene's goal, then break goal monotony."""
        goals = [
            classify_visual_goal(
                scene,
                scene_index=index,
                scene_count=len(architecture.scenes),
                keywords=keywords,
                summary=summary,
            )
            for index, scene in enumerate(architecture.scenes, start=1)
        ]
        return self._dedupe_goals(goals)

    def _dedupe_goals(self, goals: Sequence[VisualGoal]) -> list[VisualGoal]:
        """A repeated explanatory goal becomes a highlight-difference reveal.

        Two consecutive scenes teaching the same thing would feel redundant;
        the second is remapped to HIGHLIGHT_DIFFERENCE so the video compares
        instead of repeating. Non-explanatory repeats (introduce, summarize)
        are left alone.
        """
        deduped: list[VisualGoal] = []
        for goal in goals:
            if (
                deduped
                and goal == deduped[-1]
                and goal in _EXPLAIN_GOALS
            ):
                deduped.append(VisualGoal.HIGHLIGHT_DIFFERENCE)
            else:
                deduped.append(goal)
        return deduped

    def direct(
        self,
        architecture: VisualArchitecture,
        *,
        topic: str,
        keywords: Sequence[str] = (),
        summary: str = "",
    ) -> VisualStoryboard:
        """Produce the full VisualStoryboard for one VisualArchitecture."""
        goals = self.classify_goals(architecture, keywords=keywords, summary=summary)
        domain: EngineeringDomain = architecture.engineering_domain

        shots = [
            select_shot_type(goal, scene)
            for goal, scene in zip(goals, architecture.scenes, strict=True)
        ]
        transitions = plan_transitions(architecture.scenes, goals, shots)

        scenes: list[StoryboardScene] = []
        for index, (scene, goal, shot, transition) in enumerate(
            zip(architecture.scenes, goals, shots, transitions, strict=True), start=1
        ):
            camera = plan_camera(goal, shot, scene)
            lighting = plan_lighting(shot, scene)
            composition = plan_composition(shot, scene)
            visualizations = select_engineering_visualizations(
                goal, shot, domain=domain
            )
            scenes.append(
                StoryboardScene(
                    scene_id=scene.scene_id,
                    scene_index=index,
                    intent=SceneIntent(
                        goal=goal,
                        shot_type=shot,
                        engineering_visualizations=visualizations,
                        rationale=(
                            f"goal '{goal.value}' realized as {shot.value}"
                        ),
                    ),
                    camera=camera,
                    composition=composition,
                    lighting=lighting,
                    depth=scene.depth,
                    mood=scene.mood,
                    motion=scene.motion,
                    primary_subject=scene.primary_subject,
                    secondary_subjects=scene.secondary_subjects,
                    environment=scene.environment or scene.depth.background,
                    color_palette=scene.color_palette,
                    scale_reference=scene.scale_reference,
                    objects_to_avoid=scene.objects_to_avoid,
                    negative_elements=scene.negative_elements,
                    consistency_tags=scene.consistency_tags,
                    branding_tags=scene.branding_tags,
                    transition=transition,
                    thumbnail_priority=ThumbnailPriority(  # placeholder, filled below
                        score=0,
                        rank=len(architecture.scenes),
                        rationale="pending thumbnail ranking",
                    ),
                    scene_importance=scene.scene_importance,
                    thumbnail_candidate=scene.thumbnail_candidate,
                )
            )

        priorities = rank_thumbnail_candidates(scenes)
        scenes = [
            scene.model_copy(update={"thumbnail_priority": priorities[scene.scene_id]})
            for scene in scenes
        ]
        winner = next(
            scene for scene in scenes if scene.thumbnail_priority.rank == 1
        )

        return VisualStoryboard(
            version="1.0.0",
            world_id=architecture.world_id,
            engineering_domain=domain,
            modality=architecture.modality,
            topic=topic,
            scenes=scenes,
            thumbnail_scene_id=winner.scene_id,
        )