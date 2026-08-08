"""Visual Director stage (prompt 04).

Loads ``04_visual_director.md`` dynamically, translates one approved script
(and the fact-check verdict) into a timed shot plan, and returns a validated
:class:`VisualPlanOutput`.
"""

from __future__ import annotations

import json

from pr1me.core.base_stage import BaseStage
from pr1me.core.errors import PromptNotFoundError, ProviderNotConfiguredError
from pr1me.models.contracts.visual import VisualInput, VisualPlanOutput
from pr1me.providers.base_provider import CompletionRequest

#: Moderately creative: staging variety matters, shot timings remain structural.
_VISUAL_TEMPERATURE = 0.7
_VISUAL_MAX_TOKENS = 1500


class VisualStage(BaseStage[VisualInput, VisualPlanOutput]):
    """Plans the timed shot list that mirrors the approved narration."""

    stage_id = "visual"
    name = "Visual Director"
    description = "Plans a 35-45s visual shot sequence for the script."
    version = "1.0.0"
    prompt_file = "04_visual_director.md"
    depends_on = ("script", "fact_check")
    input_model = VisualInput
    output_model = VisualPlanOutput

    async def execute(self, payload: VisualInput) -> VisualPlanOutput:
        loader = self.context.prompt_loader
        if loader is None:
            raise PromptNotFoundError("no prompt loader is configured for the visual stage")
        provider = self.context.provider
        if provider is None:
            raise ProviderNotConfiguredError("no AI provider is configured for the visual stage")

        doc = await loader.load(self.prompt_file)
        request = CompletionRequest(
            model=None,
            messages=[
                {"role": "system", "content": doc.content},
                {"role": "user", "content": self._user_message(payload)},
            ],
            temperature=_VISUAL_TEMPERATURE,
            max_tokens=_VISUAL_MAX_TOKENS,
        )
        structured = await provider.generate_json(request, VisualPlanOutput)
        return structured.value

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _user_message(payload: VisualInput) -> str:
        script = {
            "hook": payload.hook,
            "explanation": payload.explanation,
            "practical_insight": payload.practical_insight,
            "ending": payload.ending,
        }
        lines = []
        if payload.topic:
            lines.append(f"topic: {payload.topic}")
        lines.append(f"script: {json.dumps(script)}")
        if payload.verdict:
            lines.append(f"fact_check_verdict: {payload.verdict}")
        corrections = payload.corrections.model_dump(exclude_none=True)
        if corrections:
            lines.append(f"fact_check_corrections: {json.dumps(corrections)}")
        return "\n".join(lines)