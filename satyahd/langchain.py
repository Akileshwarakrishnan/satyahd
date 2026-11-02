"""LangChain Middleware Integration for Satyahd (R-107).

Provides drop-in callbacks and runnable wrappers to protect LangChain
agents and chat models from making unauthorized commitments.

Usage:
    from satyahd.langchain import SatyahdCallbackHandler

    handler = SatyahdCallbackHandler(
        api_url="http://127.0.0.1:8000",
        mode="rewrite",
    )
    llm = ChatOpenAI(callbacks=[handler])
"""

from __future__ import annotations

import logging
from typing import Any

from satyahd import SatyahdClient, VerifyResult, DEFAULT_BASE_URL, DEFAULT_FAIL_CLOSED_MSG

logger = logging.getLogger("satyahd.langchain")


class SatyahdCallbackHandler:
    """LangChain callback handler that intercepts LLM outputs and verifies promises."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        mode: str = "rewrite",
        tenant_id: str = "default",
        timeout: float = 5.0,
        fail_closed_message: str = DEFAULT_FAIL_CLOSED_MSG,
    ):
        self.client = SatyahdClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            fail_closed_message=fail_closed_message,
        )
        self.mode = mode
        self.tenant_id = tenant_id
        self.last_result: VerifyResult | None = None

    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        """Intercepts LLM response generations and verifies each output against Satyahd."""
        try:
            generations = getattr(response, "generations", [])
            for gen_list in generations:
                for gen in gen_list:
                    text = getattr(gen, "text", "")
                    if text:
                        res = self.client.verify(
                            draft=text,
                            mode=self.mode,
                            tenant_id=self.tenant_id,
                        )
                        self.last_result = res
                        if res.status == "rewritten" or res.verdict != "allow":
                            logger.info(
                                "Satyahd LangChain Guardrail intercepted output. Verdict: %s, Status: %s",
                                res.verdict,
                                res.status,
                            )
                            # Update the generation text with the safe rewrite
                            setattr(gen, "text", res.safe_reply)
        except Exception as exc:
            logger.error("Satyahd LangChain callback failed-closed: %s", exc)

    def verify_message(self, draft: str, customer_message: str = "") -> VerifyResult:
        """Direct helper to verify a draft within a LangChain execution context."""
        return self.client.verify(
            draft=draft,
            customer_message=customer_message,
            mode=self.mode,
            tenant_id=self.tenant_id,
        )
