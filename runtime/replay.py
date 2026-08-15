"""Deterministic replay support.

A saved session is fully self-describing: the history JSON holds every
prompt, workflow, QA report, optimization plan, and winner. replay() rebuilds
the session result from that JSON without rendering anything, so a session
can be audited, diffed, or re-served from artifacts at any time.

Determinism itself is a stronger guarantee, verified by tests: running the
same row + seed through the session twice yields byte-identical results, and
replay() reproduces exactly what the live run produced.
"""

from __future__ import annotations

import json
from pathlib import Path

from runtime.history import RenderHistory
from runtime.models import RenderSessionResult


def replay(history: RenderHistory | Path | str | dict) -> RenderSessionResult:
    """Rebuild a session result from saved history, without re-rendering.

    Accepts a RenderHistory, a path to history.json, raw JSON text, or a dict.
    """
    if isinstance(history, RenderHistory):
        return history.to_session_result()
    if isinstance(history, Path):
        history = RenderHistory.from_file(history)
    elif isinstance(history, str):
        history = RenderHistory.from_json(history)
    elif isinstance(history, dict):
        history = RenderHistory.from_json(history)
    return history.to_session_result()


def verify_replay_identical(live: RenderSessionResult, replayed: RenderSessionResult) -> None:
    """Assert a live session and its replay are byte-for-byte identical."""
    if json.dumps(live.model_dump(mode="json"), sort_keys=True) != json.dumps(
        replayed.model_dump(mode="json"), sort_keys=True
    ):
        raise AssertionError(
            "live session and replay diverge; deterministic replay is broken"
        )