"""Meta Model Provider for Satyahd.

Implements R-202:
- Connects to Meta Model API (https://api.meta.ai/v1) using OpenAI-compatible format.
- Configures reasoning_effort (minimal for extraction, rewrite; medium for sales agent).
- Supports structured output schema for promises extraction.
- Automatic retry on 429 / 5xx.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import BaseProvider, ProviderResult

logger = logging.getLogger("satyahd.providers.meta")

STAGE_CONFIGS: dict[str, dict[str, Any]] = {
    "sales_agent": {
        "reasoning_effort": "medium",
        "temperature": 0.7,
        "max_tokens": 300,
    },
    "pre_filter": {
        "reasoning_effort": "minimal",
        "temperature": None,
        "max_tokens": 100,
    },
    "extraction": {
        "reasoning_effort": "minimal",
        "structured_output": True,
        "temperature": None,
        "max_tokens": 400,
    },
    "self_check": {
        "reasoning_effort": "minimal",
        "structured_output": True,
        "temperature": None,
        "max_tokens": 300,
    },
    "rewrite": {
        "reasoning_effort": "minimal",
        "temperature": None,
        "max_tokens": 200,
    },
    "red_team": {
        "reasoning_effort": "medium",
        "temperature": 0.8,
        "max_tokens": 350,
    },
    "image_describe": {
        "reasoning_effort": "minimal",
        "temperature": None,
        "max_tokens": 250,
    },
}


class MetaProvider(BaseProvider):
    """Meta Model API Provider (muse-spark-1.3, muse-wonder-1.0)."""

    def __init__(
        self,
        name: str = "meta",
        default_model: str = "muse-spark-1.3",
        api_base: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__(name=name, default_model=default_model)
        settings = get_settings()
        self.api_base = (api_base or settings.META_API_BASE).rstrip("/")
        self.api_key = api_key or settings.MODEL_API_KEY or settings.META_API_KEY

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
        stage_cfg = STAGE_CONFIGS.get(stage, {})
        start_time = time.perf_counter()

        if not self.api_key or self.api_key.startswith("mock_"):
            # If no live key, delegate to mock safely
            from app.providers.mock import MockProvider
            mock = MockProvider(name="meta", default_model=f"{target_model} [MOCK]")
            return mock.generate(
                stage=stage,
                messages=messages,
                model_name=f"{target_model} [MOCK]",
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                interaction_id=interaction_id,
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        effective_max_tokens = max_tokens or stage_cfg.get("max_tokens", 300)
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "max_tokens": effective_max_tokens,
        }

        reasoning = stage_cfg.get("reasoning_effort")
        if reasoning:
            payload["reasoning_effort"] = reasoning

        effective_temp = temperature if temperature is not None else stage_cfg.get("temperature")
        if effective_temp is not None:
            payload["temperature"] = effective_temp

        if stage_cfg.get("structured_output") or stage == "extraction":
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
                    logger.warning("Meta API returned %d. Retrying after 2s...", resp.status_code)
                    time.sleep(2.0)
                    continue

                break

            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.warning("Meta API attempt %d failed: %s", attempts, exc)
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
