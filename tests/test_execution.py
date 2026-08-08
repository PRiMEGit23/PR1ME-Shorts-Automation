"""Execution-layer tests: DeepSeekProvider, TopicStage, PipelineRunner."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import (
    JobAbortedError,
    PromptLoadError,
    ProviderNotConfiguredError,
)
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.topic import TopicInput, TopicOutput
from pr1me.pipeline.runner import PipelineRunner, RunReport
from pr1me.providers import (
    Completion,
    CompletionRequest,
    DeepSeekProvider,
    Usage,
)
from pr1me.providers.base_provider import BaseProvider
from pr1me.stages import TopicStage, register_auto

logger: logging.LoggerAdapter = logging.LoggerAdapter(logging.getLogger("test-execution"), {})


@pytest.fixture
def prompt_dir(tmp_path: Path) -> Path:
    """A prompts directory containing the four content-stage prompts."""
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "01_topic_generator.md").write_text(
        "# 01 Topic Generator\n\nReturn exactly one topic.", encoding="utf-8"
    )
    (prompts / "02_script_generator.md").write_text(
        "# 02 Script Generator\n\nReturn a four-block script.", encoding="utf-8"
    )
    (prompts / "03_fact_checker.md").write_text(
        "# 03 Fact Checker\n\nReturn a verdict.", encoding="utf-8"
    )
    (prompts / "04_visual_director.md").write_text(
        "# 04 Visual Director\n\nReturn a shot plan.", encoding="utf-8"
    )
    return prompts


def build_context(*, provider: BaseProvider | None = None, prompts_dir: Path) -> StageContext:
    settings = Settings()
    return StageContext(
        settings=settings,
        logger=logger,
        prompt_loader=PromptLoader(prompts_dir),
        provider=provider,
    )


# ------------------------------------------------------------------ DeepSeek --


def _deepseek_response(body: str) -> dict:
    return {
        "choices": [{"message": {"content": body}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


_TEST_TOPIC_JSON = '{"topic": "First-Layer Squish"}'


def _deepseek_handler(status: int = 200, body: str = _TEST_TOPIC_JSON) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            headers={"content-type": "application/json"},
            content=json.dumps(_deepseek_response(body)),
        )

    return httpx.MockTransport(handler)


def _deepseek_provider(transport: httpx.MockTransport) -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        http_client=httpx.AsyncClient(transport=transport),
    )


def test_deepseek_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PR1ME_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ProviderNotConfiguredError, match="API key"):
        DeepSeekProvider()


def test_deepseek_generate_parses_json() -> None:
    async def go() -> None:
        provider = _deepseek_provider(_deepseek_handler())
        request = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=200
        )
        completion = await provider.generate(request)
        assert completion.text == '{"topic": "First-Layer Squish"}'
        assert completion.usage.total_tokens == 15
        model = completion.parse_json(TopicOutput)
        assert model.topic == "First-Layer Squish"
        await provider.close()

    asyncio.run(go())


def test_deepseek_http_error() -> None:
    async def go() -> None:
        provider = _deepseek_provider(_deepseek_handler(status=500))
        with pytest.raises(Exception, match="HTTP 500"):
            await provider.generate(CompletionRequest(messages=[{"role": "user", "content": "x"}]))
        await provider.close()

    asyncio.run(go())


def test_deepseek_retries_transient_failure() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(503, headers={"content-type": "application/json"}, content=b"")
        payload = json.dumps(_deepseek_response(_TEST_TOPIC_JSON))
        return httpx.Response(200, headers={"content-type": "application/json"}, content=payload)

    async def go() -> None:
        provider = DeepSeekProvider(
            api_key="sk-test",
            base_url="https://api.deepseek.com",
            retry_base_delay=0.01,
            max_retries=4,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        completion = await provider.generate(CompletionRequest(messages=[{"role": "user", "content": "x"}]))
        assert completion.text == _TEST_TOPIC_JSON
        assert calls["count"] == 3
        await provider.close()

    asyncio.run(go())


def test_deepseek_variable_substitution() -> None:
    from pr1me.providers.deepseek import substitute_variables

    assert substitute_variables("Topic: {topic}", {"topic": "PETG"}) == "Topic: PETG"
    assert substitute_variables("{missing} stays", {"topic": "PETG"}) == "{missing} stays"


def test_deepseek_render_requires_loader() -> None:
    async def go() -> None:
        provider = DeepSeekProvider(api_key="sk-test", base_url="https://api.deepseek.com")
        with pytest.raises(PromptLoadError, match="no prompt loader"):
            await provider.render("01_topic_generator.md", {"topic": "PETG"})
        await provider.close()

    asyncio.run(go())


# ------------------------------------------------------------------ TopicStage --

class StubProvider(BaseProvider):
    """Returns a canned JSON topic without touching the network."""

    name = "stub"
    reply: str = '{"topic": "First-Layer Squish: Dial It In"}'

    async def generate(self, request: CompletionRequest) -> Completion:
        return Completion(
            request=request,
            text=self.reply,
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


#: Canned stage outputs selected by a marker substring of the system prompt.
_STAGE_REPLIES: dict[str, str] = {
    "01 Topic Generator": '{"topic": "First-Layer Squish: Dial It In"}',
    "02 Script Generator": (
        '{"hook": "Why does the layer lift?", "explanation": "Warping cools uneven.", '
        '"practical_insight": "Add a brim.", "ending": "Try it.", '
        '"word_count": 12}'
    ),
    "03 Fact Checker": (
        '{"verdict": "approved", "confidence": "high", "severity": "none", '
        '"findings": [], "corrections": {"hook": null, "explanation": null, '
        '"practical_insight": null, "ending": null}}'
    ),
    "04 Visual Director": (
        '{"total_seconds": 12, "shots": [{"id": 1, "block": "hook", '
        '"start_second": 0, "end_second": 6, "duration_seconds": 6, "visual": "macro", '
        '"camera": "push-in", "transition": "cut", "reason": "hook shot", '
        '"purpose": "Attention", "learning_goal": "learn the hook", '
        '"visual_type": "Macro Shot", "scene": {"subject": "bed", "environment": "bench", '
        '"composition": "centered", "lighting": "key", "camera_motion": "push", '
        '"focus": "nozzle", "style": "technical"}}], '
        '"branding": {"use_logo": true, "use_broll": true, "broll_source": null}}'
    ),
}


class PipelineStubProvider(BaseProvider):
    """Returns canned JSON per stage, selected by a system-prompt marker."""

    name = "pipeline-stub"

    async def generate(self, request: CompletionRequest) -> Completion:
        if not request.messages:
            raise AssertionError("expected a system message carrying the prompt")
        system = str(request.messages[0].get("content", ""))
        reply = '{"topic": "First-Layer Squish: Dial It In"}'
        for marker, canned in _STAGE_REPLIES.items():
            if marker in system:
                reply = canned
                break
        return Completion(
            request=request,
            text=reply,
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


def test_topic_stage_run(prompt_dir: Path) -> None:
    async def go() -> None:
        stage = TopicStage(context=build_context(provider=StubProvider(), prompts_dir=prompt_dir))
        output = await stage.run(
            TopicInput(
                existing_topics=["Layer Height", "Infill"],
                directive="balance beginner and advanced",
                category_focus="Materials",
            )
        )
        assert isinstance(output, TopicOutput)
        assert output.topic == "First-Layer Squish: Dial It In"

    asyncio.run(go())


def test_topic_stage_auto_registers(prompt_dir: Path) -> None:
    registry = StageRegistry(context=build_context(prompts_dir=prompt_dir))
    register_auto(registry)
    assert "topic" in registry


# ---------------------------------------------------------------- PipelineRun --


def test_runner_executes_all_pipeline_stages(tmp_path: Path, prompt_dir: Path) -> None:
    final_artifact: str | None = None

    async def go() -> None:
        nonlocal final_artifact
        context = build_context(provider=PipelineStubProvider(), prompts_dir=prompt_dir)
        registry = StageRegistry(context=context)
        register_auto(registry)
        runner = PipelineRunner(registry, context=context, artifact_dir=tmp_path)
        report = await runner.run(
            {
                "existing_topics": ["Infill"],
                "directive": "practical engineering tips",
            },
            job_id="job-1",
        )
        assert isinstance(report, RunReport)
        assert report.run_status.value == "complete"
        assert [record.stage_id for record in report.stages] == [
            "topic",
            "script",
            "fact_check",
            "visual",
        ]
        for record in report.stages:
            assert record.status.value == "ok", record.stage_id
        final_artifact = report.final_artifact

    asyncio.run(go())
    assert final_artifact is not None
    assert Path(final_artifact).exists()
    for name in (
        "job-1_topic.json",
        "job-1_script.json",
        "job-1_fact_check.json",
        "job-1_visual.json",
    ):
        assert (tmp_path / name).exists(), name
    assert json.loads((tmp_path / "job-1_visual.json").read_text(encoding="utf-8"))[
        "total_seconds"
    ] == 12


def test_single_stages_run_full_chain(prompt_dir: Path) -> None:
    async def go() -> None:
        context = build_context(provider=PipelineStubProvider(), prompts_dir=prompt_dir)
        registry = StageRegistry(context=context)
        register_auto(registry)

        script_stage = registry.resolve("script")
        script = await script_stage.run(
            {
                "topic": "First-Layer Squish",
                "existing_topics": [],
                "directive": "practical tips",
            }
        )
        assert script.hook == "Why does the layer lift?"

        fact_stage = registry.resolve("fact_check")
        verdict = await fact_stage.run(script.model_dump(mode="json"))
        assert verdict.verdict == "approved"

        visual_stage = registry.resolve("visual")
        plan = await visual_stage.run(
            {
                "topic": "First-Layer Squish",
                **script.model_dump(mode="json"),
                "verdict": verdict.verdict,
            }
        )
        assert plan.total_seconds == 12
        assert plan.shots[0].block == "hook"

    asyncio.run(go())


def test_runner_aborts_on_failure(tmp_path: Path, prompt_dir: Path) -> None:
    class BrokenProvider(StubProvider):
        reply = "not json"

    async def go() -> None:
        context = build_context(provider=BrokenProvider(), prompts_dir=prompt_dir)
        registry = StageRegistry(context=context)
        register_auto(registry)
        runner = PipelineRunner(registry, context=context, artifact_dir=tmp_path)
        with pytest.raises(JobAbortedError):
            await runner.run({"directive": "anything"}, job_id="job-2")
        assert runner.last_report is not None
        assert runner.last_report.run_status.value == "failed"

    asyncio.run(go())