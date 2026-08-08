"""Structured, asynchronous-safe logging.

Uses the stdlib ``logging`` under the hood with a JSON formatter. Every log
record carries ``ts``, ``level``, ``logger`` and any key=value context fields.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "ctx", None)
        if isinstance(extra, Mapping) and extra:
            for key, value in extra.items():
                payload[key] = value
        return json.dumps(payload, default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return None
        return value
    if isinstance(value, (list, tuple)):
        return [json_default_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): json_default_safe(v) for k, v in value.items()}
    return str(value)


def json_default_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return _json_default(value)


_LOG_RESERVED = {"exc_info", "stack_info", "stacklevel", "extra"}


class ContextLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that packs kwargs and a static context into every record.

    Usage preserves ``logger.info("msg", event="stage.completed", duration_ms=5)``;
    the keyword extras (everything beyond the stdlib logging kwargs) are merged
    into the record's ``ctx`` dict and emitted as structured JSON fields.
    """

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        ctx: dict[str, Any] = {}
        if "extra" in kwargs and isinstance(kwargs["extra"], dict):
            extra_ctx = kwargs["extra"].get("ctx")
            if isinstance(extra_ctx, dict):
                ctx.update(extra_ctx)
        if self.extra:
            extra_ctx = self.extra.get("ctx")
            if isinstance(extra_ctx, dict):
                ctx.update(extra_ctx)
        for key in list(kwargs):
            if key not in _LOG_RESERVED:
                ctx[key] = kwargs.pop(key)
        kwargs["extra"] = {"ctx": ctx}
        return msg, kwargs


def setup_logging(*, level: str = "INFO", json: bool = True) -> None:
    """Configure the root logger once."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level.upper())
    if json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.handlers[:] = [handler]
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter:
    """Return a context-aware logger for a module or stage."""
    logger = logging.getLogger(name)
    return ContextLoggerAdapter(logger, {"ctx": context})
