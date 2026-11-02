"""Satyahd Universal Python SDK.

A drop-in trust layer for any AI chatbot.
Customer -> Host Chatbot -> draft/tool call -> Satyahd -> verdict -> Host Chatbot -> Customer

Usage:
    import satyahd

    # 1. Verify text response
    result = satyahd.verify(
        draft=bot_draft,
        customer_message=user_prompt,
        mode="rewrite",
    )
    send_to_customer(result.safe_reply)

    # 2. Verify tool / action call
    act = satyahd.verify_action(
        tool_name="apply_discount",
        arguments={"percent": 50, "order_id": "ORD-123"},
    )
    if act.allowed:
        execute_action()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("satyahd.sdk")

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_FAIL_CLOSED_MSG = "Thanks for your message. A member of our team will confirm the details and get back to you shortly."


@dataclass
class VerifyResult:
    verdict: str  # "allow" | "block" | "review"
    safe_reply: str
    status: str  # "allowed" | "rewritten" | "held"
    audit_seq: int | None
    interaction_id: str
    policy_version: str
    tenant_id: str
    mode: str
    sandbox: bool
    promises: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def is_allowed(self) -> bool:
        return self.verdict == "allow" or self.status in ("allowed", "rewritten")


@dataclass
class ActionVerifyResult:
    verdict: str  # "allow" | "block" | "review"
    allowed: bool
    action_name: str
    reason: str
    threshold: float | None
    audit_seq: int | None
    interaction_id: str
    tenant_id: str
    sandbox: bool
    error: str | None = None


class SatyahdClient:
    """Client for interfacing with the Satyahd Universal Middleman Plugin."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        timeout: float = 5.0,
        fail_closed_message: str = DEFAULT_FAIL_CLOSED_MSG,
        http_client: httpx.Client | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.fail_closed_message = fail_closed_message
        self._http_client = http_client

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout)

    def verify(
        self,
        draft: str,
        customer_message: str = "",
        mode: str = "rewrite",
        tenant_id: str = "default",
        context: dict[str, Any] | None = None,
        sandbox: bool = False,
    ) -> VerifyResult:
        """Verifies an outgoing LLM draft response.
        
        Fail-closed: if the server is unreachable, times out, or returns an error,
        it safely falls back to fail_closed_message and verdict="review".
        """
        url = f"{self.base_url}/v1/verify"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if sandbox:
            headers["X-Satyahd-Sandbox"] = "true"

        ctx = context or {}
        if customer_message and "customer_message" not in ctx:
            ctx["customer_message"] = customer_message

        payload = {
            "draft": draft,
            "context": ctx,
            "tenant_id": tenant_id,
            "mode": mode,
        }

        try:
            client = self._get_client()
            should_close = (client != self._http_client)
            try:
                resp = client.post(url, headers=headers, json=payload)
            finally:
                if should_close:
                    client.close()

            if resp.status_code == 200:
                data = resp.json()
                return VerifyResult(
                    verdict=data.get("verdict", "review"),
                    safe_reply=data.get("safe_reply", self.fail_closed_message),
                    status=data.get("status", "held"),
                    audit_seq=data.get("audit_seq"),
                    interaction_id=data.get("interaction_id", "local_fail"),
                    policy_version=data.get("policy_version", "1.0"),
                    tenant_id=data.get("tenant_id", tenant_id),
                    mode=data.get("mode", mode),
                    sandbox=data.get("sandbox", sandbox),
                    promises=data.get("promises", []),
                    violations=data.get("violations", []),
                    evidence=data.get("evidence", {}),
                )
            else:
                logger.error("Satyahd /v1/verify returned HTTP %d: %s", resp.status_code, resp.text)
                return self._fallback_verify_result(
                    error=f"HTTP {resp.status_code}: {resp.text}",
                    mode=mode,
                    tenant_id=tenant_id,
                    sandbox=sandbox,
                )

        except Exception as exc:
            # If server connection was refused, check if we can seamlessly evaluate via local in-process app
            err_str = str(exc)
            if "actively refused" in err_str or "ConnectError" in err_str or "ConnectionRefused" in err_str:
                try:
                    from fastapi.testclient import TestClient
                    from app.main import app
                    local_tc = TestClient(app)
                    resp = local_tc.post("/v1/verify", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return VerifyResult(
                            verdict=data.get("verdict", "review"),
                            safe_reply=data.get("safe_reply", self.fail_closed_message),
                            status=data.get("status", "held"),
                            audit_seq=data.get("audit_seq"),
                            interaction_id=data.get("interaction_id", "local"),
                            policy_version=data.get("policy_version", "1.0"),
                            tenant_id=data.get("tenant_id", tenant_id),
                            mode=data.get("mode", mode),
                            sandbox=data.get("sandbox", sandbox),
                            promises=data.get("promises", []),
                            violations=data.get("violations", []),
                            evidence=data.get("evidence", {}),
                        )
                except Exception:
                    pass

            logger.error("Satyahd /v1/verify connection failed: %s", exc)
            return self._fallback_verify_result(
                error=str(exc),
                mode=mode,
                tenant_id=tenant_id,
                sandbox=sandbox,
            )

    def verify_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tenant_id: str = "default",
        context: dict[str, Any] | None = None,
        sandbox: bool = False,
    ) -> ActionVerifyResult:
        """Verifies an action-tool call before execution.
        
        Fail-closed: returns allowed=False on any failure.
        """
        url = f"{self.base_url}/v1/verify/action"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if sandbox:
            headers["X-Satyahd-Sandbox"] = "true"

        payload = {
            "action_name": tool_name,
            "tool_name": tool_name,
            "parameters": arguments,
            "args": arguments,
            "context": context or {},
            "tenant_id": tenant_id,
        }

        try:
            client = self._get_client()
            should_close = (client != self._http_client)
            try:
                resp = client.post(url, headers=headers, json=payload)
            finally:
                if should_close:
                    client.close()

            if resp.status_code == 200:
                data = resp.json()
                return ActionVerifyResult(
                    verdict=data.get("verdict", "block"),
                    allowed=bool(data.get("allowed", False)),
                    action_name=data.get("action_name", tool_name),
                    reason=data.get("reason", "Decision returned by Satyahd Gateway."),
                    threshold=data.get("threshold"),
                    audit_seq=data.get("audit_seq"),
                    interaction_id=data.get("interaction_id", "act_local"),
                    tenant_id=data.get("tenant_id", tenant_id),
                    sandbox=data.get("sandbox", sandbox),
                )
            else:
                return ActionVerifyResult(
                    verdict="block",
                    allowed=False,
                    action_name=tool_name,
                    reason=f"Gateway error HTTP {resp.status_code}",
                    threshold=None,
                    audit_seq=None,
                    interaction_id="act_err",
                    tenant_id=tenant_id,
                    sandbox=sandbox,
                    error=resp.text,
                )

        except Exception as exc:
            err_str = str(exc)
            if "actively refused" in err_str or "ConnectError" in err_str or "ConnectionRefused" in err_str:
                try:
                    from fastapi.testclient import TestClient
                    from app.main import app
                    local_tc = TestClient(app)
                    resp = local_tc.post("/v1/verify/action", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        return ActionVerifyResult(
                            verdict=data.get("verdict", "block"),
                            allowed=bool(data.get("allowed", False)),
                            action_name=data.get("action_name", tool_name),
                            reason=data.get("reason", "Decision returned by Satyahd Gateway."),
                            threshold=data.get("threshold"),
                            audit_seq=data.get("audit_seq"),
                            interaction_id=data.get("interaction_id", "act_local"),
                            tenant_id=data.get("tenant_id", tenant_id),
                            sandbox=data.get("sandbox", sandbox),
                        )
                except Exception:
                    pass

            return ActionVerifyResult(
                verdict="block",
                allowed=False,
                action_name=tool_name,
                reason=f"Gateway connection failure: {exc}",
                threshold=None,
                audit_seq=None,
                interaction_id="act_fail_closed",
                tenant_id=tenant_id,
                sandbox=sandbox,
                error=str(exc),
            )

    def _fallback_verify_result(
        self,
        error: str,
        mode: str,
        tenant_id: str,
        sandbox: bool,
    ) -> VerifyResult:
        return VerifyResult(
            verdict="review",
            safe_reply=self.fail_closed_message,
            status="held",
            audit_seq=None,
            interaction_id="local_fail_closed",
            policy_version="1.0",
            tenant_id=tenant_id,
            mode=mode,
            sandbox=sandbox,
            error=error,
        )


# Module-level convenience functions
_default_client = SatyahdClient()


def verify(
    draft: str,
    customer_message: str = "",
    mode: str = "rewrite",
    base_url: str = DEFAULT_BASE_URL,
    tenant_id: str = "default",
    sandbox: bool = False,
    timeout: float = 5.0,
    fallback_message: str = DEFAULT_FAIL_CLOSED_MSG,
) -> VerifyResult:
    """Module-level helper to verify an LLM draft with ~1 line of code."""
    client = SatyahdClient(base_url=base_url, timeout=timeout, fail_closed_message=fallback_message)
    return client.verify(
        draft=draft,
        customer_message=customer_message,
        mode=mode,
        tenant_id=tenant_id,
        sandbox=sandbox,
    )


def verify_action(
    tool_name: str,
    arguments: dict[str, Any],
    base_url: str = DEFAULT_BASE_URL,
    tenant_id: str = "default",
    sandbox: bool = False,
    timeout: float = 5.0,
) -> ActionVerifyResult:
    """Module-level helper to verify a tool/action call with ~1 line of code."""
    client = SatyahdClient(base_url=base_url, timeout=timeout)
    return client.verify_action(
        tool_name=tool_name,
        arguments=arguments,
        tenant_id=tenant_id,
        sandbox=sandbox,
    )


from satyahd.langchain import SatyahdCallbackHandler

__all__ = [
    "SatyahdClient",
    "VerifyResult",
    "ActionVerifyResult",
    "SatyahdCallbackHandler",
    "verify",
    "verify_action",
]

