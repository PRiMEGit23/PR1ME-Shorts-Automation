"""Script Generator stage (prompt 02).

Loads ``02_script_generator.md`` dynamically, turns one approved topic into a
four-block spoken script, and returns a validated :class:`ScriptOutput`.
"""

from __future__ import annotations

from pr1me.core.base_stage import BaseStage
from pr1me.core.errors import PromptNotFoundError, ProviderNotConfiguredError
from pr1me.models.contracts.script import ScriptInput, ScriptOutput
from pr1me.providers.base_provider import CompletionRequest

#: Lightly creative wiring; the strict 120-word cap is enforced by the contract.
_SCRIPT_TEMPERATURE = 0.7
_SCRIPT_MAX_TOKENS = 400


class ScriptStage(BaseStage[ScriptInput, ScriptOutput]):
    """Writes one 35-45s spoken script for an approved topic."""

    stage_id = "script"
    name = "Script Writer"
    description = "Writes a premium script (hook / explanation / insight / ending)."
    version = "1.0.0"
    prompt_file = "02_script_generator.md"
    depends_on = ("topic",)
    input_model = ScriptInput
    output_model = ScriptOutput

    async def execute(self, payload: ScriptInput) -> ScriptOutput:
        loader = self.context.prompt_loader
        if loader is None:
            raise PromptNotFoundError("no prompt loader is configured for the script stage")
        provider = self.context.provider
        if provider is None:
            raise ProviderNotConfiguredError("no AI provider is configured for the script stage")

        doc = await loader.load(self.prompt_file)
        request = CompletionRequest(
            model=None,
            messages=[
                {"role": "system", "content": doc.content},
                {"role": "user", "content": self._user_message(payload)},
            ],
            temperature=_SCRIPT_TEMPERATURE,
            max_tokens=_SCRIPT_MAX_TOKENS,
        )
        structured = await provider.generate_json(request, ScriptOutput)
        return structured.value

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _user_message(payload: ScriptInput) -> str:
        lines = [f"topic: {payload.topic}"]
        if payload.factual_context:
            lines.append(f"factual_context: {payload.factual_context}")
        return "\n".join(lines)