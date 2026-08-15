"""Session manager: run the full knowledge -> render -> QA -> optimize pipeline.

RenderSession is the runtime's entry point. For one Knowledge Base row it
runs the whole deterministic chain - Educational Director, Visual
Intelligence (via the StoryboardBuilder adapter), Prompt Compiler - and then
hands each scene to the RenderLoop. The session persists every attempt's
artifacts (prompt, workflow JSON, QA report, optimization report, image) and
writes a replayable history JSON alongside them.

Same row + same seed always reproduces the same sequence: nothing in the
session depends on clocks, randomness, or models.
"""

from __future__ import annotations

from pathlib import Path

from knowledge.educational_director import EducationalDirector
from knowledge.image_qa.image_critic import ImageCritic
from knowledge.render_optimizer import OptimizationEngine
from knowledge.visual_architecture import EngineeringDomain, Modality

from runtime.cache import RenderCache
from runtime.models import RenderSessionResult, SessionConfig
from runtime.render_loop import RenderLoop
from runtime.renderer import Renderer
from runtime.retry_manager import RetryManager
from runtime.storyboard_builder import StoryboardBuilder
from runtime.workflow_builder import WorkflowBuilder


class RenderSession:
    """The autonomous generation engine for one topic row."""

    def __init__(
        self,
        *,
        renderer: Renderer,
        director: EducationalDirector | None = None,
        storyboard_builder: StoryboardBuilder | None = None,
        loop: RenderLoop | None = None,
        cache: RenderCache | None = None,
    ) -> None:
        self._renderer = renderer
        self._director = director if director is not None else EducationalDirector()
        self._storyboard_builder = (
            storyboard_builder if storyboard_builder is not None else StoryboardBuilder()
        )
        self._loop = loop
        # NB: never use `cache or ...` - an empty RenderCache is falsy (__len__).
        self._cache = cache if cache is not None else RenderCache()

    def run(
        self,
        row: dict[str, str],
        scene_id: str,
        *,
        seed: int,
        engineering_domain: EngineeringDomain,
        modality: Modality,
        config: SessionConfig | None = None,
    ) -> RenderSessionResult:
        """Generate one scene autonomously; returns the full session result."""
        config = config or SessionConfig()
        plan = self._director.direct_from_csv(row)
        storyboard = self._storyboard_builder.build(
            plan,
            engineering_domain=engineering_domain,
            modality=modality,
        )
        scene = next(s for s in storyboard.scenes if s.scene_id == scene_id)
        loop = self._loop or self._make_loop()
        result = loop.run(
            plan=plan,
            storyboard=storyboard,
            scene=scene,
            topic=plan.topic,
            seed=seed,
            config=config,
        )
        if config.save_artifacts:
            self._save_session(config.output_root, result)
        return result

    def run_all(
        self,
        row: dict[str, str],
        *,
        seed: int,
        engineering_domain: EngineeringDomain,
        modality: Modality,
        config: SessionConfig | None = None,
    ) -> dict[str, RenderSessionResult]:
        """Generate every scene of the row in order; scene_id -> result."""
        config = config or SessionConfig()
        plan = self._director.direct_from_csv(row)
        storyboard = self._storyboard_builder.build(
            plan,
            engineering_domain=engineering_domain,
            modality=modality,
        )
        results: dict[str, RenderSessionResult] = {}
        for scene in storyboard.scenes:
            results[scene.scene_id] = self.run(
                row,
                scene.scene_id,
                seed=seed,
                engineering_domain=engineering_domain,
                modality=modality,
                config=config,
            )
        return results

    def _make_loop(self) -> RenderLoop:
        return RenderLoop(
            renderer=self._renderer,
            optimizer=OptimizationEngine(),
            critic=ImageCritic(),
            workflow_builder=WorkflowBuilder(),
            cache=self._cache,
            retry_manager=RetryManager(),
        )

    @staticmethod
    def _save_session(output_root: Path, result: RenderSessionResult) -> Path:
        from runtime.models import topic_slug

        directory = output_root / topic_slug(result.topic) / result.scene_id
        directory.mkdir(parents=True, exist_ok=True)
        history_path = directory / "history.json"
        result.history.to_file(history_path)
        return history_path