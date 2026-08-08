"""Dynamic prompt loading and caching.

Loads the prompt markdown files from ``/prompts`` at runtime. The engine never
hardcodes prompt text and never embeds prompts in stage code. Every stage
declares ``prompt_file = "NN_slug.md"`` and the loader resolves it.

Responsibilities:

- enumerate the prompt directory
- load and cache prompt contents
- verify prompt existence
- verify prompt version (optional version manifest)
- detect missing prompt files
- hot-reload support (development mode only)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pr1me.core.errors import PromptLoadError, PromptNotFoundError, PromptVersionError
from pr1me.core.logging import get_logger

#: Prompt filenames follow the prompt library convention: ``NN_slug.md``.
_PROMPT_RE = re.compile(r"^(?P<index>[0-9]{2})_(?P<slug>[a-zA-Z0-9_-]+)\.md$")

#: Optional sidecar mapping ``slug -> semver`` used for version verification.
_MANIFEST_NAME = ".prompt_versions.json"


@dataclass(frozen=True, slots=True)
class PromptDocument:
    """A loaded, cached prompt document."""

    index: str
    slug: str
    filename: str
    path: Path
    content: str
    digest: str
    version: str | None
    modified_at: datetime

    @property
    def title(self) -> str:
        return self.slug.replace("_", " ").replace("generator", "Generator")


class PromptLoader:
    """Load, cache, and validate the prompt layer.

    The loader is async-first: all public methods are awaitable and internal
    state is protected by an ``asyncio.Lock``. Prompt content is cached by
    filename. ``hot_reload`` re-reads files whose mtime changed and is intended
    for development only.
    """

    def __init__(self, prompts_dir: Path, *, hot_reload: bool = False) -> None:
        self._dir = prompts_dir
        self._hot_reload = hot_reload
        self._logger = get_logger("pr1me.core.prompts", prompts_dir=str(prompts_dir))
        self._cache: dict[str, PromptDocument] = {}
        self._index: dict[str, str] = {}
        self._loaded = False
        self._lock = asyncio.Lock()
        self._versions: dict[str, str] = self._read_versions()

    # ------------------------------------------------------------- public ----

    async def load(self, prompt_file: str) -> PromptDocument:
        """Return a cached (or freshly loaded) prompt document.

        :param prompt_file: either a full filename (``"01_topic_generator.md"``),
            a bare slug (``"topic_generator"``) or an index (``"01"``).
        :raises PromptNotFoundError: when the prompt is not found.
        """
        key = await self._resolve_key(prompt_file)
        if key is None:
            raise PromptNotFoundError(
                f"prompt {prompt_file!r} not found in {self._dir}"
            )
        async with self._lock:
            doc = self._cache.get(key)
            if doc is None or self._is_stale(doc):
                doc = self._read(key)
                self._cache[key] = doc
            return doc

    async def load_many(self, prompt_files: Iterable[str]) -> dict[str, PromptDocument]:
        """Load several prompts, raising (with the missing list) if any is absent."""
        missing = await self.missing(prompt_files)
        if missing:
            raise PromptNotFoundError(
                f"missing prompt file(s): {sorted(missing)}",
                detail={"missing": sorted(missing)},
            )
        return {file: await self.load(file) for file in prompt_files}

    async def inspect(self) -> list[PromptDocument]:
        """Return metadata for every discoverable prompt file."""
        async with self._lock:
            self._index = self._scan()
            docs: list[PromptDocument] = []
            for filename in self._index.values():
                if filename not in self._cache:
                    self._cache[filename] = self._read(filename)
                docs.append(self._cache[filename])
            return sorted(docs, key=lambda doc: doc.index)

    async def refresh(self) -> None:
        """Drop all caches and retry loading (development / hot-reload)."""
        async with self._lock:
            self._cache.clear()
            self._index = self._scan()
            self._versions = self._read_versions()

    # ----------------------------------------------------------- existence ----

    async def exists(self, prompt_file: str) -> bool:
        return await self._resolve_key(prompt_file) is not None

    async def missing(self, prompt_files: Iterable[str]) -> list[str]:
        """Return the subset of ``prompt_files`` that are not present."""
        missing: list[str] = []
        for prompt_file in prompt_files:
            if not await self.exists(prompt_file):
                missing.append(prompt_file)
        return missing

    # ------------------------------------------------------------ version -----

    async def verify_version(self, prompt_file: str, *, expected: str | None = None) -> None:
        """Verify a prompt's declared version against the version manifest.

        Versions are read from the optional ``.prompt_versions.json`` sidecar in
        the prompts directory, keyed by slug. When the manifest is absent or the
        slug is not listed, verification is skipped rather than invented.

        :raises PromptVersionError: when ``expected`` is given and mismatches.
        """
        slug = self._slug_of(prompt_file)
        declared = self._versions.get(slug)
        if declared is None:
            return
        if expected is not None and declared != expected:
            raise PromptVersionError(
                f"prompt {prompt_file!r} declares version {declared!r}, "
                f"expected {expected!r}"
            )

    # ------------------------------------------------------------ internals ----

    def _scan(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for path in sorted(self._dir.glob("[0-9][0-9]_*")):
            match = _PROMPT_RE.match(path.name)
            if match is None:
                continue
            index[match.group("slug")] = path.name
        return index

    def _read(self, filename: str) -> PromptDocument:
        path = self._dir / filename
        match = _PROMPT_RE.match(filename)
        if match is None:
            raise PromptLoadError(f"unexpected prompt filename {filename!r}")
        try:
            text = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
        except OSError as exc:
            raise PromptLoadError(f"cannot read prompt {path}: {exc}") from exc
        slug = match.group("slug")
        return PromptDocument(
            index=match.group("index"),
            slug=slug,
            filename=filename,
            path=path,
            content=text,
            digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            version=self._versions.get(slug),
            modified_at=datetime.fromtimestamp(mtime, tz=UTC),
        )

    def _is_stale(self, doc: PromptDocument) -> bool:
        if not self._hot_reload:
            return False
        try:
            return doc.path.stat().st_mtime != doc.modified_at.timestamp()
        except OSError:
            return True

    async def _resolve_key(self, prompt_file: str) -> str | None:
        name = prompt_file.strip()
        if name.endswith(".md"):
            return name if (self._dir / name).is_file() else None
        async with self._lock:
            if not self._index:
                self._index = self._scan()
        slug = name.lower()
        if slug in self._index:
            return self._index[slug]
        for filename in self._index.values():
            if filename.startswith(f"{slug}_"):
                return filename
        return None

    @staticmethod
    def _slug_of(prompt_file: str) -> str:
        name = prompt_file.strip().removesuffix(".md")
        return name.split("_", 1)[1] if "_" in name else name

    def _read_versions(self) -> dict[str, str]:
        manifest = self._dir / _MANIFEST_NAME
        if not manifest.is_file():
            return {}
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._logger.warning("event=prompt.versions.malformed", error=str(exc))
            return {}
        return {str(key): str(value) for key, value in data.items()}