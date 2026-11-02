"""Deterministic Mock Provider for Satyahd.

Implements R-204:
- Deterministic mock provider for offline demos, reproducible evaluations, and unit tests.
- Replicates extraction, rewrite, self-check, image description, and red-team stages without external network calls.
"""

from __future__ import annotations

import time
from typing import Any

from app.providers.base import BaseProvider, ProviderResult


class MockProvider(BaseProvider):
    """Deterministic, zero-network mock provider."""

    def __init__(self, name: str = "mock", default_model: str = "muse-spark-1.3 [MOCK]"):
        super().__init__(name=name, default_model=default_model)

    def generate(
        self,
        stage: str,
        messages: list[dict[str, Any]],
        model_name: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        interaction_id: str | None = None,
        **kwargs: Any,
    ) -> ProviderResult:
        start_time = time.perf_counter()
        target_model = model_name or self.default_model

        from app.models import _generate_mock_response
        content = _generate_mock_response(stage, messages, tools)
        latency_ms = max(5, int((time.perf_counter() - start_time) * 1000))

        input_tokens = sum(len(str(m.get("content", ""))) // 4 for m in messages) + 10
        output_tokens = len(content) // 4 + 5
        cost = self.estimate_cost(input_tokens, output_tokens)

        return ProviderResult(
            content=content,
            stage=stage,
            model=target_model,
            provider_name=self.name,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            ok=True,
            is_mock=True,
        )
