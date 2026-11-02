"""Non-Meta Model Provider (OpenAI / Anthropic Compatible) for Satyahd.

Implements R-203:
- Connects to OpenAI or Anthropic endpoints when live API keys are provided.
- Operates deterministically in offline/mock mode when running in local evaluation.
- Follows the same ProviderResult contract for uniform verification.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import BaseProvider, ProviderResult
from app.providers.mock import MockProvider

logger = logging.getLogger("satyahd.providers.openai")


class OpenAIProvider(BaseProvider):
    """OpenAI / Non-Meta provider (gpt-4o, gpt-4o-mini, or compatible)."""

    def __init__(
        self,
        name: str = "openai",
        default_model: str = "gpt-4o-mini",
        api_base: str = "https://api.openai.com/v1",
        api_key: str | None = None,
    ):
        super().__init__(name=name, default_model=default_model)
        self.api_base = (api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._mock_fallback = MockProvider(name=name, default_model=f"{default_model} [MOCK]")

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
        settings = get_settings()
        target_model = model_name or self.default_model
        start_time = time.perf_counter()

        # If no OpenAI key or offline mock mode requested, use deterministic fallback
        if not self.api_key or self.api_key.startswith("mock_") or settings.ALLOW_MOCK:
            res = self._mock_fallback.generate(
                stage=stage,
                messages=messages,
                model_name=f"{target_model} [MOCK]",
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                interaction_id=interaction_id,
                **kwargs,
            )
            res.provider_name = self.name
            return res

        # Live OpenAI API Execution
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens or 300,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if stage in ("extraction", "self_check"):
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools

        url = f"{self.api_base}/chat/completions"
        attempts = 0
        max_attempts = 2

        while attempts < max_attempts:
            attempts += 1
            try:
                with httpx.Client(timeout=float(settings.MODEL_TIMEOUT_SECONDS)) as client:
                    resp = client.post(url, headers=headers, json=payload)

                latency_ms = int((time.perf_counter() - start_time) * 1000)

                if resp.status_code == 200:
                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    msg = choice.get("message", {})
                    content = msg.get("content", "") or ""
                    tool_calls = msg.get("tool_calls", []) or []
                    usage = data.get("usage", {})
                    in_tok = usage.get("prompt_tokens", 0)
                    out_tok = usage.get("completion_tokens", 0)
                    cost = self.estimate_cost(in_tok, out_tok)

                    return ProviderResult(
                        content=content,
                        stage=stage,
                        model=target_model,
                        provider_name=self.name,
                        latency_ms=latency_ms,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost,
                        ok=True,
                        is_mock=False,
                        tool_calls=tool_calls,
                        raw_response=data,
                    )

                if resp.status_code in (429, 500, 502, 503, 504) and attempts < max_attempts:
                    logger.warning("OpenAI API returned %d. Retrying...", resp.status_code)
                    time.sleep(2.0)
                    continue

                break

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning("OpenAI API attempt %d error: %s", attempts, exc)
                if attempts < max_attempts:
                    time.sleep(2.0)
                    continue

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        return ProviderResult(
            content="",
            stage=stage,
            model=target_model,
            provider_name=self.name,
            latency_ms=latency_ms,
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            ok=False,
            is_mock=False,
        )
