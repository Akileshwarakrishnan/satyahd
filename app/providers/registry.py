"""Provider Registry and Fallback Manager for Satyahd.

Implements R-205 & R-206:
- Provider discovery & lookup by name ("meta", "openai", "mock").
- Fail-closed fallback: if primary provider times out or fails, attempts secondary provider or fails closed.
- Automatic per-provider latency, token, and cost accounting.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.config import get_settings
from app.db import get_db
from app.providers.base import BaseProvider, ProviderResult
from app.providers.meta import MetaProvider
from app.providers.mock import MockProvider
from app.providers.openai_provider import OpenAIProvider

logger = logging.getLogger("satyahd.providers.registry")

_PROVIDERS: dict[str, BaseProvider] = {}


def register_provider(name: str, provider: BaseProvider) -> None:
    """Registers a model provider instance."""
    _PROVIDERS[name.lower()] = provider


def get_provider(name: str | None = None) -> BaseProvider:
    """Returns requested provider or default configured provider."""
    settings = get_settings()
    provider_name = (name or getattr(settings, "DEFAULT_PROVIDER", "meta")).lower()

    if not _PROVIDERS:
        # Initialize default standard providers
        register_provider("mock", MockProvider())
        register_provider("meta", MetaProvider())
        register_provider("openai", OpenAIProvider())

    if provider_name in _PROVIDERS:
        return _PROVIDERS[provider_name]

    # If unknown name, default to meta or mock
    logger.warning("Requested provider '%s' not found. Defaulting to 'meta'.", provider_name)
    return _PROVIDERS.get("meta", MockProvider())


def log_provider_usage(
    result: ProviderResult,
    stage: str,
    interaction_id: str | None = None,
) -> None:
    """Persists model usage, latency, tokens and costs to model_usage table."""
    try:
        usage_id = f"mu_{uuid.uuid4().hex[:12]}"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO model_usage (
                    id, interaction_id, stage, model, latency_ms, input_tokens, output_tokens, ok, cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage_id,
                    interaction_id,
                    stage,
                    f"{result.provider_name}:{result.model}",
                    result.latency_ms,
                    result.input_tokens,
                    result.output_tokens,
                    1 if result.ok else 0,
                    result.cost_usd,
                ),
            )
    except Exception as exc:
        logger.error("Failed to log provider usage: %s", exc)


def call_provider_with_fallback(
    stage: str,
    messages: list[dict[str, Any]],
    provider_name: str | None = None,
    fallback_provider_name: str | None = "mock",
    model_name: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    interaction_id: str | None = None,
    **kwargs: Any,
) -> ProviderResult:
    """Calls primary provider with automatic fallback on failure (R-205).
    
    If both fail, returns an ok=False result so caller fails closed.
    """
    primary = get_provider(provider_name)
    result = primary.generate(
        stage=stage,
        messages=messages,
        model_name=model_name,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        interaction_id=interaction_id,
        **kwargs,
    )

    if result.ok:
        log_provider_usage(result, stage, interaction_id)
        return result

    # Fail-closed provider fallback
    if fallback_provider_name and fallback_provider_name.lower() != primary.name:
        logger.warning(
            "Primary provider '%s' failed for stage '%s'. Trying fallback '%s'...",
            primary.name,
            stage,
            fallback_provider_name,
        )
        fallback = get_provider(fallback_provider_name)
        fb_result = fallback.generate(
            stage=stage,
            messages=messages,
            model_name=model_name,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            interaction_id=interaction_id,
            **kwargs,
        )
        log_provider_usage(fb_result, stage, interaction_id)
        return fb_result

    log_provider_usage(result, stage, interaction_id)
    return result
