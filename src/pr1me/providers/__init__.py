"""AI providers package.

Exposes the abstract provider interface and the provider registry. Concrete
backends (DeepSeek, OpenAI, Claude, Gemini, local) live in sibling modules and
inherit from ``BaseProvider``.
"""

from pr1me.providers.base_provider import (
    BaseProvider,
    Completion,
    CompletionRequest,
    Message,
    NoopProvider,
    StructuredCompletion,
    Usage,
)
from pr1me.providers.deepseek import DeepSeekProvider
from pr1me.providers.registry import ProviderRegistry

__all__ = [
    "BaseProvider",
    "Completion",
    "CompletionRequest",
    "DeepSeekProvider",
    "Message",
    "NoopProvider",
    "ProviderRegistry",
    "StructuredCompletion",
    "Usage",
]