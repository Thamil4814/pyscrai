"""
Shared Infrastructure Module
=============================

Technical adapters for external systems (LLM, DB, vectors, embeddings, export).
"""

# LLM
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
    ModelPricing,
)
from forge.shared.infrastructure.llm.provider_factory import (
    ProviderFactory,
    ProviderType,
    get_provider,
    complete_simple,
)
from forge.shared.infrastructure.llm.openrouter_provider import OpenRouterProvider
from forge.shared.infrastructure.llm.rate_limiter import get_rate_limiter, reset_rate_limiter

# Persistence
from forge.shared.infrastructure.persistence.duckdb_service import DuckDBPersistenceService

# Vector Store
from forge.shared.infrastructure.vector.qdrant_service import QdrantService

# Embeddings
from forge.shared.infrastructure.embeddings.embedding_service import EmbeddingService

# Export
from forge.shared.infrastructure.export.export_service import ExportService

__all__ = [
    # LLM
    "LLMProvider",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "ModelNotFoundError",
    "LLMMessage",
    "LLMResponse",
    "ModelInfo",
    "MessageRole",
    "Conversation",
    "ModelPricing",
    "ProviderFactory",
    "ProviderType",
    "get_provider",
    "complete_simple",
    "OpenRouterProvider",
    "get_rate_limiter",
    "reset_rate_limiter",
    # Persistence
    "DuckDBPersistenceService",
    # Vector
    "QdrantService",
    # Embeddings
    "EmbeddingService",
    # Export
    "ExportService",
]
