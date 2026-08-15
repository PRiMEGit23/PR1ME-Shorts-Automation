"""Retry manager: the retry budget and duplicate-render guard.

Two responsibilities:

1. Budget - the loop may render at most ``max_attempts`` times; attempts
   beyond that are refused before any render happens.
2. Duplicate guard - a render whose content fingerprint was already executed
   is rejected as SKIPPED_DUPLICATE. Because every stage is deterministic,
   an identical render would only reproduce the identical outcome, so
   repeating it is never useful and never allowed.
"""

from __future__ import annotations

from runtime.models import DEFAULT_MAX_ATTEMPTS, AttemptStatus


class RetryManager:
    """Deterministic budget and duplicate tracking for one session."""

    def __init__(self, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> None:
        self.max_attempts = max_attempts
        self._executed: list[str] = []

    def can_render(self, attempts_used: int) -> bool:
        """True while the budget is not exhausted."""
        return attempts_used < self.max_attempts

    def remaining(self, attempts_used: int) -> int:
        return max(0, self.max_attempts - attempts_used)

    def is_duplicate(self, fingerprint: str) -> bool:
        return fingerprint in self._executed

    def record(self, fingerprint: str) -> None:
        """Mark a fingerprint as executed (call only when rendering happens)."""
        self._executed.append(fingerprint)

    def classify(self, fingerprint: str) -> AttemptStatus:
        """What status an attempt would get without rendering anything."""
        return AttemptStatus.SKIPPED_DUPLICATE if self.is_duplicate(fingerprint) else AttemptStatus.RENDERED

    @property
    def executed_fingerprints(self) -> tuple[str, ...]:
        return tuple(self._executed)