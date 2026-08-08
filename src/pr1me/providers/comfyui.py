"""ComfyUI image provider (local ComfyUI HTTP API).

Everything that talks to a local ComfyUI server lives here:

- workflow template loading from configuration (never hardcoded)
- prompt variable injection into the typed workflow graph
- queueing (``POST /prompt``)
- waiting for completion (polling ``GET /history``)
- retrieving generated image files (``GET /view``)
- structured logging, retries, and timeouts

The provider is transport-only and concept-agnostic: it knows nothing about
visual plans or shots. The stage layer builds prompt variables and decides
where image files land. It deliberately does **not** extend
:class:`~pr1me.providers.base_provider.BaseProvider`, which is the LLM
completion interface; image generation is a different capability.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import random
import struct
from collections.abc import Mapping
from pathlib import Path
from time import monotonic
from typing import Any

import httpx
from pydantic import BaseModel, Field

from pr1me.core.errors import PipelineError, ProviderNotConfiguredError
from pr1me.core.logging import get_logger

_DEFAULT_BASE_URL = "http://127.0.0.1:8188"
_ENV_BASE_URL = "PR1ME_COMFYUI_BASE_URL"
_ENV_WORKFLOW = "PR1ME_COMFYUI_WORKFLOW"
_ENV_TIMEOUT = "PR1ME_COMFYUI_TIMEOUT_SECONDS"
_ENV_POLL_INTERVAL = "PR1ME_COMFYUI_POLL_INTERVAL"
_ENV_MAX_RETRIES = "PR1ME_COMFYUI_MAX_RETRIES"

#: HTTP statuses that are safe to retry (nothing to fix client-side).
_RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}

_DEFAULT_REQUEST_TIMEOUT = 30.0
_DEFAULT_EXECUTION_TIMEOUT = 600.0
_DEFAULT_POLL_INTERVAL = 1.0
_DEFAULT_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 30.0


class ComfyUIError(PipelineError):
    """Base class for every ComfyUI provider failure."""

    code = "comfyui_error"


class ComfyUIQueueError(ComfyUIError):
    """The workflow could not be submitted to the ComfyUI server."""

    code = "comfyui_queue_error"


class ComfyUIExecutionError(ComfyUIError):
    """A queued workflow failed or aborted while executing."""

    code = "comfyui_execution_error"


class ComfyUITimeoutError(ComfyUIError):
    """A queued workflow did not finish within the configured timeout."""

    code = "comfyui_timeout_error"


class ComfyUIWorkflowError(ComfyUIError):
    """The workflow template could not be loaded or parsed."""

    code = "comfyui_workflow_error"


# ------------------------------------------------------------------ typed API -


class ComfyUIOutputImage(BaseModel):
    """One generated image as reported by the ComfyUI server."""

    filename: str
    subfolder: str = ""
    image_type: str = "output"
    node_id: int | None = None


class ComfyUIQueueResponse(BaseModel):
    """Typed result of ``POST /prompt``."""

    prompt_id: str
    number: int = 0
    node_errors: dict[str, Any] = Field(default_factory=dict)


class ComfyUIExecution(BaseModel):
    """Executed state for one prompt, from ``GET /history``."""

    prompt_id: str
    completed: bool = False
    status_str: str | None = None
    images: list[ComfyUIOutputImage] = Field(default_factory=list)
    error: str | None = None


class ComfyUIRender(BaseModel):
    """One finalized render saved to disk."""

    file: str
    prompt_id: str
    width: int
    height: int


# ------------------------------------------------------------------ injection -


def inject_variables(workflow: Mapping[str, Any], variables: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-copy ``workflow`` and inject ``variables`` into its node inputs.

    Two rules apply to each string input value:

    - when the whole value is a placeholder (``"{key}"``), the variable is
      injected with its native type (so numeric nodes receive ints/floats);
    - embedded placeholders inside a larger string are substituted textually.

    Unknown placeholders are left intact so callers get loud validation errors
    instead of silently losing variables.
    """
    graph: dict[str, Any] = copy.deepcopy(dict(workflow))
    for node in graph.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in list(inputs.items()):
            if isinstance(value, str):
                placeholder = _whole_placeholder(value)
                if placeholder is not None and placeholder in variables:
                    inputs[key] = variables[placeholder]
                else:
                    inputs[key] = _embedded_substitute(value, variables)
    return graph


def _whole_placeholder(value: str) -> str | None:
    if len(value) >= 3 and value.startswith("{") and value.endswith("}"):
        inner = value[1:-1]
        if inner.isidentifier():
            return inner
    return None


def _embedded_substitute(text: str, variables: Mapping[str, Any]) -> str:
    if "{" not in text:
        return text
    for name, value in variables.items():
        if name.isidentifier():
            text = text.replace(f"{{{name}}}", str(value))
    return text


def load_workflow_file(path: str | Path) -> dict[str, Any]:
    """Parse a workflow JSON file, raising :class:`ComfyUIWorkflowError`."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ComfyUIWorkflowError(f"cannot load workflow {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ComfyUIWorkflowError(f"workflow {path} must be a JSON object")
    return data


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Return ``(width, height)`` for PNG bytes, else ``(0, 0)``.

    PNG dimensions live in the IHDR chunk directly after the 8-byte signature:
    big-endian uint32 width (offset 16) and height (offset 20).
    """
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return 0, 0
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def parse_queue_response(data: Any) -> ComfyUIQueueResponse:
    """Convert a ``POST /prompt`` body into a typed queue response."""
    if not isinstance(data, dict):
        raise ComfyUIQueueError(f"ComfyUI returned an unexpected response shape: {str(data)[:300]}")
    node_errors = data.get("node_errors")
    node_errors = node_errors if isinstance(node_errors, dict) else {}
    if node_errors:
        raise ComfyUIQueueError(
            "ComfyUI rejected the workflow with node errors",
            detail={"node_errors": {str(k): str(v) for k, v in node_errors.items()}},
        )
    prompt_raw = data.get("prompt_id")
    if not prompt_raw:
        raise ComfyUIQueueError(
            "ComfyUI response is missing prompt_id",
            detail={"body": str(data)[:300]},
        )
    return ComfyUIQueueResponse(
        prompt_id=str(prompt_raw),
        number=int(data.get("number", 0) or 0),
        node_errors=node_errors,
    )


def parse_history(prompt_id: str, record: dict[str, Any]) -> ComfyUIExecution:
    """Convert one ``/history`` record into a typed execution status."""
    status = record.get("status")
    status = status if isinstance(status, dict) else {}
    images: list[ComfyUIOutputImage] = []
    outputs = record.get("outputs")
    if isinstance(outputs, dict):
        for node_id, node_out in outputs.items():
            if not isinstance(node_out, dict):
                continue
            for image in node_out.get("images") or []:
                if isinstance(image, dict) and image.get("filename"):
                    images.append(
                        ComfyUIOutputImage(
                            filename=str(image["filename"]),
                            subfolder=str(image.get("subfolder", "")),
                            image_type=str(image.get("type", "output")),
                            node_id=int(node_id) if str(node_id).isdigit() else None,
                        )
                    )
    error: str | None = _extract_error(status)
    return ComfyUIExecution(
        prompt_id=prompt_id,
        completed=bool(status.get("completed")),
        status_str=status.get("status_str"),
        images=images,
        error=error,
    )


def _extract_error(status: dict[str, Any]) -> str | None:
    for message in status.get("messages") or []:
        if isinstance(message, list) and message and message[0] == "execution_error":
            return _narrow_error(message)
    exceptions = status.get("exceptions")
    if exceptions:
        return str(exceptions)[:300]
    return None


def _narrow_error(message: list[Any]) -> str:
    if len(message) < 2:
        return "execution error"
    payload = message[1]
    if isinstance(payload, dict):
        reason = payload.get("exception_message")
        if reason:
            return str(reason)[:500]
        node_type = payload.get("node_type")
        if node_type:
            return f"{node_type} raised during execution"
    return str(payload)[:500]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _env_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _first(*values: object) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


# ------------------------------------------------------------------ provider -


class ComfyUIProvider:
    """Async client for a local ComfyUI server.

    Configuration comes from explicit constructor arguments or the
    ``PR1ME_COMFYUI_*`` environment variables. When ``workflow_file`` is not
    supplied it defaults to ``<repo_root>/workflows/comfyui.json`` so a workflow
    is always loadable from configuration.
    """

    name = "comfyui"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        workflow_file: str | Path | None = None,
        timeout_seconds: float | None = None,
        poll_interval: float | None = None,
        request_timeout: float | None = None,
        max_retries: int | None = None,
        retry_base_delay: float | None = None,
        retry_max_delay: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (base_url or os.getenv(_ENV_BASE_URL) or _DEFAULT_BASE_URL).rstrip("/")
        self._workflow_file = Path(workflow_file) if workflow_file is not None else None
        if self._workflow_file is not None and not self._workflow_file.is_file():
            raise ProviderNotConfiguredError(f"ComfyUI workflow file not found: {self._workflow_file}")
        self._timeout = _first(timeout_seconds, _env_float(_ENV_TIMEOUT), _DEFAULT_EXECUTION_TIMEOUT)
        self._poll_interval = _first(poll_interval, _env_float(_ENV_POLL_INTERVAL), _DEFAULT_POLL_INTERVAL)
        self._request_timeout = _first(request_timeout, None, _DEFAULT_REQUEST_TIMEOUT)
        self._max_retries = _first(max_retries, _env_int(_ENV_MAX_RETRIES), _DEFAULT_MAX_RETRIES)
        self._retry_base_delay = _first(retry_base_delay, None, _RETRY_BASE_DELAY)
        self._retry_max_delay = _first(retry_max_delay, None, _RETRY_MAX_DELAY)
        self._http_client = http_client
        self._owns_client = http_client is None
        self._logger = get_logger(
            "pr1me.providers.comfyui",
            base_url=self._base_url,
            workflow=str(self._workflow_file),
        )

    # ------------------------------------------------------------- entry ----

    async def render(
        self,
        variables: dict[str, Any],
        *,
        output_dir: str | Path,
        workflow: Mapping[str, Any] | None = None,
    ) -> list[ComfyUIRender]:
        """Queue the workflow, wait for completion, and save every image.

        :param variables: prompt variables injected into the workflow template.
        :param output_dir: destination folder (created on demand).
        :param workflow: optional explicit graph; defaults to the configured
            template.
        :raises ComfyUIError: transport, queue, execution, or timeout failures.
            Fail-fast: no partial result is ever returned.
        """
        graph = workflow if workflow is not None else await self.load_workflow()
        decorated = inject_variables(graph, variables)
        queued = await self.queue(decorated)
        self._logger.info(
            "event=comfyui.queued",
            prompt_id=queued.prompt_id,
            number=queued.number,
            n_variables=len(variables),
        )
        status = await self.wait(queued.prompt_id)
        if status.error:
            raise ComfyUIExecutionError(
                f"workflow {queued.prompt_id} failed: {status.error}",
                detail={"prompt_id": queued.prompt_id},
            )
        if status.completed and status.images:
            rendered = []
            for image in status.images:
                rendered.append(
                    await self._download(image, output_dir=output_dir, prompt_id=queued.prompt_id)
                )
            self._logger.info(
                "event=comfyui.completed",
                prompt_id=queued.prompt_id,
                n_images=len(rendered),
            )
            return rendered
        raise ComfyUIExecutionError(f"workflow {queued.prompt_id} completed without any images")

    async def queue(self, workflow: Mapping[str, Any]) -> ComfyUIQueueResponse:
        """Submit a workflow graph and return the server-assigned prompt id."""
        return await self._retried_post("/prompt", {"prompt": workflow})

    async def load_workflow(self) -> dict[str, Any]:
        """Load and parse the configured workflow template."""
        if self._workflow_file is None:
            raise ComfyUIWorkflowError("no workflow template configured; set PR1ME_COMFYUI_WORKFLOW")
        return await asyncio.to_thread(load_workflow_file, self._workflow_file)

    async def wait(self, prompt_id: str) -> ComfyUIExecution:
        """Poll ``/history`` until the workflow finishes or the timeout passes."""
        deadline = monotonic() + self._timeout
        while True:
            history = await self._retried_get(f"/history/{prompt_id}")
            record = history.get(prompt_id) if isinstance(history, dict) else None
            if isinstance(record, dict):
                status = parse_history(prompt_id, record)
                if status.completed:
                    return status
            if monotonic() >= deadline:
                raise ComfyUITimeoutError(f"workflow {prompt_id} did not complete within {self._timeout}s")
            await asyncio.sleep(self._poll_interval)

    async def download(self, image: ComfyUIOutputImage, *, output_dir: str | Path) -> ComfyUIRender:
        """Fetch one generated image file and store it under ``output_dir``."""
        return await self._download(image, output_dir=output_dir, prompt_id="")

    async def _download(
        self,
        image: ComfyUIOutputImage,
        *,
        output_dir: str | Path,
        prompt_id: str,
    ) -> ComfyUIRender:
        dest = Path(output_dir)
        await asyncio.to_thread(_ensure_dir, dest)
        params = {
            "filename": image.filename,
            "subfolder": image.subfolder,
            "type": image.image_type,
        }
        data = await self._retried_get_bytes("/view", params)
        target = dest / image.filename
        await asyncio.to_thread(target.write_bytes, data)
        width, height = png_dimensions(data)
        self._logger.info(
            "event=comfyui.image_saved",
            filename=image.filename,
            bytes=len(data),
            width=width,
            height=height,
        )
        return ComfyUIRender(file=str(target), prompt_id=prompt_id, width=width, height=height)

    async def close(self) -> None:
        """Release the resources owned by this provider."""
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()

    @property
    def workflow_name(self) -> str:
        """Identifier of the configured workflow template (for provenance)."""
        if self._workflow_file is not None:
            return self._workflow_file.name
        return ""

    # -------------------------------------------------------------- transport

    def _ensure_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self._request_timeout)
        return self._http_client

    def _should_retry_attempt(self, attempt: int) -> bool:
        return attempt < self._max_retries

    async def _backoff(self, attempt: int, *, reason: str) -> None:
        delay = min(self._retry_base_delay * (2 ** (attempt - 1)), self._retry_max_delay)
        jittered = delay * (0.5 + random.random())
        self._logger.warning(
            "event=comfyui.retry",
            attempt=attempt,
            reason=reason,
            delay_ms=round(jittered * 1000, 1),
        )
        await asyncio.sleep(jittered)

    async def _retried_post(self, path: str, payload: dict[str, Any]) -> ComfyUIQueueResponse:
        client = self._ensure_client()
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.post(f"{self._base_url}{path}", json=payload)
            except httpx.HTTPError as exc:
                last_error = exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=f"transport {type(exc).__name__}")
                continue
            if response.status_code in (200, 201):
                return parse_queue_response(response.json())
            last_error = ComfyUIQueueError(
                f"ComfyUI {path} returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
            )
            if response.status_code not in _RETRYABLE_STATUSES or not self._should_retry_attempt(attempt):
                break
            await self._backoff(attempt, reason=f"http {response.status_code}")
        if isinstance(last_error, ComfyUIError):
            raise last_error
        raise ComfyUIQueueError(
            f"ComfyUI request failed: {last_error}",
            detail={"exc_type": type(last_error).__name__},
        ) from last_error

    async def _retried_get(self, path: str) -> Any:
        client = self._ensure_client()
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.get(f"{self._base_url}{path}")
            except httpx.HTTPError as exc:
                last_error = exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=f"transport {type(exc).__name__}")
                continue
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, dict) else {}
            last_error = ComfyUIExecutionError(
                f"ComfyUI {path} returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
            )
            if response.status_code not in _RETRYABLE_STATUSES or not self._should_retry_attempt(attempt):
                break
            await self._backoff(attempt, reason=f"http {response.status_code}")
        if isinstance(last_error, ComfyUIError):
            raise last_error
        raise ComfyUIExecutionError(
            f"ComfyUI request failed: {last_error}",
            detail={"exc_type": type(last_error).__name__},
        ) from last_error

    async def _retried_get_bytes(self, path: str, params: dict[str, str]) -> bytes:
        client = self._ensure_client()
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.get(f"{self._base_url}{path}", params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                if not self._should_retry_attempt(attempt):
                    break
                await self._backoff(attempt, reason=f"transport {type(exc).__name__}")
                continue
            if response.status_code == 200:
                return response.content
            last_error = ComfyUIExecutionError(
                f"ComfyUI {path} returned HTTP {response.status_code}",
                detail={"status": response.status_code, "body": response.text[:300]},
            )
            if response.status_code not in _RETRYABLE_STATUSES or not self._should_retry_attempt(attempt):
                break
            await self._backoff(attempt, reason=f"http {response.status_code}")
        if isinstance(last_error, ComfyUIError):
            raise last_error
        raise ComfyUIExecutionError(
            f"ComfyUI request failed: {last_error}",
            detail={"exc_type": type(last_error).__name__},
        ) from last_error
