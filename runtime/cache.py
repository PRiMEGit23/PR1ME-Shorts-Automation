"""Render cache: content-addressed storage of render results.

The cache is keyed by the render fingerprint (prompt + workflow + seed). It
is what lets the loop "never repeat an identical render": a fingerprint that
already produced a result is never rendered again - the cached artifacts are
reused instead. Deterministic and safe to share between sessions.

Storage is optional: with root=None the cache keeps results in memory only.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge.image_qa.qa_models import GeneratedImageMetadata

from runtime.models import RenderResult


class CachedRender:
    """One cached render result plus its on-disk location."""

    def __init__(self, result: RenderResult, path: Path | None = None) -> None:
        self.result = result
        self.path = path


class RenderCache:
    """Content-addressed store: fingerprint -> RenderResult."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root
        self._memory: dict[str, RenderResult] = {}

    @property
    def root(self) -> Path | None:
        return self._root

    def get(self, fingerprint: str) -> RenderResult | None:
        if fingerprint in self._memory:
            return self._memory[fingerprint]
        if self._root is not None:
            entry = self._root / fingerprint
            metadata_path = entry / "metadata.json"
            if metadata_path.exists():
                metadata = GeneratedImageMetadata.model_validate_json(
                    metadata_path.read_text(encoding="utf-8")
                )
                image_path = entry / "image.png"
                if image_path.exists():
                    return RenderResult(
                        metadata=metadata, image_bytes=image_path.read_bytes()
                    )
        return None

    def put(self, fingerprint: str, result: RenderResult) -> Path | None:
        self._memory[fingerprint] = result
        if self._root is None:
            return None
        entry = self._root / fingerprint
        entry.mkdir(parents=True, exist_ok=True)
        (entry / "metadata.json").write_text(
            result.metadata.model_dump_json(), encoding="utf-8"
        )
        (entry / "image.png").write_bytes(result.image_bytes)
        (entry / "fingerprint.json").write_text(
            json.dumps({"fingerprint": fingerprint}, sort_keys=True), encoding="utf-8"
        )
        return entry

    def has(self, fingerprint: str) -> bool:
        return fingerprint in self._memory or (
            self._root is not None and (self._root / fingerprint / "metadata.json").exists()
        )

    def __len__(self) -> int:
        if self._root is None:
            return len(self._memory)
        # On disk the fingerprint directories are the source of truth;
        # memory entries are always mirrored on disk when a root is set.
        return sum(1 for p in self._root.iterdir() if p.is_dir())