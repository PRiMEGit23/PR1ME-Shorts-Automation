"""Provider registry for easy backend swapping.

Providers are registered by name (``"deepseek"``, ``"openai"``, ``"noop"``,
...) and resolved lazily. The engine asks the registry for the configured
provider instead of constructing providers directly.
"""

from __future__ import annotations

from typing import TypeVar

from pr1me.core.errors import ProviderNotConfiguredError
from pr1me.providers.base_provider import BaseProvider, NoopProvider

ProviderT = TypeVar("ProviderT", bound=BaseProvider)


class ProviderRegistry:
    """Maps provider names to provider *factory* callables."""

    def __init__(self) -> None:
        self._factories: dict[str, type[BaseProvider]] = {}
        # Default noop provider is always available so unconfigured runs fail fast.
        self.register(NoopProvider)

    def register(self, provider_cls: type[ProviderT]) -> None:
        """Register (or replace) a provider class under ``provider_cls.name``."""
        if not getattr(provider_cls, "name", None):
            raise ProviderNotConfiguredError("provider class must define a 'name' attribute")
        self._factories[provider_cls.name] = provider_cls

    def available(self) -> list[str]:
        """Return the names of all registered providers."""
        return sorted(self._factories)

    def build(self, name: str) -> BaseProvider:
        """Instantiate the provider with the given name.

        :raises ProviderNotConfiguredError: when the name is unknown.
        """
        try:
            cls = self._factories[name]
        except KeyError as exc:
            raise ProviderNotConfiguredError(
                f"provider {name!r} is not registered; available: {self.available()}"
            ) from exc
        return cls()

    def has(self, name: str) -> bool:
        return name in self._factories