"""
LLM Interface - Provider abstraction layer.

Supports multiple backends: OpenRouter, Cherry (local proxy), LM Studio.
"""

from forge.shared.infrastructure.llm.base import (
    LLMProvider,
    LLMError,
    AuthenticationError,
    RateLimitError,
    ModelNotFoundError,
)
from forge.shared.infrastructure.llm.models import (
    LLMMessage,
    LLMResponse,
    ModelInfo,
    MessageRole,
    Conversation,
)
from forge.shared.infrastructure.llm.provider_factory import (
    ProviderFactory,
    ProviderType,
    get_provider,
    complete_simple,
)
from forge.shared.infrastructure.llm.openrouter_provider import OpenRouterProvider

__all__ = [
    # Base
    "LLMProvider",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "ModelNotFoundError",
    # Models
    "LLMMessage",
    "LLMResponse",
    "ModelInfo",
    "MessageRole",
    "Conversation",
    # Factory
    "ProviderFactory",
    "ProviderType",
    "get_provider",
    "complete_simple",
    # Providers
    "OpenRouterProvider",
]
