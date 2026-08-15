"""Publisher stage (prompt 16 + YouTube upload).

Consumes the rendered video from :class:`RenderManifestOutput`, the approved
publication metadata from :class:`MetadataOutput`, and the rendered
``thumbnail.png`` from :class:`ThumbnailManifestOutput`, uploads the Short to
YouTube through the :class:`~pr1me.providers.youtube.YouTubeProvider`, and
returns a single :class:`PublishManifestOutput`.

The stage owns the deterministic boundary: the fixed deliverable paths
(``short.mp4`` / ``thumbnail.png`` under the run directory), the pre-upload
asset checks, the tag policy (the platform has no separate hashtag field, so
the API ``tags`` list carries the declared tags and hashtags verbatim), the
category-id resolution, the dry-run payload, and the post-upload visibility
match. All transport, OAuth, retries, and timeouts live in the YouTube
provider.
"""

from __future__ import annotations

import os
from pathlib import Path

from pr1me.core.base_stage import BaseStage
from pr1me.core.context import StageContext
from pr1me.core.errors import PipelineError
from pr1me.models.common import ValidationDescriptor
from pr1me.models.contracts.publish import (
    PublishInput,
    PublishManifestOutput,
    PublishMetadata,
    PublishUploadPayload,
)
from pr1me.models.meta import ValidationStatus, Visibility
from pr1me.providers.youtube import (
    YouTubeProvider,
    YouTubeUploadRequest,
    youtube_category_id,
)

_ENV_OUTPUT_DIR = "PR1ME_PUBLISH_OUTPUT_DIR"
_ENV_DRY_RUN = "PR1ME_PUBLISH_DRY_RUN"

#: Deliverable names produced by the upstream render and thumbnail stages
#: (CLI contract; the overrides in PublishInput win when provided).
_FILENAME_VIDEO = "short.mp4"
_FILENAME_THUMBNAIL = "thumbnail.png"


class PublishValidationError(PipelineError):
    """The Short failed the deterministic pre- or post-publish checks."""

    code = "publish_validation_error"


class PublisherStage(BaseStage[PublishInput, PublishManifestOutput]):
    """Uploads one approved Short to YouTube and returns the publish manifest."""

    stage_id = "publisher"
    name = "Publisher"
    description = "Uploads one approved Short to YouTube and returns the publish manifest."
    version = "1.0.0"
    depends_on = ("video_render", "metadata", "thumbnail")
    input_model = PublishInput
    output_model = PublishManifestOutput

    def __init__(
        self,
        context: StageContext,
        *,
        youtube_provider: YouTubeProvider | None = None,
    ) -> None:
        self._youtube = youtube_provider
        super().__init__(context)

    async def execute(self, payload: PublishInput) -> PublishManifestOutput:
        settings = self.context.settings
        configured_dir = os.getenv(_ENV_OUTPUT_DIR)
        work_dir = Path(configured_dir) if configured_dir else settings.work_dir
        video_file = Path(payload.video_file) if payload.video_file else work_dir / _FILENAME_VIDEO
        thumbnail_file = (
            Path(payload.thumbnail_file) if payload.thumbnail_file else work_dir / _FILENAME_THUMBNAIL
        )
        self._require_assets((video_file, "video"), (thumbnail_file, "thumbnail"))

        metadata = payload.metadata_block()
        dry_run = payload.dry_run or os.getenv(_ENV_DRY_RUN, "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._logger.info(
            "event=publisher.started",
            title=metadata.title,
            visibility=metadata.visibility.value,
            dry_run=dry_run,
            video=str(video_file),
            thumbnail=str(thumbnail_file),
        )

        if dry_run:
            manifest = PublishManifestOutput(
                visibility=metadata.visibility,
                dry_run=True,
                upload_payload=self._upload_payload(metadata),
                validation=ValidationDescriptor(
                    status=ValidationStatus.OK,
                    checks=["file_ok", "metadata_ok", "dry_run_payload"],
                ),
            )
        else:
            manifest = await self._publish(metadata, video_file, thumbnail_file)

        self._logger.info(
            "event=publisher.completed",
            video_id=manifest.video_id,
            url=manifest.url,
            visibility=manifest.visibility.value if manifest.visibility else None,
            dry_run=manifest.dry_run,
            checks=manifest.validation.checks,
        )
        return manifest

    # ------------------------------------------------------------ internals --

    async def _publish(
        self,
        metadata: PublishMetadata,
        video_file: Path,
        thumbnail_file: Path,
    ) -> PublishManifestOutput:
        category_id = youtube_category_id(metadata.category)
        if not category_id:
            raise PublishValidationError(
                f"category {metadata.category!r} is not a known YouTube category id",
                detail={"category": metadata.category},
            )
        provider = self._youtube or YouTubeProvider()
        request = YouTubeUploadRequest(
            video_file=str(video_file),
            thumbnail_file=str(thumbnail_file),
            title=metadata.title,
            description=metadata.description,
            tags=[*metadata.tags, *metadata.hashtags],
            category_id=category_id,
            visibility=metadata.visibility.value,
            publish_at=metadata.publish_at if metadata.visibility is Visibility.SCHEDULED else None,
            made_for_kids=metadata.made_for_kids,
        )
        result = await provider.publish(request)

        if result.visibility != metadata.visibility.value:
            raise PublishValidationError(
                "published resource visibility does not match the intended visibility",
                detail={
                    "video_id": result.video_id,
                    "intended": metadata.visibility.value,
                    "actual": result.visibility,
                },
            )
        return PublishManifestOutput(
            video_id=result.video_id,
            url=result.url,
            visibility=metadata.visibility,
            published_at=result.published_at,
            dry_run=False,
            validation=ValidationDescriptor(
                status=ValidationStatus.OK,
                checks=["file_ok", "metadata_ok", "upload_ok", "visibility_match"],
            ),
        )

    @staticmethod
    def _upload_payload(metadata: PublishMetadata) -> PublishUploadPayload:
        """The exact intended upload payload (prompt 16 dry-run contract)."""
        return PublishUploadPayload(
            title=metadata.title,
            description=metadata.description,
            tags=[*metadata.tags, *metadata.hashtags],
            visibility=metadata.visibility,
            publish_at=metadata.publish_at if metadata.visibility is Visibility.SCHEDULED else None,
        )

    @staticmethod
    def _require_assets(*assets: tuple[Path, str]) -> None:
        """Fail fast when a deliverable is missing or empty before upload."""
        for path, label in assets:
            if not path.is_file():
                raise PublishValidationError(
                    f"{label} file missing before upload: {path}",
                    detail={"path": str(path)},
                )
            try:
                size = path.stat().st_size
            except OSError as exc:
                raise PublishValidationError(
                    f"cannot stat {label} file {path}: {exc}",
                    detail={"path": str(path)},
                ) from exc
            if size <= 0:
                raise PublishValidationError(
                    f"{label} file is empty before upload: {path}",
                    detail={"path": str(path)},
                )