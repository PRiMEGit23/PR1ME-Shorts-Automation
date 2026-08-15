"""The closed render loop: render -> QA -> optimize -> render again.

One scene's autonomous improvement cycle. The loop:

1. renders attempt N (via the Renderer protocol; results are content-cached)
2. runs Image QA on the render
3. on PASS: record the winner and stop
4. on FAIL: ask the Render Optimizer for a plan, apply the plan's prompt
   mutations, regenerate the workflow, and loop until PASS or the budget.

Guarantees:
- never repeats an identical render: the content fingerprint is checked
  against executed fingerprints and the cache before any render
- no LLM calls anywhere: every stage is deterministic
- every attempt is recorded in a RenderHistory (and saved to disk when
  artifact saving is on)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from knowledge.compiler import compile_for_storyboard
from knowledge.compiler.prompt_compiler import CompiledPrompt
from knowledge.educational_director.educational_models import EducationalPlan
from knowledge.image_qa.image_critic import ImageCritic, QAContext
from knowledge.model_director import (
    SWITCH_AFTER_ATTEMPTS,
    next_fallback,
    replan_for_model,
    should_switch_model,
)
from knowledge.model_director.model_profiles import SceneModelPlan
from knowledge.render_optimizer import (
    OptimizationEngine,
    RenderOptimizer,
    RenderProfileKey,
)
from knowledge.render_optimizer import (
    apply as apply_mutations,
)
from knowledge.visual_intelligence.storyboard import StoryboardScene, VisualStoryboard

from runtime.cache import RenderCache
from runtime.models import (
    AttemptStatus,
    RenderAttempt,
    RenderRequest,
    RenderResult,
    RenderSessionResult,
    SessionConfig,
    attempt_dir,
    fingerprint_of,
)
from runtime.renderer import Renderer
from runtime.retry_manager import RetryManager
from runtime.workflow_builder import WorkflowBuilder


class RenderLoop:
    """One scene's deterministic close-the-loop generation cycle.

    The loop may run in two modes:

    - legacy (``directive=None``): the Phase-6 behavior, unchanged - the
      workflow profile comes from the storyboard, and the optimizer's plan
      regenerates the workflow.
    - directed (``directive=SceneModelPlan``): the workflow compiles from
      the Model Director's compiled backend profile via the backend
      adapters; after ``SWITCH_AFTER_ATTEMPTS`` consecutive QA failures the
      loop asks the deterministic fallback strategy whether a different
      image model predicts meaningfully higher quality, and switches when
      it does (recorded as a ``MODEL_SWITCHED`` attempt).
    """

    def __init__(
        self,
        *,
        renderer: Renderer,
        optimizer: OptimizationEngine | RenderOptimizer | None = None,
        critic: ImageCritic | None = None,
        workflow_builder: WorkflowBuilder | None = None,
        cache: RenderCache | None = None,
        retry_manager: RetryManager | None = None,
    ) -> None:
        self._renderer = renderer
        self._optimizer = optimizer if optimizer is not None else OptimizationEngine()
        self._critic = critic if critic is not None else ImageCritic()
        self._workflow_builder = (
            workflow_builder if workflow_builder is not None else WorkflowBuilder()
        )
        # NB: never use `cache or ...` - an empty RenderCache is falsy (__len__).
        self._cache = cache if cache is not None else RenderCache()
        self._retries = retry_manager if retry_manager is not None else RetryManager()

    def run(
        self,
        *,
        plan: EducationalPlan,
        storyboard: VisualStoryboard,
        scene: StoryboardScene,
        topic: str,
        seed: int,
        config: SessionConfig,
        directive: SceneModelPlan | None = None,
    ) -> RenderSessionResult:
        """Run the loop for one scene and return the full session result."""
        compiled = compile_for_storyboard(storyboard, config.model_key, topic=topic)
        current_prompt = compiled.scenes[scene.scene_id]
        current_directive = directive
        if current_directive is not None:
            profile = current_directive.workflow_profile
            current_workflow = self._workflow_builder.build_from_directive(
                prompt=current_prompt, plan=current_directive
            )
        else:
            profile, _ = _initial_profile(scene)
            current_workflow = self._workflow_builder.build(
                prompt=current_prompt, profile=profile
            )

        attempts: list[RenderAttempt] = []
        index = 1
        while self._retries.can_render(_render_count(attempts)):
            attempt_id = f"attempt_{index:02d}"
            fingerprint = fingerprint_of(
                current_prompt.prompt, current_prompt.negative_prompt, current_workflow, seed
            )

            if self._retries.is_duplicate(fingerprint):
                attempts.append(
                    RenderAttempt(
                        attempt_id=attempt_id,
                        index=index,
                        status=AttemptStatus.SKIPPED_DUPLICATE,
                        scene_id=scene.scene_id,
                        prompt=current_prompt.prompt,
                        negative_prompt=current_prompt.negative_prompt or "",
                        workflow=current_workflow,
                        workflow_profile=profile,
                        seed=seed,
                        fingerprint=fingerprint,
                        image_sha256=_sha256(b""),
                        image_model=(
                            current_directive.model_profile.image_model
                            if current_directive is not None
                            else None
                        ),
                        rationale=(
                            f"identical render to a previous attempt "
                            f"({fingerprint[:12]}); deterministic loop stops"
                        ),
                    )
                )
                break

            result = self._render_or_reuse(
                fingerprint,
                current_prompt,
                current_workflow,
                profile,
                scene,
                seed,
                index,
                image_model=(
                    current_directive.model_profile.image_model
                    if current_directive is not None
                    else None
                ),
            )
            self._retries.record(fingerprint)

            ctx = QAContext(
                plan=plan,
                storyboard=storyboard,
                scene=scene,
                metadata=result.metadata,
                compiled_prompt=current_prompt,
            )
            report = self._critic.assess(ctx, topic=topic)

            passed = report.pass_fail.value == "pass"
            optimization_report = None
            if not passed:
                optimization_report = self._optimizer.optimize(
                    report, scene=scene, compiled_prompt=current_prompt
                )

            if passed:
                rationale = "QA passed; the image is accepted"
            elif optimization_report is not None:
                rationale = (
                    f"QA rejected (overall {report.overall_score}); "
                    f"{len(optimization_report.optimization_actions)} "
                    "optimization actions prescribed"
                )
            else:
                rationale = "QA rejected; the optimizer prescribed nothing"
            attempt = RenderAttempt(
                attempt_id=attempt_id,
                index=index,
                status=AttemptStatus.PASSED if passed else AttemptStatus.FAILED,
                scene_id=scene.scene_id,
                prompt=current_prompt.prompt,
                negative_prompt=current_prompt.negative_prompt or "",
                workflow=current_workflow,
                workflow_profile=profile,
                seed=seed,
                fingerprint=fingerprint,
                image_sha256=_sha256(result.image_bytes),
                image_model=(
                    current_directive.model_profile.image_model
                    if current_directive is not None
                    else None
                ),
                qa_report=report,
                optimization_report=optimization_report,
                rationale=rationale,
            )
            attempts.append(attempt)

            if config.save_artifacts:
                self._save_attempt(config.output_root, topic, attempt, result)

            if passed:
                break

            switch = None
            if current_directive is not None and optimization_report is not None:
                switch = self._maybe_switch_model(
                    attempts,
                    current_directive,
                    scene,
                    current_prompt,
                    seed,
                )
                if switch is not None:
                    current_directive, current_workflow, switch_attempt = switch
                    profile = current_directive.workflow_profile
                    attempts.append(switch_attempt)
                    index += 1

            if not self._retries.can_render(_render_count(attempts)):
                break
            if optimization_report is None or not optimization_report.optimization_actions:
                break

            mutated_prompt, mutated_negative = apply_mutations(
                current_prompt.prompt,
                current_prompt.negative_prompt or "",
                optimization_report.prompt_mutations,
            )
            mutated = CompiledPrompt(
                prompt=mutated_prompt,
                negative_prompt=mutated_negative or None,
                metadata=current_prompt.metadata,
            )
            visualization_tokens: tuple[str, ...] = ()
            if optimization_report.visualization_changes:
                visualization_tokens = tuple(
                    optimization_report.visualization_changes[-1].prompt_tokens
                )
            if current_directive is not None:
                next_workflow = self._workflow_builder.build_from_directive(
                    prompt=mutated,
                    plan=current_directive,
                    visualization_tokens=visualization_tokens,
                )
            else:
                next_workflow = self._workflow_builder.regenerate(
                    optimization_report, current_workflow
                )
            if (
                mutated_prompt == current_prompt.prompt
                and mutated_negative == (current_prompt.negative_prompt or "")
                and next_workflow == current_workflow
            ):
                break
            current_prompt = mutated
            current_workflow = next_workflow
            index += 1

        return RenderSessionResult(
            topic=topic,
            scene_id=scene.scene_id,
            seed=seed,
            max_attempts=self._retries.max_attempts,
            passed=any(a.status is AttemptStatus.PASSED for a in attempts),
            winner=next((a for a in reversed(attempts) if a.status is AttemptStatus.PASSED), None),
            attempts=attempts,
        )

    def _render_or_reuse(
        self,
        fingerprint: str,
        prompt: CompiledPrompt,
        workflow: dict,
        profile: RenderProfileKey,
        scene: StoryboardScene,
        seed: int,
        index: int,
        image_model: str | None = None,
    ) -> RenderResult:
        """Render, or reuse the cached result for this fingerprint."""
        cached = self._cache.get(fingerprint)
        if cached is not None:
            return cached
        request = RenderRequest(
            attempt_index=index,
            scene_id=scene.scene_id,
            prompt=prompt.prompt,
            negative_prompt=prompt.negative_prompt or "",
            workflow=workflow,
            workflow_profile=profile,
            seed=seed,
            image_model=image_model,
        )
        result = self._renderer.render(request)
        self._cache.put(fingerprint, result)
        return result

    def _maybe_switch_model(
        self,
        attempts: list[RenderAttempt],
        directive: SceneModelPlan,
        scene: StoryboardScene,
        prompt: CompiledPrompt,
        seed: int,
    ) -> tuple[SceneModelPlan, dict[str, Any], RenderAttempt] | None:
        """Ask the fallback strategy whether the image model should switch.

        Returns (new directive, new workflow, the MODEL_SWITCHED attempt)
        when the deterministic rules say a different model predicts
        meaningfully higher QA - or None when nothing changes.
        """
        failures = 0
        for attempt in reversed(attempts):
            if attempt.status is AttemptStatus.FAILED:
                failures += 1
            else:
                break
        current = directive.model_profile.image_model
        if failures < SWITCH_AFTER_ATTEMPTS:
            return None
        fallback = next_fallback(current)
        if fallback is None:
            return None
        switched, reason = should_switch_model(
            current,
            fallback,
            scene.intent.shot_type,
            consecutive_failures=failures,
        )
        if not switched:
            return None
        new_directive = replan_for_model(directive, fallback)
        new_workflow = self._workflow_builder.build_from_directive(
            prompt=prompt, plan=new_directive
        )
        attempt = RenderAttempt(
            attempt_id=f"attempt_{len(attempts) + 1:02d}",
            index=len(attempts) + 1,
            status=AttemptStatus.MODEL_SWITCHED,
            scene_id=scene.scene_id,
            prompt=prompt.prompt,
            negative_prompt=prompt.negative_prompt or "",
            workflow=new_workflow,
            workflow_profile=new_directive.workflow_profile,
            seed=seed,
            fingerprint=fingerprint_of(
                prompt.prompt, prompt.negative_prompt, new_workflow, seed
            ),
            image_sha256=_sha256(b""),
            image_model=fallback,
            rationale=reason,
        )
        return new_directive, new_workflow, attempt

    @staticmethod
    def _save_attempt(
        output_root: Path,
        topic: str,
        attempt: RenderAttempt,
        result: RenderResult,
    ) -> None:
        directory = attempt_dir(output_root, topic, attempt.scene_id, attempt.attempt_id)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "prompt.txt").write_text(attempt.prompt, encoding="utf-8")
        (directory / "prompt_negative.txt").write_text(
            attempt.negative_prompt, encoding="utf-8"
        )
        (directory / "workflow.json").write_text(
            json.dumps(attempt.workflow, indent=2, sort_keys=True), encoding="utf-8"
        )
        if attempt.qa_report is not None:
            (directory / "qa_report.json").write_text(
                attempt.qa_report.model_dump_json(indent=2), encoding="utf-8"
            )
        if attempt.optimization_report is not None:
            (directory / "optimization_report.json").write_text(
                attempt.optimization_report.model_dump_json(indent=2), encoding="utf-8"
            )
        (directory / "image.png").write_bytes(result.image_bytes)
        attempt.image_path = directory / "image.png"
        (directory / "attempt.json").write_text(
            attempt.model_dump_json(indent=2), encoding="utf-8"
        )


def _render_count(attempts: list[RenderAttempt]) -> int:
    """How many attempts actually consumed a render (switches excluded)."""
    return sum(
        1
        for attempt in attempts
        if attempt.status
        not in (AttemptStatus.SKIPPED_DUPLICATE, AttemptStatus.MODEL_SWITCHED)
    )


def _initial_profile(scene: StoryboardScene) -> tuple[RenderProfileKey, str]:
    from knowledge.render_optimizer import select_workflow_profile

    return select_workflow_profile(
        visualization_type=(
            scene.intent.engineering_visualizations[0].type
            if scene.intent.engineering_visualizations
            else None
        ),
        shot_type=scene.intent.shot_type,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()