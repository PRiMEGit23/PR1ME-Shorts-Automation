"""The AI Director: EducationalPlan -> DirectorOutput, deterministically.

The director is a decision engine, not a model: it consumes the
EducationalPlan (the teaching intent) and emits the complete creative
brief - arc structure, per-scene budgets, cinematic plans, structural
roles, and predicted attention / retention - before any prompt is
generated. Every decision is a pure function of the plan; running it
twice yields identical output.

Module responsibilities (each decision lives in exactly one module):

- scene_prioritizer : arc count (merge/split), goals, shots, importance
- visual_budget     : visual/animation/motion budgets, diagram priority,
                      engineering emphasis and overlays
- emotion_curve     : emotional intensity per scene and the arc shape
- reveal_planner    : when each scene's information is revealed
- pacing_planner    : information density and the film's pacing profile
- transition_planner: the cut grammar between scenes
- hero_scene_selector : the showpiece scene
- thumbnail_strategy  : the scene that stops the scroll
- comparison_strategy : comparison emphasis per scene
- attention_model   : predicted attention and retention
"""

from __future__ import annotations

from knowledge.ai_director.attention_model import AttentionModel
from knowledge.ai_director.comparison_strategy import ComparisonStrategy
from knowledge.ai_director.director_models import (
    AI_DIRECTOR_VERSION,
    DirectorOutput,
    SceneDirective,
)
from knowledge.ai_director.director_rules import (
    camera_for,
    clamp,
    composition_for,
    lighting_for,
    mood_for,
    motion_for,
)
from knowledge.ai_director.emotion_curve import EmotionCurve
from knowledge.ai_director.hero_scene_selector import HeroSceneSelector
from knowledge.ai_director.pacing_planner import PacingPlanner
from knowledge.ai_director.reveal_planner import RevealPlanner
from knowledge.ai_director.scene_prioritizer import SceneBlueprint, ScenePrioritizer
from knowledge.ai_director.thumbnail_strategy import ThumbnailStrategy
from knowledge.ai_director.transition_planner import TransitionPlanner
from knowledge.ai_director.visual_budget import VisualBudgetAllocator
from knowledge.educational_director.educational_models import EducationalPlan


class AIDirector:
    """The deterministic AI Director for one educational plan."""

    version = AI_DIRECTOR_VERSION

    def __init__(self) -> None:
        self._prioritizer = ScenePrioritizer()
        self._budgets = VisualBudgetAllocator()
        self._emotions = EmotionCurve()
        self._reveals = RevealPlanner()
        self._pacing = PacingPlanner()
        self._transitions = TransitionPlanner()
        self._thumbnails = ThumbnailStrategy()
        self._heroes = HeroSceneSelector()
        self._comparisons = ComparisonStrategy()
        self._attention = AttentionModel()

    def direct(self, plan: EducationalPlan) -> DirectorOutput:
        """Direct one plan into a full creative brief (pure and deterministic)."""
        blueprints, arc_rationale = self._prioritizer.plan(plan)
        last = max(b.index for b in blueprints)

        importances = {b.index: b.base_importance for b in blueprints}
        comparison = self._comparisons.plan(
            blueprints, plan, merged_arc=len(blueprints) == 4
        )
        budgets = self._budgets.allocate(blueprints, plan)
        emotions = self._emotions.curve(blueprints, plan)
        hero_index = self._heroes.pick(blueprints, importances, emotions, plan)
        importances[hero_index] = 5
        thumbnail_index, priorities = self._thumbnails.pick(
            blueprints, importances, emotions, budgets, hero_index
        )
        reveal_orders, reveal_label = self._reveals.plan(blueprints, plan)
        pacing = self._pacing.plan(blueprints, plan, comparison)
        pacing_profile = self._pacing.profile(pacing)
        emotion_arc = self._emotions.label(emotions)
        transitions = self._transitions.plan(emotions, comparison, pacing)
        prediction = self._attention.predict(
            importances=importances,
            emotions=emotions,
            pacing=pacing,
            reveal_orders=reveal_orders,
            budgets=budgets,
            hero_index=hero_index,
            thumbnail_index=thumbnail_index,
        )

        directives: list[SceneDirective] = []
        for blueprint in blueprints:
            index = blueprint.index
            budget = budgets[index]
            camera_intensity = clamp(
                round(3 + importances[index] * 0.8 + (1 if emotions[index] >= 8 else 0))
            )
            lighting_priority = clamp(
                round(2 + importances[index] + (1 if emotions[index] >= 8 else 0))
            )
            is_hero = index == hero_index
            is_thumbnail = index == thumbnail_index
            is_recap = index == last

            roles = []
            if is_hero:
                roles.append("hero")
            if is_thumbnail:
                roles.append("thumbnail")
            if is_recap:
                roles.append("recap")

            directives.append(
                SceneDirective(
                    scene_index=index,
                    scene_id=f"S{index}",
                    visual_goal=blueprint.goal,
                    shot_type=blueprint.shot_type,
                    engineering_visualizations=list(budget.visualizations),
                    importance=importances[index],
                    visual_budget=budget.visual_budget,
                    animation_budget=budget.animation_budget,
                    motion_budget=budget.motion_budget,
                    camera_intensity=camera_intensity,
                    lighting_priority=lighting_priority,
                    diagram_priority=budget.diagram_priority,
                    engineering_emphasis=budget.engineering_emphasis,
                    comparison_emphasis=comparison[index],
                    emotion=emotions[index],
                    pacing=pacing[index],
                    retention_score=prediction.retention_scores[index],
                    expected_attention=prediction.expected_attention[index],
                    reveal_order=reveal_orders[index],
                    camera=camera_for(camera_intensity),
                    lighting=lighting_for(lighting_priority),
                    composition=composition_for(
                        camera_intensity, is_thumbnail=is_thumbnail
                    ),
                    motion=motion_for(
                        budget.motion_budget,
                        diagram_priority=budget.diagram_priority,
                        goal=blueprint.goal,
                    ),
                    mood=mood_for(
                        emotions[index],
                        comparison[index],
                        budget.diagram_priority,
                    ),
                    transition=transitions[index],
                    thumbnail_priority=priorities[index],
                    is_hero=is_hero,
                    is_thumbnail=is_thumbnail,
                    is_recap=is_recap,
                    rationale=self._rationale(
                        blueprint,
                        importances[index],
                        roles,
                        arc_rationale,
                    ),
                )
            )

        hero_id = f"S{hero_index}"
        thumbnail_id = f"S{thumbnail_index}"
        recap_id = f"S{last}"
        summary = (
            f"{len(directives)}-scene {emotion_arc} arc ({arc_rationale.split(':')[0]}); "
            f"hero {hero_id}, thumbnail {thumbnail_id}, recap {recap_id}; "
            f"{reveal_label}, {pacing_profile} pacing; predicted retention "
            f"{prediction.predicted_retention}%, attention {prediction.predicted_attention}%"
        )
        return DirectorOutput(
            version=self.version,
            topic=plan.topic,
            teaching_strategy=plan.teaching_strategy,
            scene_count=len(directives),
            scene_directives=directives,
            hero_scene_id=hero_id,
            thumbnail_scene_id=thumbnail_id,
            recap_scene_id=recap_id,
            emotion_arc=emotion_arc,
            pacing_profile=pacing_profile,
            reveal_plan=reveal_label,
            predicted_retention=prediction.predicted_retention,
            predicted_attention=prediction.predicted_attention,
            summary=summary,
        )

    @staticmethod
    def _rationale(
        blueprint: SceneBlueprint,
        importance: int,
        roles: list[str],
        arc_rationale: str,
    ) -> str:
        """One deterministic rationale line per scene (no prose generation)."""
        role_text = f", roles: {', '.join(roles)}" if roles else ""
        notes = ", " + ", ".join(blueprint.notes) if blueprint.notes else ""
        return (
            f"{blueprint.goal.value} scene ({blueprint.shot_type.value}), "
            f"importance {importance}, "
            f"reason: {arc_rationale}{role_text}{notes}"
        )
