"""Publisher stage contract (YouTube upload manifest).

The publisher consumes the video file produced by :class:`RenderManifestOutput`,
the publication metadata produced by :class:`MetadataOutput`, and the
``thumbnail.png`` produced by :class:`ThumbnailManifestOutput`, then returns a
single :class:`PublishManifestOutput`.

Because the pipeline runner flattens every upstream output into one dict,
:class:`PublishInput` in-lines the metadata stage's flat fields (title,
description, ...) and carries explicit ``video_file``/``thumbnail_file``
overrides for callers that resolve media paths themselves. The unique
thumbnail fields (``bytes``, ``width``, ``height``, ``checksum``, ``concept``)
ride along untouched and are ignored via ``extra``.

The JSON output shape mirrors prompt 16 (``prompts/16_publisher.md``) exactly:
``video_id``/``url`` are only set after a real upload and ``upload_payload``
records the exact intended configuration on a dry run.

These models are plain data: no transport, no OAuth, no filesystem access.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field, model_validator

from pr1me.models.common import StableModel, ValidationDescriptor
from pr1me.models.contracts.base import StageInput, StageOutput
from pr1me.models.contracts.publishing import SearchIntent, TargetAudience
from pr1me.models.meta import Visibility


class PublishMetadata(StableModel):
    """The exact publication configuration of one Short (prompt 06 shape).

    Reproducible by construction: every field mirrors the approved
    :class:`~pr1me.models.contracts.publishing.MetadataOutput` schema so the
    publisher never invents or rewrites creative content.
    """

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=5, max_length=10)
    hashtags: list[str] = Field(default_factory=list, max_length=3)
    category: str = Field(..., min_length=1)
    visibility: Visibility
    publish_at: str | None = Field(default=None)
    made_for_kids: bool = False
    primary_keyword: str = Field(..., min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    subtitle_language: str = Field("en", min_length=2, description="ISO 639-1 language code for subtitles")
    subtitle_timing: str | None = Field(default=None, description="Subtitle timing schema (start-end pairs in ms)")
    subtitle_file: str | None = Field(default=None, description="Path to generated SRT subtitle file")
    search_intent: SearchIntent
    target_audience: TargetAudience
    language: str = Field("en", min_length=1)


class PublishInput(StageInput):
    """Input for the publisher stage.

    ``video_file`` and ``thumbnail_file`` are optional overrides; when absent
    the stage resolves the rendered deliverables from the configured work
    directory. ``dry_run`` executes the full validation and returns the
    intended upload payload without uploading anything (prompt 16 contract).

    ``extra`` is ignored because the pipeline runner feeds the flattened
    outputs of every upstream stage alongside these fields.
    """

    model_config = ConfigDict(extra="ignore")

    video_file: str | None = Field(default=None)
    thumbnail_file: str | None = Field(default=None)
    dry_run: bool = False

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=5, max_length=10)
    hashtags: list[str] = Field(default_factory=list, max_length=3)
    category: str = Field(..., min_length=1)
    visibility: Visibility
    publish_at: str | None = Field(default=None)
    made_for_kids: bool = False
    primary_keyword: str = Field(..., min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: SearchIntent
    target_audience: TargetAudience
    language: str = Field("en", min_length=1)

    @model_validator(mode="after")
    def _schedule_requires_publish_at(self) -> PublishInput:
        if self.visibility is Visibility.SCHEDULED and not self.publish_at:
            raise ValueError("publish_at is required when visibility is 'scheduled'")
        return self

    def metadata_block(self) -> PublishMetadata:
        """The nested publication metadata block (prompt 16 input shape)."""
        return PublishMetadata(
            title=self.title,
            description=self.description,
            tags=self.tags,
            hashtags=self.hashtags,
            category=self.category,
            visibility=self.visibility,
            publish_at=self.publish_at,
            made_for_kids=self.made_for_kids,
            primary_keyword=self.primary_keyword,
            secondary_keywords=self.secondary_keywords,
            search_intent=self.search_intent,
            target_audience=self.target_audience,
            language=self.language,
        )


class PublishUploadPayload(StableModel):
    """The exact intended upload payload (returned on dry runs)."""

    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    tags: list[str] = Field(..., min_length=1)
    visibility: Visibility
    publish_at: str | None = Field(default=None)


class PublishManifestOutput(StageOutput):
    """The publication report for one uploaded Short (prompt 16 output shape).

    ``video_id`` and ``url`` are present only after a real upload (``dry_run``
    false); they stay ``None`` on a dry run. ``validation`` is ``ok`` only when
    every deterministic publish check -- including the post-upload visibility
    match -- passed.
    """

    video_id: str | None = Field(default=None, min_length=1)
    url: str | None = Field(default=None)
    visibility: Visibility | None = Field(default=None)
    published_at: str | None = Field(default=None)
    dry_run: bool = False
    upload_payload: PublishUploadPayload | None = Field(default=None)
    validation: ValidationDescriptor = Field(default_factory=ValidationDescriptor)