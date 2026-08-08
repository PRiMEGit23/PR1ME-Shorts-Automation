"""Basic framework smoke tests for base_stage, stage_registry, prompt_loader."""

from __future__ import annotations

import asyncio
import logging

import pytest

from pr1me.core.base_stage import BaseStage
from pr1me.core.config import Settings
from pr1me.core.context import StageContext
from pr1me.core.errors import (
    ContractViolationError,
    ModelValidationError,
    PipelineDependencyError,
    StageRegistrationError,
)
from pr1me.core.prompt_loader import PromptLoader
from pr1me.core.stage_registry import StageRegistry
from pr1me.models.contracts.base import StageInput, StageOutput


class DummyInput(StageInput):
    value: str


class DummyOutput(StageOutput):
    ok: int


class GoodStage(BaseStage[DummyInput, DummyOutput]):
    stage_id = "good"
    name = "Good"
    input_model = DummyInput
    output_model = DummyOutput

    async def execute(self, payload: DummyInput) -> DummyOutput:
        return DummyOutput(ok=len(payload.value))


class FailingStage(GoodStage):
    stage_id = "failing"

    async def execute(self, payload: DummyInput) -> DummyOutput:
        raise RuntimeError("boom")


class DuplicateStage(GoodStage):
    stage_id = "good"


logger = logging.getLogger("test")


def build_context() -> StageContext:
    return StageContext(settings=Settings(), logger=logger)


def test_stage_happy_path() -> None:
    stage = GoodStage(context=build_context())

    async def go() -> None:
        result = await stage.run(DummyInput(value="hello"))
        assert result.ok == 5

    asyncio.run(go())


def test_stage_invalid_input_fails_fast() -> None:
    stage = GoodStage(context=build_context())

    async def go() -> None:
        with pytest.raises(ModelValidationError):
            await stage.run({"value": 123})  # type: ignore[arg-type]

    asyncio.run(go())


def test_stage_contract_violation() -> None:
    class BrokenStage(GoodStage):
        stage_id = "broken"

        async def execute(self, payload: DummyInput) -> DummyOutput:
            return {"ok": "not-an-int"}  # type: ignore[return-value]

    stage = BrokenStage(context=build_context())

    async def go() -> None:
        with pytest.raises(ContractViolationError):
            await stage.run({"value": "x"})

    asyncio.run(go())


def test_stage_generic_exception_wrapped() -> None:
    stage = FailingStage(context=build_context())

    async def go() -> None:
        from pr1me.core.errors import StageExecutionError

        with pytest.raises(StageExecutionError):
            await stage.run({"value": "x"})

    asyncio.run(go())


def test_registry_register_duplicate() -> None:
    registry = StageRegistry(context=build_context())
    registry.register(GoodStage)
    with pytest.raises(StageRegistrationError):
        registry.register(DuplicateStage)


def test_registry_execution_order_and_dep_validation() -> None:
    class DependentStage(GoodStage):
        stage_id = "dep_last"
        depends_on = ("good",)

    registry = StageRegistry(context=build_context())
    registry.register(GoodStage)
    registry.register(DependentStage)
    order = registry.execution_order()
    assert order.index("good") < order.index("dep_last")
    registry.validate()


def test_registry_unknown_dep_raises() -> None:
    class GhostDepStage(GoodStage):
        stage_id = "ghost_dep"
        depends_on = ("ghost",)

    registry = StageRegistry(context=build_context())
    registry.register(GhostDepStage)
    with pytest.raises(PipelineDependencyError):
        registry.validate()


def test_registry_instances_bypassed() -> None:
    registry = StageRegistry(context=build_context())
    instance = GoodStage(context=build_context())
    registry.register(instance)
    assert registry.resolve("good") is instance


def test_prompt_loader_finds_and_caches(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "01_topic_generator.md").write_text("# Topic", encoding="utf-8")
    loader = PromptLoader(prompts)

    async def go() -> None:
        doc = await loader.load("01_topic_generator.md")
        assert doc.slug == "topic_generator"
        assert doc.content == "# Topic"
        assert await loader.exists("topic_generator")
        assert await loader.missing(["02_script_generator.md"]) == ["02_script_generator.md"]
        again = await loader.load("01_topic_generator.md")
        assert again.slug == doc.slug

    asyncio.run(go())


def test_prompt_loader_missing_raises(tmp_path) -> None:
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    loader = PromptLoader(prompts)

    async def go() -> None:
        from pr1me.core.errors import PromptNotFoundError

        with pytest.raises(PromptNotFoundError):
            await loader.load("01_topic_generator.md")

    asyncio.run(go())


def test_provider_noop_fails_fast() -> None:
    from pr1me.core.errors import ProviderNotConfiguredError
    from pr1me.providers import CompletionRequest, NoopProvider, ProviderRegistry

    async def go() -> None:
        provider = ProviderRegistry().build("noop")
        assert isinstance(provider, NoopProvider)
        with pytest.raises(ProviderNotConfiguredError):
            await provider.generate(CompletionRequest(messages=[{"role": "user", "content": "hi"}]))

    asyncio.run(go())