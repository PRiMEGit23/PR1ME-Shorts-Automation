"""YouTube publishing provider (OAuth credentials + resumable upload).

Everything that places one Short on YouTube lives in this module:

- :class:`YouTubeBackend` -- the transport seam for the YouTube Data API
- :class:`HTTPYouTubeBackend` -- a concrete backend implementing the resumable
  upload protocol (video init -> media PUT -> thumbnail set -> verify)
- :class:`YouTubeProvider` -- OAuth token handling (direct access token or
  refresh-token renewal), the retry policy, the per-call timeout, structured
  logging, and typed response building

The provider is transport-only and concept-agnostic: it knows nothing about
publish manifests or metadata stages. The stage layer builds the exact snippet
and status configuration and decides which files to publish. It deliberately
does **not** extend :class:`~pr1me.providers.base_provider.BaseProvider`,
which is the LLM completion interface; uploading is a different capability.
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, Field

from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.core.logging import get_logger
from pr1me.providers.voice import _env_float, _env_int, _first

_ENV_PROVIDER = "PR1ME_YOUTUBE_PROVIDER"
_ENV_ACCESS_TOKEN = "PR1ME_YOUTUBE_ACCESS_TOKEN"
_ENV_REFRESH_TOKEN = "PR1ME_YOUTUBE_REFRESH_TOKEN"
_ENV_CLIENT_ID = "PR1ME_YOUTUBE_CLIENT_ID"
_ENV_CLIENT_SECRET = "PR1ME_YOUTUBE_CLIENT_SECRET"
_ENV_BASE_URL = "PR1ME_YOUTUBE_BASE_URL"
_ENV_TOKEN_URI = "PR1ME_YOUTUBE_TOKEN_URI"
_ENV_TIMEOUT = "PR1ME_YOUTUBE_TIMEOUT_SECONDS"
_ENV_MAX_RETRIES = "PR1ME_YOUTUBE_MAX_RETRIES"

_DEFAULT_PROVIDER = "http"
_DEFAULT_BASE_URL = "https://www.googleapis.com"
_DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
_DEFAULT_VIDEO_CONTENT_TYPE = "video/mp4"
_DEFAULT_IMAGE_CONTENT_TYPE = "image/png"

_DEFAULT_REQUEST_TIMEOUT = 60.0
_DEFAULT_TIMEOUT = 600.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 30.0

#: HTTP statuses that are safe to retry (nothing to fix client-side).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

R = TypeVar("R")

#: Renew the access token this many seconds before it actually expires.
_TOKEN_RENEW_MARGIN_SECONDS = 60.0

#: Channel category names -> YouTube Data API numeric category ids.
#: Deterministic channel policy: unknown names resolve to ``None`` and the
#: publish fails closed before any upload starts.
_CATEGORY_IDS: dict[str, str] = {
    "Science & Technology": "28",
    "Education": "27",
    "Howto & Style": "26",
    "Film & Animation": "1",
    "Entertainment": "24",
    "Music": "25",
}


def youtube_category_id(name: str) -> str | None:
    """Map a channel category name to the YouTube API ``categoryId``.

    Numeric identifiers pass through unchanged; unknown names return ``None``
    so the caller can abort the publish before any upload starts.
    """
    candidate = name.strip()
    if candidate.isdigit():
        return candidate
    return _CATEGORY_IDS.get(candidate)


class YouTubeProviderError(PipelineError):
    """Base class for every YouTube publishing provider failure."""

    code = "youtube_provider_error"


class YouTubeAuthError(YouTubeProviderError):
    """The YouTube OAuth credentials are invalid or lack upload permission."""

    code = "youtube_auth_error"


class YouTubeUploadError(YouTubeProviderError):
    """The YouTube Data API rejected or could not serve an upload step."""

    code = "youtube_upload_error"

    def __init__(self, message: str, *, detail: Any | None = None, retryable: bool = False) -> None:
        super().__init__(message, detail=detail)
        self.retryable = retryable


class YouTubeTimeoutError(YouTubeProviderError):
    """A YouTube API call did not complete within the configured timeout."""

    code = "youtube_timeout_error"


# ------------------------------------------------------------------ typed API -


class YouTubeUploadRequest(BaseModel):
    """A provider-agnostic YouTube publish request for one Short."""

    video_file: str = Field(..., min_length=1)
    thumbnail_file: str | None = Field(default=None, min_length=1)
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=20)
    category_id: str = Field(..., min_length=1)
    visibility: str = Field(..., min_length=1)
    publish_at: str | None = Field(default=None)
    made_for_kids: bool = False


class YouTubePublishResult(BaseModel):
    """One published Short reported back by YouTube (verified)."""

    video_id: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    visibility: str = Field(..., min_length=1)
    published_at: str | None = None
    upload_status: str = "uploaded"


# ------------------------------------------------------------------- backend --


class YouTubeBackend(ABC):
    """Transport seam for the YouTube Data API.

    Concrete backends (Google, a mock, a proxy) implement the four protocol
    steps; the provider layer adds OAuth, retries, timeouts, and typed
    responses on top.
    """

    name: str = "base"

    @abstractmethod
    async def initialize_upload(
        self,
        *,
        access_token: str,
        metadata: dict[str, Any],
        media_size: int,
        media_type: str,
    ) -> str:
        """Start a resumable upload session; return its upload URI."""

    @abstractmethod
    async def upload_media(
        self,
        *,
        upload_uri: str,
        data: bytes,
        media_type: str,
    ) -> dict[str, Any]:
        """PUT the media bytes into the resumable session; return the response."""

    @abstractmethod
    async def set_thumbnail(
        self,
        *,
        access_token: str,
        video_id: str,
        data: bytes,
        image_type: str,
    ) -> dict[str, Any]:
        """Attach the thumbnail image to the published video."""

    @abstractmethod
    async def fetch_video(
        self,
        *,
        access_token: str,
        video_id: str,
    ) -> dict[str, Any]:
        """Fetch one published resource (snippet + status)."""

    @abstractmethod
    async def refresh_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Exchange a refresh token for a fresh access token."""

    async def close(self) -> None:
        """Release any resources owned by this backend."""


class HTTPYouTubeBackend(YouTubeBackend):
    """Concrete backend speaking the YouTube Data API upload protocol.

    Implements the canonical resumable flow: ``POST`` video metadata for a
    session URI, ``PUT`` the media bytes into that URI, ``POST`` the thumbnail,
    then ``GET`` the published resource for verification. Transport errors and
    non-2xx statuses raise :class:`YouTubeAuthError` (401/403) or
    :class:`YouTubeUploadError` (everything else); the retry policy lives in
    :class:`YouTubeProvider`.
    """

    name = "http"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token_uri: str | None = None,
        request_timeout: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv(_ENV_BASE_URL) or _DEFAULT_BASE_URL).rstrip("/")
        self._token_uri = token_uri or os.getenv(_ENV_TOKEN_URI) or _DEFAULT_TOKEN_URI
        self._request_timeout = _first(request_timeout, None, _DEFAULT_REQUEST_TIMEOUT)
        self._http_client = http_client
        self._owns_client = http_client is None

    # ------------------------------------------------------------ protocol ----

    async def initialize_upload(
        self,
        *,
        access_token: str,
        metadata: dict[str, Any],
        media_size: int,
        media_type: str,
    ) -> str:
        url = f"{self._base_url}/upload/youtube/v3/videos"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": media_type,
            "X-Upload-Content-Length": str(media_size),
        }
        try:
            response = await self._ensure_client().post(
                url,
                params={"uploadType": "resumable", "part": "snippet,status"},
                json=metadata,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(
                f"youtube transport error while starting the upload: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        location = str(response.headers.get("Location") or "")
        if response.status_code != 200 or not location:
            raise self._status_error("starting the upload", response, note="missing session Location header")
        return location

    async def upload_media(
        self,
        *,
        upload_uri: str,
        data: bytes,
        media_type: str,
    ) -> dict[str, Any]:
        headers = {"Content-Type": media_type}
        try:
            response = await self._ensure_client().put(upload_uri, content=data, headers=headers)
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(
                f"youtube transport error while uploading the media: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise self._status_error("uploading the video", response)
        return response.json()

    async def set_thumbnail(
        self,
        *,
        access_token: str,
        video_id: str,
        data: bytes,
        image_type: str,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/upload/youtube/v3/thumbnails/set"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": image_type}
        try:
            response = await self._ensure_client().post(
                url,
                params={"videoId": video_id, "uploadType": "media"},
                content=data,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(
                f"youtube transport error while setting the thumbnail: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise self._status_error("setting the thumbnail", response)
        return response.json()

    async def fetch_video(
        self,
        *,
        access_token: str,
        video_id: str,
    ) -> dict[str, Any]:
        url = f"{self._base_url}/youtube/v3/videos"
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = await self._ensure_client().get(
                url,
                params={"part": "snippet,status", "id": video_id},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(
                f"youtube transport error while verifying the video: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise self._status_error("verifying the video", response)
        items = response.json().get("items") or []
        if not items:
            raise YouTubeUploadError(
                f"published video {video_id} was not found for verification",
                detail={"video_id": video_id},
                retryable=False,
            )
        return items[0]

    async def refresh_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> dict[str, Any]:
        form = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        try:
            response = await self._ensure_client().post(self._token_uri, data=form)
        except httpx.HTTPError as exc:
            raise YouTubeUploadError(
                f"youtube transport error while renewing the token: {exc}",
                detail={"exc_type": type(exc).__name__},
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise self._status_error("renewing the access token", response)
        return response.json()

    async def close(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()

    # ------------------------------------------------------------ internals --

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._request_timeout)
        return self._http_client

    def _status_error(
        self,
        step: str,
        response: httpx.Response,
        *,
        note: str | None = None,
    ) -> YouTubeProviderError:
        status = response.status_code
        detail: dict[str, Any] = {"status": status, "body": response.text[:300]}
        if note:
            detail["note"] = note
        if status in (401, 403):
            return YouTubeAuthError(
                f"youtube {step} rejected the credentials (HTTP {status})",
                detail=detail,
            )
        return YouTubeUploadError(
            f"youtube {step} returned HTTP {status}",
            detail=detail,
            retryable=status in _RETRYABLE_STATUSES,
        )


_AVAILABLE_BACKENDS: dict[str, type[YouTubeBackend]] = {"http": HTTPYouTubeBackend}


def build_youtube_backend(provider: str | None = None) -> YouTubeBackend:
    """Instantiate the configured YouTube backend from ``PR1ME_YOUTUBE_PROVIDER``."""
    name = provider or os.getenv(_ENV_PROVIDER) or _DEFAULT_PROVIDER
    try:
        cls = _AVAILABLE_BACKENDS[name]
    except KeyError as exc:
        raise ProviderNotConfiguredError(
            f"youtube provider {name!r} is not available; available: {sorted(_AVAILABLE_BACKENDS)}"
        ) from exc
    return cls()


# ------------------------------------------------------------------ provider --


class YouTubeProvider:
    """Async client for the YouTube Data API.

    Configuration comes from explicit constructor arguments or the
    ``PR1ME_YOUTUBE_*`` environment variables. OAuth uses the configured
    access token directly, or renews it from a refresh token when client
    credentials are supplied. The actual API transport is injected as a
    :class:`YouTubeBackend` (never hardcoded here); a missing configuration
    fails fast at construction so a misconfigured publish never starts.
    """

    name = "youtube"

    def __init__(
        self,
        *,
        backend: YouTubeBackend | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._backend = backend if backend is not None else HTTPYouTubeBackend(http_client=http_client)
        self._access_token = access_token or os.getenv(_ENV_ACCESS_TOKEN) or ""
        self._refresh_token = refresh_token or os.getenv(_ENV_REFRESH_TOKEN)
        self._client_id = client_id or os.getenv(_ENV_CLIENT_ID)
        self._client_secret = client_secret or os.getenv(_ENV_CLIENT_SECRET)
        self._timeout = _first(timeout_seconds, _env_float(_ENV_TIMEOUT), _DEFAULT_TIMEOUT)
        self._max_retries = _first(max_retries, _env_int(_ENV_MAX_RETRIES), _DEFAULT_MAX_RETRIES)
        self._retry_base_delay = _first(retry_base_delay, None, _RETRY_BASE_DELAY)
        self._retry_max_delay = _first(retry_max_delay, None, _RETRY_MAX_DELAY)
        self._expires_at: float | None = None
        self._logger = get_logger("pr1me.providers.youtube", backend=self._backend.name)
        if not self._access_token and not self._can_refresh():
            raise ProviderNotConfiguredError(
                f"no YouTube access token configured; set {_ENV_ACCESS_TOKEN} or pass access_token="
            )

    # ------------------------------------------------------------ entry ------

    async def publish(self, request: YouTubeUploadRequest) -> YouTubePublishResult:
        """Publish one Short exactly as configured and return the verified result.

        The media is uploaded through the resumable protocol, the thumbnail is
        attached when supplied, and the live resource is re-fetched to confirm
        its state. Fail-fast: no partial result is ever returned.
        """
        video_bytes = await asyncio.to_thread(self._read_asset, request.video_file, kind="video")
        thumbnail_bytes: bytes | None = None
        if request.thumbnail_file:
            thumbnail_bytes = await asyncio.to_thread(
                self._read_asset, request.thumbnail_file, kind="thumbnail"
            )
        token = await self._ensure_token()
        metadata = self._build_metadata(request)
        content_type = _DEFAULT_VIDEO_CONTENT_TYPE

        self._logger.info(
            "event=youtube.publish.started",
            title=request.title,
            bytes=len(video_bytes),
            thumbnail=thumbnail_bytes is not None,
            visibility=request.visibility,
        )
        upload_uri = await self._retried(
            lambda: self._backend.initialize_upload(
                access_token=token,
                metadata=metadata,
                media_size=len(video_bytes),
                media_type=content_type,
            ),
            label="initialize",
        )
        raw = await self._retried(
            lambda: self._backend.upload_media(
                upload_uri=upload_uri,
                data=video_bytes,
                media_type=content_type,
            ),
            label="upload",
        )
        result = self._parse_upload(raw)
        if thumbnail_bytes is not None:
            await self._retried(
                lambda: self._backend.set_thumbnail(
                    access_token=token,
                    video_id=result.video_id,
                    data=thumbnail_bytes,
                    image_type=_DEFAULT_IMAGE_CONTENT_TYPE,
                ),
                label="thumbnail",
            )
        verified = await self._retried(
            lambda: self._backend.fetch_video(access_token=token, video_id=result.video_id),
            label="verify",
        )
        result = self._apply_verified(result, verified)
        self._logger.info(
            "event=youtube.publish.completed",
            video_id=result.video_id,
            url=result.url,
            visibility=result.visibility,
            published_at=result.published_at,
        )
        return result

    async def close(self) -> None:
        """Release the resources owned by the configured backend."""
        await self._backend.close()

    @property
    def provider_name(self) -> str:
        """Identifier of the configured YouTube backend (for provenance)."""
        return self._backend.name

    # -------------------------------------------------------------- auth -----

    async def _ensure_token(self) -> str:
        if self._can_refresh() and (not self._access_token or self._token_expired()):
            await self._refresh()
        if not self._access_token:
            raise ProviderNotConfiguredError(
                f"no YouTube access token configured; set {_ENV_ACCESS_TOKEN} or pass access_token="
            )
        return self._access_token

    async def _refresh(self) -> None:
        if not self._can_refresh():
            raise ProviderNotConfiguredError(
                "YouTube token refresh requires the refresh token, client id, and client secret"
            )
        raw = await self._retried(
            lambda: self._backend.refresh_token(
                client_id=self._client_id or "",
                client_secret=self._client_secret or "",
                refresh_token=self._refresh_token or "",
            ),
            label="token",
        )
        token = str(raw.get("access_token") or "")
        if not token:
            raise YouTubeAuthError("the YouTube token endpoint returned no access_token")
        self._access_token = token
        self._store_expiry(raw.get("expires_in"))

    def _store_expiry(self, expires_in: Any) -> None:
        try:
            seconds = float(expires_in)
        except (TypeError, ValueError):
            self._expires_at = None
            return
        self._expires_at = time.monotonic() + seconds - _TOKEN_RENEW_MARGIN_SECONDS

    def _token_expired(self) -> bool:
        return self._expires_at is not None and time.monotonic() >= self._expires_at

    def _can_refresh(self) -> bool:
        return bool(self._refresh_token and self._client_id and self._client_secret)

    # ------------------------------------------------------------ retries ----

    async def _retried(self, action: Callable[[], Awaitable[R]], *, label: str) -> R:
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return await asyncio.wait_for(action(), timeout=self._timeout)
            except TimeoutError:
                last_error = YouTubeTimeoutError(
                    f"youtube {label} did not complete within {self._timeout:g}s",
                    detail={"step": label},
                )
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason="timeout")
            except YouTubeAuthError as exc:
                raise exc
            except YouTubeUploadError as exc:
                last_error = exc
                if not exc.retryable:
                    raise exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=exc.message)
        if isinstance(last_error, YouTubeProviderError):
            raise last_error
        raise YouTubeUploadError(f"youtube {label} failed: {last_error}") from last_error

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=youtube.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    # ------------------------------------------------------------ internals --

    @staticmethod
    def _read_asset(file: str, *, kind: str) -> bytes:
        path = Path(file)
        if not path.is_file():
            raise YouTubeUploadError(
                f"{kind} file missing before upload: {path}",
                detail={"file": file},
                retryable=False,
            )
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise YouTubeUploadError(
                f"cannot read {kind} file {path}: {exc}",
                detail={"file": file},
                retryable=False,
            ) from exc
        if not data:
            raise YouTubeUploadError(
                f"{kind} file is empty before upload: {path}",
                detail={"file": file},
                retryable=False,
            )
        return data

    @staticmethod
    def _build_metadata(request: YouTubeUploadRequest) -> dict[str, Any]:
        snippet: dict[str, Any] = {
            "title": request.title,
            "description": request.description,
            "categoryId": request.category_id,
        }
        if request.tags:
            snippet["tags"] = request.tags
        status: dict[str, Any] = {
            "privacyStatus": request.visibility,
            "selfDeclaredMadeForKids": request.made_for_kids,
        }
        if request.publish_at:
            status["publishAt"] = request.publish_at
        return {"snippet": snippet, "status": status}

    @staticmethod
    def _parse_upload(raw: dict[str, Any]) -> YouTubePublishResult:
        video_id = str(raw.get("id") or "").strip()
        if not video_id:
            raise YouTubeUploadError(
                "the video upload response carried no video id",
                detail={"status": raw.get("status")},
                retryable=False,
            )
        status = raw.get("status") or {}
        visibility = str(status.get("privacyStatus") or "")
        if not visibility:
            raise YouTubeUploadError(
                "the video upload response carried no privacyStatus",
                detail={"video_id": video_id},
                retryable=False,
            )
        return YouTubePublishResult(
            video_id=video_id,
            url=f"https://youtu.be/{video_id}",
            visibility=visibility,
            upload_status=str(status.get("uploadStatus") or "uploaded"),
        )

    @staticmethod
    def _apply_verified(result: YouTubePublishResult, verified: dict[str, Any]) -> YouTubePublishResult:
        status = verified.get("status") or {}
        snippet = verified.get("snippet") or {}
        visibility = str(status.get("privacyStatus") or "")
        if not visibility:
            raise YouTubeUploadError(
                "the verified resource carries no privacyStatus",
                detail={"video_id": result.video_id},
                retryable=False,
            )
        published = snippet.get("publishedAt")
        return result.model_copy(
            update={
                "visibility": visibility,
                "published_at": str(published) if published else None,
            }
        )