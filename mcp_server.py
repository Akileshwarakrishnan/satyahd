"""
Satyahd Model Context Protocol (MCP) Server.
Enables MCP-compatible AI clients (Claude Desktop, Cursor, Antigravity, custom agents)
to connect directly to the Satyahd deterministic zero-trust policy enforcement gate.

Exposed Tools:
- verify_draft: Intercepts & validates draft replies, excising unauthorized promises
- verify_action: Pre-flight authorization gate for tool calls (e.g. refunds, cancellations)
- check_audit_trail: Cryptographically verifies Ed25519 signatures and SHA-256 continuous hash chain
- get_active_policies: Returns the enterprise policy rules currently enforced
"""

import sys
import os
import json
import asyncio
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mcp.server.mcpserver import MCPServer
from fastapi.testclient import TestClient
from app.main import app

# In-process client for deterministic, sub-15ms local execution
_client = TestClient(app)

# Initialize MCP Server
server = MCPServer(
    name="satyahd",
    version="1.0.0",
    description="Satyahd Meta AI-Powered Zero-Trust Policy Enforcement Gate for Enterprise AI Agents"
)


@server.tool(
    name="verify_draft",
    description=(
        "Intercept and verify an AI agent's proposed draft reply against corporate policy rules "
        "and live database facts. Automatically rewrites unauthorized commitments (e.g. unapproved discounts, "
        "guaranteed refunds, non-compliant delivery windows) while preserving customer empathy. "
        "Returns approved text, policy violations, and Ed25519 signature."
    ),
)
async def verify_draft(
    draft: str,
    customer_message: str = "",
    mode: str = "rewrite",
    tenant_id: str = "default",
) -> str:
    """Verifies a candidate draft response before emitting it to the customer.

    Args:
        draft: The proposed response text from the AI agent.
        customer_message: The preceding customer message/request.
        mode: Verification mode - 'rewrite' (auto-rewrite violations), 'block_only', or 'return_feedback'.
        tenant_id: Tenant or organization identifier.

    Returns:
        JSON string containing the verification verdict, safe approved reply,
        violations detected, and audit signature.
    """
    payload = {
        "draft": draft,
        "context": {"customer_message": customer_message} if customer_message else {},
        "mode": mode,
        "tenant_id": tenant_id,
    }
    resp = _client.post("/v1/verify", json=payload)
    return json.dumps(resp.json(), indent=2)


@server.tool(
    name="verify_action",
    description=(
        "Pre-flight authorization gate for tool calls and actions (e.g. issue_refund, apply_discount, "
        "cancel_booking). Validates requested tool arguments against enterprise business constraints "
        "and rate limits before execution. Returns whether the action is permitted or blocked."
    ),
)
async def verify_action(
    action_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    tenant_id: str = "default",
) -> str:
    """Pre-flight authorization check for action-tools.

    Args:
        action_name: The name of the tool/action to invoke (e.g. 'issue_refund', 'apply_discount').
        parameters: Key-value parameters to pass to the tool.
        tenant_id: Tenant or organization identifier.

    Returns:
        JSON string with authorization decision, reason, policy clause, and audit sequence.
    """
    payload = {
        "action_name": action_name,
        "parameters": parameters or {},
        "tenant_id": tenant_id,
    }
    resp = _client.post("/v1/verify/action", json=payload)
    return json.dumps(resp.json(), indent=2)


@server.tool(
    name="check_audit_trail",
    description=(
        "Cryptographically verifies the Satyahd ledger integrity. Validates the continuous "
        "SHA-256 hash chain and Ed25519 asymmetric signatures across all interaction records "
        "to prove non-repudiation and zero tampering."
    ),
)
async def check_audit_trail(limit: int = 100) -> str:
    """Audits the cryptographic hash chain and signatures.

    Args:
        limit: Number of recent audit records to verify (default: 100).

    Returns:
        JSON string showing whether the hash chain is intact, count of verified entries,
        and legal non-repudiation status.
    """
    resp = _client.get("/v1/audit/verify")
    return json.dumps(resp.json(), indent=2)


@server.tool(
    name="get_active_policies",
    description=(
        "Retrieves active business rules and policy constraints currently enforced by Satyahd "
        "(e.g. refund windows, bereavement discount documentation requirements, maximum discount thresholds)."
    ),
)
async def get_active_policies(rule_pack: str = "all") -> str:
    """Lists current enterprise policy constraints.

    Args:
        rule_pack: Specific rule pack name or 'all' for active rules.

    Returns:
        JSON string containing active policy clauses, thresholds, and conditions.
    """
    resp = _client.get("/v1/rules")
    return json.dumps(resp.json(), indent=2)


def main():
    """Runs the MCP server using standard I/O (stdio) transport for Claude Desktop / Cursor."""
    print("Starting Satyahd MCP Server (stdio transport)...", file=sys.stderr)
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
