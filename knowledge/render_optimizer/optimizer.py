"""Render optimizer: translate a QA failure into a concrete fix plan.

The optimizer is the close of the Phase 1-5 loop: Image QA rejected an
image, so this stage prescribes exactly how to change the storyboard scene,
the compiled prompt, and the render workflow, plus a deterministic
projection of the scores after the fixes.

Rule of determinism: identical (report, scene, prompt) inputs always produce
identical plans. No randomness, no LLM, no re-rendering. The plan is
instructions for a future stage (or a human) to execute.
"""

from __future__ import annotations

from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.image_qa.qa_models import (
    FAIL_FLOOR,
    PASS_THRESHOLD,
    ImageQualityReport,
    IssueSeverity,
    QACheck,
)
from knowledge.render_optimizer.optimization_models import (
    MAX_GAIN_PER_ROUND,
    CameraChange,
    CompositionChange,
    ExpectedScoreImprovement,
    LightingChange,
    MutationKind,
    OptimizationAction,
    OptimizationActionKind,
    OptimizedRenderPlan,
    PromptMutation,
    VisualizationChange,
    WorkflowChange,
)
from knowledge.render_optimizer.optimization_rules import (
    OPTIMIZATION_FLOOR,
    OPTIMIZATION_RULES,
    SCORE_FIELDS,
    rule_for,
)
from knowledge.render_optimizer.prompt_mutator import (
    camera_mutations,
    composition_mutations,
    lighting_mutations,
    negative_mutations,
    visualization_mutations,
)
from knowledge.render_optimizer.workflow_selector import select_workflow_profile
from knowledge.visual_architecture import (
    CameraDistance,
    CompositionRule,
    Framing,
    Lens,
    LightDirection,
    LightingStyle,
)
from knowledge.visual_intelligence.storyboard import (
    EngineeringVisualizationType,
    StoryboardScene,
)

#: Score weights, mirrored from knowledge/image_qa/image_critic._WEIGHTS.
#: The test suite asserts this stays in lockstep with the QA engine.
SCORE_WEIGHTS: dict[str, float] = {
    "engineering": 0.20,
    "educational": 0.20,
    "composition": 0.15,
    "subject_hierarchy": 0.10,
    "visual_clarity": 0.10,
    "thumbnail": 0.10,
    "consistency": 0.15,
}

_FIELD_TO_BUCKET = {
    "engineering_score": "engineering",
    "educational_score": "educational",
    "composition_score": "composition",
    "subject_hierarchy_score": "subject_hierarchy",
    "visual_clarity_score": "visual_clarity",
    "thumbnail_score": "thumbnail",
    "consistency_score": "consistency",
}

_VISUALIZATION_TOKENS: dict[EngineeringVisualizationType, list[str]] = {
    EngineeringVisualizationType.CROSS_SECTION: ["cross section view", "interior details"],
    EngineeringVisualizationType.EXPLODED_ASSEMBLY: ["exploded view", "separated parts"],
    EngineeringVisualizationType.TRANSPARENT_HOUSING: ["transparent shell", "internal parts"],
    EngineeringVisualizationType.WIREFRAME_OVERLAY: ["wireframe overlay", "edge lines"],
    EngineeringVisualizationType.STRESS_DIRECTION: ["stress heat map", "force arrows"],
    EngineeringVisualizationType.HEAT_MAP: ["heat map", "temperature gradient"],
    EngineeringVisualizationType.FORCE_ARROWS: ["force arrows", "load direction"],
    EngineeringVisualizationType.TOLERANCE_OVERLAY: ["tolerance callouts", "dimension marks"],
    EngineeringVisualizationType.DIMENSION_OVERLAY: ["dimension lines", "measurements"],
    EngineeringVisualizationType.MATERIAL_CALLOUTS: ["material callouts", "labels"],
    EngineeringVisualizationType.MANUFACTURING_STEPS: ["manufacturing steps", "process sequence"],
    EngineeringVisualizationType.LAYER_PRINT: ["layer-by-layer print", "print layers"],
}


class RenderOptimizer:
    """One optimization pass over a QA report (or a simulated score state)."""

    def optimize(
        self,
        report: ImageQualityReport,
        *,
        scene: StoryboardScene | None = None,
        compiled_prompt: CompiledPrompt | None = None,
    ) -> OptimizedRenderPlan:
        """Build the full fix plan for one rejected image."""
        scores = {field: getattr(report, field) for field in SCORE_FIELDS}
        actions = self._collect_actions(scores, report.issues)
        return self._assemble(
            report.topic,
            report.scene_id,
            scores,
            actions,
            scene=scene,
            compiled_prompt=compiled_prompt,
        )

    def _collect_actions(
        self,
        scores: dict[str, float],
        issues: list,
        applied: list[tuple[str, str]] | None = None,
    ) -> list[OptimizationAction]:
        """Fire rules from issues and from scores still below the floor.

        ``applied`` carries (check.value, instruction) keys already granted in
        earlier rounds; those actions are never emitted twice.
        """
        from knowledge.image_qa.qa_models import QAIssue

        fired: list[tuple[str, str]] = list(applied or [])
        actions: list[OptimizationAction] = []

        def add(check: QACheck, template, severity: IssueSeverity, why: str) -> None:
            key = (check.value, template.instruction)
            if key in fired:
                return
            fired.append(key)
            actions.append(
                OptimizationAction(
                    kind=template.kind,
                    check=check,
                    instruction=template.instruction,
                    expected_gain=template.gain,
                    target_score=template.target_score,
                    rationale=why,
                )
            )

        for issue in issues:
            if not isinstance(issue, QAIssue):
                continue
            rule = rule_for(issue.check)
            for template in rule.actions:
                if issue.severity is IssueSeverity.CRITICAL or template.severity <= issue.severity:
                    add(issue.check, template, issue.severity, issue.message)

        for field in SCORE_FIELDS:
            if scores[field] >= OPTIMIZATION_FLOOR:
                continue
            for check, rule in OPTIMIZATION_RULES.items():
                candidates = [
                    t for t in rule.actions if t.target_score == field
                ]
                if not candidates:
                    continue
                template = max(candidates, key=lambda t: (t.gain,))
                add(
                    check,
                    template,
                    IssueSeverity.MINOR,
                    f"{field.replace('_', ' ')} {scores[field]:.1f} is below "
                    f"the optimization floor {OPTIMIZATION_FLOOR:.0f}",
                )
        return actions

    def _assemble(
        self,
        topic: str,
        scene_id: str,
        scores: dict[str, float],
        actions: list[OptimizationAction],
        *,
        scene: StoryboardScene | None,
        compiled_prompt: CompiledPrompt | None,
    ) -> OptimizedRenderPlan:
        camera: list[CameraChange] = []
        lighting: list[LightingChange] = []
        composition: list[CompositionChange] = []
        visualization: list[VisualizationChange] = []
        workflow: list[WorkflowChange] = []
        mutations: list[PromptMutation] = []

        # OptimizedRenderPlan caps optimization_actions at 24; never build a
        # plan the schema cannot carry (a catastrophically failing render can
        # fire every rule at once). Cap before translating so mutations,
        # workflow changes, and projections all describe the same action set.
        actions = list(actions[:24])

        for action in actions:
            self._translate(
                action,
                scene,
                camera,
                lighting,
                composition,
                visualization,
                workflow,
                mutations,
            )

        expected = self._project(scores, actions)
        return OptimizedRenderPlan(
            topic=topic,
            scene_id=scene_id,
            optimization_actions=actions,
            prompt_mutations=mutations,
            workflow_changes=workflow,
            camera_changes=camera,
            lighting_changes=lighting,
            composition_changes=composition,
            visualization_changes=visualization,
            expected_score_improvement=expected,
            rationale=(
                f"{len(actions)} actions to raise {topic!r} {scene_id} "
                f"from {expected.overall - expected.improvement:.1f} to a "
                f"predicted {expected.overall:.1f}"
            ),
        )

    def _translate(
        self,
        action: OptimizationAction,
        scene: StoryboardScene | None,
        camera: list[CameraChange],
        lighting: list[LightingChange],
        composition: list[CompositionChange],
        visualization: list[VisualizationChange],
        workflow: list[WorkflowChange],
        mutations: list[PromptMutation],
    ) -> None:
        """Append the typed changes and prompt mutations one action implies."""
        check = action.check
        if action.kind is OptimizationActionKind.VISUALIZATION:
            viz_type = self._visualization_type_for(check, scene)
            if any(v.type is viz_type for v in visualization):
                return
            viz = VisualizationChange(
                type=viz_type,
                elements=_VISUALIZATION_TOKENS[viz_type],
                prompt_tokens=_VISUALIZATION_TOKENS[viz_type],
                rationale=action.rationale,
            )
            visualization.append(viz)
            mutations.extend(visualization_mutations(viz))
            profile, reason = select_workflow_profile(
                visualization_type=viz_type,
                shot_type=scene.intent.shot_type if scene else None,
            )
            if not any(w.profile is profile for w in workflow):
                workflow.append(
                    WorkflowChange(profile=profile, rationale=f"{reason}: {action.instruction}")
                )
        elif action.kind is OptimizationActionKind.WORKFLOW:
            profile, reason = select_workflow_profile(
                visualization_type=self._visualization_type_for(check, scene),
                shot_type=scene.intent.shot_type if scene else None,
            )
            if not any(w.profile is profile for w in workflow):
                workflow.append(
                    WorkflowChange(profile=profile, rationale=f"{reason}: {action.instruction}")
                )
        elif action.kind is OptimizationActionKind.CAMERA:
            change = self._camera_change_for(check)
            if not change:
                if scene is not None:
                    mutations.append(
                        PromptMutation(
                            kind=MutationKind.APPEND,
                            target_prompt="positive",
                            target="",
                            replacement=(
                                f"{scene.camera.distance.value} shot, "
                                f"{scene.camera.angle.value} angle, "
                                f"{scene.camera.lens.value} lens, "
                                f"{scene.camera.framing.value} framing"
                            ),
                            rationale=action.rationale,
                        )
                    )
                return
            if any(c.model_dump(exclude={"rationale"}) == change for c in camera):
                return
            camera.append(CameraChange(**change, rationale=action.rationale))
            old_values = None
            if scene is not None:
                old_values = {
                    "shot": scene.camera.distance.value,
                    "angle": scene.camera.angle.value,
                    "lens": scene.camera.lens.value,
                    "framing": scene.camera.framing.value,
                }
            mutations.extend(
                camera_mutations(
                    CameraChange(**change, rationale=action.rationale),
                    old_values=old_values,
                )
            )
        elif action.kind is OptimizationActionKind.LIGHTING:
            change = self._lighting_change_for(check)
            if not change:
                if scene is not None:
                    mutations.append(
                        PromptMutation(
                            kind=MutationKind.APPEND,
                            target_prompt="positive",
                            target="",
                            replacement=(
                                f"{scene.lighting.direction.value} lighting, "
                                f"{scene.lighting.style.value} style"
                            ),
                            rationale=action.rationale,
                        )
                    )
                return
            if any(light.model_dump(exclude={"rationale"}) == change for light in lighting):
                return
            lighting.append(LightingChange(**change, rationale=action.rationale))
            old_values = None
            if scene is not None:
                old_values = {
                    "direction": scene.lighting.direction.value,
                    "style": scene.lighting.style.value,
                }
            mutations.extend(
                lighting_mutations(
                    LightingChange(**change, rationale=action.rationale),
                    old_values=old_values,
                )
            )
        elif action.kind is OptimizationActionKind.COMPOSITION:
            change = self._composition_change_for(check)
            if not change:
                return
            if any(c.model_dump(exclude={"rationale"}) == change for c in composition):
                return
            old_rule = None
            if scene is not None and scene.composition is not None:
                old_rule = scene.composition.rule.value
            composition.append(CompositionChange(**change, rationale=action.rationale))
            mutations.extend(
                composition_mutations(
                    CompositionChange(**change, rationale=action.rationale), old_rule
                )
            )
        elif action.kind is OptimizationActionKind.CONSISTENCY:
            mutations.extend(negative_mutations(["inconsistent color", "mixed materials"], rationale=action.rationale))
        elif action.kind is OptimizationActionKind.PROMPT:
            if check is QACheck.VISUAL_CLUTTER:
                mutations.extend(
                    negative_mutations(
                        ["clutter", "background objects", "text"],
                        rationale=action.rationale,
                    )
                )
            mutations.append(
                PromptMutation(
                    kind=MutationKind.APPEND,
                    target_prompt="positive",
                    target="",
                    replacement=action.instruction,
                    rationale=action.rationale,
                )
            )

    @staticmethod
    def _visualization_type_for(
        check: QACheck, scene: StoryboardScene | None
    ) -> EngineeringVisualizationType:
        if check is QACheck.EDUCATIONAL_EFFECTIVENESS:
            if scene and scene.intent.engineering_visualizations:
                return scene.intent.engineering_visualizations[0].type
            return EngineeringVisualizationType.MATERIAL_CALLOUTS
        return EngineeringVisualizationType.CROSS_SECTION

    @staticmethod
    def _camera_change_for(check: QACheck) -> dict:
        if check is QACheck.PRIMARY_SUBJECT_VISIBILITY:
            return {
                "distance": CameraDistance.MACRO,
                "lens": Lens.MACRO_100,
                "framing": Framing.TIGHT,
            }
        if check is QACheck.SUBJECT_HIERARCHY:
            return {"framing": Framing.TIGHT}
        if check is QACheck.COMPOSITION_QUALITY:
            return {"lens": Lens.STANDARD_35, "framing": Framing.SUBJECT_CENTER}
        if check is QACheck.GEOMETRY_CORRECTNESS:
            return {"distance": CameraDistance.MEDIUM}
        return {}

    @staticmethod
    def _lighting_change_for(check: QACheck) -> dict:
        if check is QACheck.THUMBNAIL_STRENGTH:
            return {"direction": LightDirection.KEY, "style": LightingStyle.HARD_KEY}
        if check is QACheck.LIGHTING_SUITABILITY:
            return {"style": LightingStyle.STUDIO}
        return {}

    @staticmethod
    def _composition_change_for(check: QACheck) -> dict:
        if check is QACheck.PRIMARY_SUBJECT_VISIBILITY:
            return {"emphasis": "primary subject dominating the frame"}
        if check is QACheck.SUBJECT_HIERARCHY:
            return {"emphasis": "clear subject hierarchy, dominant primary subject"}
        if check is QACheck.COMPOSITION_QUALITY:
            return {"rule": CompositionRule.RULE_OF_THIRDS}
        if check is QACheck.THUMBNAIL_STRENGTH:
            return {
                "rule": CompositionRule.RULE_OF_THIRDS,
                "emphasis": "strong focal point",
            }
        return {}

    @staticmethod
    def _project(
        scores: dict[str, float], actions: list[OptimizationAction]
    ) -> ExpectedScoreImprovement:
        """Project the eight scores after all actions, deterministically."""
        gains = {field: 0.0 for field in SCORE_FIELDS}
        for action in actions:
            field = action.target_score
            if field not in gains:
                continue
            gains[field] = min(MAX_GAIN_PER_ROUND, gains[field] + action.expected_gain)

        projected = {
            field: min(100.0, scores[field] + gains[field]) for field in SCORE_FIELDS
        }
        overall = RenderOptimizer._overall(projected)
        before = RenderOptimizer._overall(scores)
        sub_scores = list(projected.values())
        predicted_pass = (
            overall >= PASS_THRESHOLD
            and all(score >= FAIL_FLOOR for score in sub_scores)
            and not any(
                a.rationale and "critical" in a.rationale.lower() for a in actions
            )
        )
        return ExpectedScoreImprovement(
            engineering=projected["engineering_score"],
            educational=projected["educational_score"],
            composition=projected["composition_score"],
            subject_hierarchy=projected["subject_hierarchy_score"],
            visual_clarity=projected["visual_clarity_score"],
            thumbnail=projected["thumbnail_score"],
            consistency=projected["consistency_score"],
            overall=round(overall, 1),
            improvement=round(max(0.0, overall - before), 1),
            predicted_pass=predicted_pass,
        )

    @staticmethod
    def _overall(scores: dict[str, float]) -> float:
        return sum(
            SCORE_WEIGHTS[_FIELD_TO_BUCKET[field]] * value
            for field, value in scores.items()
        )