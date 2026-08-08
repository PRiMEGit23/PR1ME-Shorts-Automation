"""Topic Generator stage (prompt 01).

Loads ``01_topic_generator.md`` dynamically and asks the configured AI for
exactly one topic. The prompt text lives only in ``/prompts``; this stage just
wires the prompt to the provider contract.
"""

from __future__ import annotations

import json

from pr1me.core.base_stage import BaseStage
from pr1me.core.errors import PromptNotFoundError, ProviderNotConfiguredError
from pr1me.models.contracts.topic import TopicInput, TopicOutput
from pr1me.providers.base_provider import CompletionRequest

#: Fixed sampling budget for one topic; no extra prose, no list.
_TOPIC_TEMPERATURE = 0.7
_TOPIC_MAX_TOKENS = 200


class TopicStage(BaseStage[TopicInput, TopicOutput]):
    """Generates one approved topic from existing topics, a directive, and an
    optional category focus."""

    stage_id = "topic"
    name = "Topic Generator"
    description = "Generates one premium 3D-printing / engineering Short topic."
    version = "1.0.0"
    prompt_file = "01_topic_generator.md"
    input_model = TopicInput
    output_model = TopicOutput

    async def execute(self, payload: TopicInput) -> TopicOutput:
        loader = self.context.prompt_loader
        if loader is None:
            raise PromptNotFoundError("no prompt loader is configured for the topic stage")
        doc = await loader.load(self.prompt_file)
        provider = self.context.provider
        if provider is None:
            raise ProviderNotConfiguredError("no AI provider is configured for the topic stage")

        request = CompletionRequest(
            model=None,
            messages=[
                {"role": "system", "content": doc.content},
                {"role": "user", "content": self._user_message(payload)},
            ],
            temperature=_TOPIC_TEMPERATURE,
            max_tokens=_TOPIC_MAX_TOKENS,
        )
        structured = await provider.generate_json(request, TopicOutput)
        return structured.value

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _user_message(payload: TopicInput) -> str:
        lines = [
            f"existing_topics: {', '.join(payload.existing_topics) or '(none)'}",
            f"directive: {json.dumps(payload.directive)}",
        ]
        if payload.category_focus is not None:
            lines.append(f"category_focus: {json.dumps(payload.category_focus)}")
        return "\n".join(lines)