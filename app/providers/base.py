"""Base Provider Interface for Satyahd Model Abstraction.

Implements R-201:
- BaseProvider abstract interface for Meta, OpenAI, Anthropic, and Mock providers.
- ProviderResult with token, latency, cost accounting, and raw output preservation.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderResult:
    content: str
    stage: str
    model: str
    provider_name: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    ok: bool
    is_mock: bool = False
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract interface that all model providers must implement."""

    def __init__(self, name: str, default_model: str):
        self.name = name
        self.default_model = default_model

    @abstractmethod
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
        """Executes a completion request for a specific pipeline stage."""
        pass

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Default token cost estimation ($0.20/1M input, $0.50/1M output)."""
        return (input_tokens / 1_000_000 * 0.20) + (output_tokens / 1_000_000 * 0.50)
