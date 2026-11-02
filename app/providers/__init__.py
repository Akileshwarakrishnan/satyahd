"""Satyahd Model Providers Package.

Implements R-201 to R-206:
- Provider abstraction and interfaces
- Meta, OpenAI, and Mock implementations
- Dynamic registry, fail-closed fallback, and cost accounting
"""

from app.providers.base import BaseProvider, ProviderResult
from app.providers.meta import MetaProvider
from app.providers.mock import MockProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.registry import (
    call_provider_with_fallback,
    get_provider,
    log_provider_usage,
    register_provider,
)

__all__ = [
    "BaseProvider",
    "ProviderResult",
    "MetaProvider",
    "MockProvider",
    "OpenAIProvider",
    "get_provider",
    "register_provider",
    "call_provider_with_fallback",
    "log_provider_usage",
]
