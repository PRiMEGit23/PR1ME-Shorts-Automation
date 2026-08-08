"""Metadata stage (prompt 06).

Loads ``06_metadata_generator.md`` dynamically, turns one approved topic and
its script into the complete YouTube Shorts publication metadata, and returns
a validated :class:`MetadataOutput`.

The stage owns the deterministic boundary: the channel language default and
the SEO quality checks. The primary-keyword placement, the tag-count policy,
and the hashtag cap from prompt 06 are re-verified locally so a contract that
validates structurally but fails SEO fails fast.
"""

from __future__ import annotations

import re

from pr1me.core.base_stage import BaseStage
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.publishing import (
    MetadataOutput,
    PublishingInput,
)
from pr1me.models.meta import ValidationStatus
from pr1me.stages.publishing_common import generate_publishing_payload

#: SEO fidelity is structural; temperature stays low so metadata is stable.
_METADATA_TEMPERATURE = 0.5
_METADATA_MAX_TOKENS = 700

#: Channel default language (PIPELINE_SPEC: English channel).
_LANGUAGE = "en"

#: Prompt 06 tag-count policy: 5-10 realistic search terms.
_MIN_TAGS = 5
_MAX_TAGS = 10

#: Prompt 06 hashtag policy: no more than three.
_MAX_HASHTAGS = 3


class MetadataValidationError(PipelineError):
    """The generated metadata failed the deterministic SEO checks."""

    code = "metadata_validation_error"


class MetadataStage(BaseStage[PublishingInput, MetadataOutput]):
    """Generates the publication metadata for one approved Short."""

    stage_id = "metadata"
    name = "Metadata"
    description = "Generates the SEO title, description, tags, and visibility for one Short."
    version = "1.0.0"
    prompt_file = "06_metadata_generator.md"
    depends_on = ("topic", "script", "video_render")
    input_model = PublishingInput
    output_model = MetadataOutput

    async def execute(self, payload: PublishingInput) -> MetadataOutput:
        metadata = await generate_publishing_payload(
            self.context,
            prompt_file=self.prompt_file,
            payload=payload,
            temperature=_METADATA_TEMPERATURE,
            max_tokens=_METADATA_MAX_TOKENS,
            output_model=MetadataOutput,
        )
        self._validate(metadata)

        manifest = metadata.model_copy(
            update={
                "language": _LANGUAGE,
                "validation": ValidationDescriptor(
                    status=ValidationStatus.OK,
                    checks=[
                        "title_within_limit",
                        "primary_keyword_in_title",
                        "primary_keyword_in_description",
                        "tags_within_policy",
                        "hashtags_within_limit",
                    ],
                ),
            }
        )
        self._logger.info(
            "event=metadata.completed",
            topic=payload.topic,
            title=manifest.title,
            visibility=manifest.visibility.value,
            intent=manifest.search_intent,
            n_tags=len(manifest.tags),
        )
        return manifest

    # ------------------------------------------------------------ internals --

    def _validate(self, output: MetadataOutput) -> None:
        if len(output.title) > 100:
            raise MetadataValidationError(
                f"title exceeds the 100 character limit ({len(output.title)} chars)",
                detail={"title": output.title},
            )
        keyword = _normalize(output.primary_keyword)
        if not keyword:
            raise MetadataValidationError("primary_keyword is empty", detail={"title": output.title})
        if keyword not in _normalize(output.title):
            raise MetadataValidationError(
                "primary keyword must appear in the title",
                detail={"title": output.title, "keyword": output.primary_keyword},
            )
        if keyword not in _normalize(output.description):
            raise MetadataValidationError(
                "primary keyword must appear in the description",
                detail={"keyword": output.primary_keyword},
            )
        if not (_MIN_TAGS <= len(output.tags) <= _MAX_TAGS):
            raise MetadataValidationError(
                f"tags must be {_MIN_TAGS}-{_MAX_TAGS} search terms, got {len(output.tags)}",
                detail={"n_tags": len(output.tags)},
            )
        if len(output.hashtags) > _MAX_HASHTAGS:
            raise MetadataValidationError(
                f"hashtags must be at most {_MAX_HASHTAGS}, got {len(output.hashtags)}",
                detail={"n_hashtags": len(output.hashtags)},
            )


def _normalize(text: str) -> str:
    """Fold a phrase for matching: lowercase, drop everything non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", text.lower())