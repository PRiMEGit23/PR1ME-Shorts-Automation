"""Fact Checker stage (prompt 03).

Loads ``03_fact_checker.md`` dynamically, reviews the generated script for
factual and engineering accuracy, and returns a validated
:class:`FactSummaryOutput` (verdict + findings + corrections).
"""

from __future__ import annotations

from pr1me.core.base_stage import BaseStage
from pr1me.core.errors import PromptNotFoundError, ProviderNotConfiguredError
from pr1me.models.contracts.factcheck import FactCheckInput, FactSummaryOutput
from pr1me.providers.base_provider import CompletionRequest

#: Lower temperature: review should be consistent and conservative.
_FACT_TEMPERATURE = 0.2
_FACT_MAX_TOKENS = 400


class FactCheckStage(BaseStage[FactCheckInput, FactSummaryOutput]):
    """Audits a script for engineering/factual accuracy."""

    stage_id = "fact_check"
    name = "Fact Checker"
    description = "Reviews script accuracy and returns a structured verdict."
    version = "1.0.0"
    prompt_file = "03_fact_checker.md"
    depends_on = ("script",)
    input_model = FactCheckInput
    output_model = FactSummaryOutput

    async def execute(self, payload: FactCheckInput) -> FactSummaryOutput:
        loader = self.context.prompt_loader
        if loader is None:
            raise PromptNotFoundError("no prompt loader is configured for the fact-check stage")
        provider = self.context.provider
        if provider is None:
            raise ProviderNotConfiguredError("no AI provider is configured for the fact-check stage")

        doc = await loader.load(self.prompt_file)
        request = CompletionRequest(
            model=None,
            messages=[
                {"role": "system", "content": doc.content},
                {"role": "user", "content": self._user_message(payload)},
            ],
            temperature=_FACT_TEMPERATURE,
            max_tokens=_FACT_MAX_TOKENS,
        )
        structured = await provider.generate_json(request, FactSummaryOutput)
        return structured.value

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _user_message(payload: FactCheckInput) -> str:
        lines = ["script:"]
        lines.append(f"  hook: {payload.hook}")
        lines.append(f"  explanation: {payload.explanation}")
        lines.append(f"  practical_insight: {payload.practical_insight}")
        lines.append(f"  ending: {payload.ending}")
        if payload.word_count is not None:
            lines.append(f"  word_count: {payload.word_count}")
        if payload.topic:
            lines.append(f"topic: {payload.topic}")
        return "\n".join(lines)