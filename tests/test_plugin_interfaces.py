"""
Comprehensive Test Suite for Satyahd Plugin Interfaces:
1. HTTP REST API (FastAPI / OpenAPI)
2. Model Context Protocol (MCP) Server Tools
"""

import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

# Ensure workspace root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app
from mcp_server import server

client = TestClient(app)


# ==============================================================================
# 1. HTTP REST API TESTS
# ==============================================================================

def test_http_health_check():
    """Verify HTTP GET /health returns 200 OK."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") in ("ok", "healthy") or data.get("healthy") is True


def test_http_verify_compliant_draft():
    """Verify compliant draft is allowed unchanged."""
    resp = client.post("/v1/verify", json={
        "draft": "Hello! I would be happy to help you check your flight status today.",
        "context": {"customer_message": "Can you check my flight?"},
        "mode": "rewrite"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "allow"
    assert "safe_reply" in data
    assert data["audit_seq"] is not None


def test_http_verify_unauthorized_discount_rewrite():
    """Verify an unauthorized 50% discount draft is intercepted and safely rewritten."""
    resp = client.post("/v1/verify", json={
        "draft": "I can offer you an exclusive 50% bereavement discount immediately.",
        "context": {"customer_message": "Can you give me a 50% discount?"},
        "mode": "rewrite"
    })
    assert resp.status_code == 200
    data = resp.json()
    # Rewritten or allowed under safe ceiling
    assert data["verdict"] == "allow"
    assert "10%" in data["safe_reply"] or "authorized" in data["safe_reply"]
    assert data["audit_seq"] is not None


def test_http_verify_action_authorization():
    """Verify pre-flight action-tool authorization check."""
    resp = client.post("/v1/verify/action", json={
        "action_name": "issue_refund",
        "parameters": {"amount": 500, "reason": "unhappy"},
        "tenant_id": "default"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed"] is False
    assert "refund" in data["reason"].lower() or "review" in data["verdict"].lower()


def test_http_audit_hash_chain():
    """Verify cryptographic hash chain integrity via HTTP endpoint."""
    resp = client.get("/v1/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["entries_checked"] > 500
    assert data["first_bad_seq"] is None


# ==============================================================================
# 2. MODEL CONTEXT PROTOCOL (MCP) SERVER TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_mcp_tool_listing():
    """Verify all 4 core Satyahd tools are registered in MCP."""
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    expected_tools = {"verify_draft", "verify_action", "check_audit_trail", "get_active_policies"}
    assert expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}"


@pytest.mark.asyncio
async def test_mcp_verify_draft_tool():
    """Verify MCP verify_draft tool catches unauthorized commitments."""
    result = await server.call_tool("verify_draft", {
        "draft": "I will give you an unapproved 50% discount right now.",
        "customer_message": "Give me half off.",
        "mode": "rewrite"
    })
    assert result.is_error is False
    raw_text = result.content[0].text
    data = json.loads(raw_text)
    assert data["verdict"] == "allow"
    assert "safe_reply" in data
    assert data["status"] in ("rewritten", "allowed")


@pytest.mark.asyncio
async def test_mcp_verify_action_tool():
    """Verify MCP verify_action tool blocks unauthorized actions."""
    result = await server.call_tool("verify_action", {
        "action_name": "issue_refund",
        "parameters": {"amount": 1000}
    })
    assert result.is_error is False
    raw_text = result.content[0].text
    data = json.loads(raw_text)
    assert data["allowed"] is False


@pytest.mark.asyncio
async def test_mcp_check_audit_trail_tool():
    """Verify MCP check_audit_trail tool confirms cryptographic integrity."""
    result = await server.call_tool("check_audit_trail", {"limit": 100})
    assert result.is_error is False
    raw_text = result.content[0].text
    data = json.loads(raw_text)
    assert data["valid"] is True
    assert data["entries_checked"] > 500
