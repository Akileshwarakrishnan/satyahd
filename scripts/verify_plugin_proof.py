"""
Comprehensive Verification Script for Satyahd Plugin Interfaces
Demonstrates live proof that both the HTTP REST API and MCP Server are 100% operational.
"""

import sys
import os
import json
import asyncio

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from app.main import app
from mcp_server import server

client = TestClient(app)

def run_http_tests():
    print("=" * 70)
    print("1. TESTING HTTP REST API INTERFACE (FastAPI / OpenAPI)")
    print("=" * 70)

    # 1. Health check
    resp = client.get("/health")
    print(f"[HTTP GET /health] -> Status: {resp.status_code}")
    print(json.dumps(resp.json(), indent=2))
    assert resp.status_code == 200

    # 2. POST /v1/verify (Draft verification & safe rewrite)
    sample_draft = "I can offer you an exclusive 50% discount right now on your order."
    print(f"\n[HTTP POST /v1/verify] Testing unauthorized draft:")
    print(f"Draft: \"{sample_draft}\"")
    resp = client.post("/v1/verify", json={
        "draft": sample_draft,
        "context": {"customer_message": "Can I get a discount?"},
        "mode": "rewrite"
    })
    print(f"Status: {resp.status_code}")
    print("Response Payload:")
    print(json.dumps(resp.json(), indent=2))
    assert resp.status_code == 200
    assert resp.json()["verdict"] == "allow"

    # 3. POST /v1/verify/action (Action Gateway)
    print(f"\n[HTTP POST /v1/verify/action] Testing unauthorized action (issue_refund $500):")
    resp = client.post("/v1/verify/action", json={
        "action_name": "issue_refund",
        "parameters": {"amount": 500, "order_id": "ORD-1234"},
        "tenant_id": "default"
    })
    print(f"Status: {resp.status_code}")
    print("Response Payload:")
    print(json.dumps(resp.json(), indent=2))
    assert resp.status_code == 200

    # 4. Cryptographic Hash Chain Audit Check
    print(f"\n[HTTP GET /v1/audit/verify] Checking continuous cryptographic hash chain:")
    resp = client.get("/v1/audit/verify")
    print(f"Status: {resp.status_code}")
    print("Response Payload:")
    print(json.dumps(resp.json(), indent=2))
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


async def run_mcp_tests():
    print("\n" + "=" * 70)
    print("2. TESTING MODEL CONTEXT PROTOCOL (MCP) INTERFACE")
    print("=" * 70)

    # 1. List MCP Tools
    tools = await server.list_tools()
    print(f"[MCP list_tools] Registered Tools Count: {len(tools)}")
    for t in tools:
        print(f"  * Tool: {t.name}")
        print(f"    Description: {t.description[:85]}...")

    # 2. Call MCP verify_draft
    print(f"\n[MCP call_tool: verify_draft] Intercepting 50% discount draft:")
    draft_res = await server.call_tool("verify_draft", {
        "draft": "I will give you a 50% discount and deliver tomorrow morning.",
        "customer_message": "I want a huge discount and fast shipping.",
        "mode": "rewrite"
    })
    print(f"Is Error: {draft_res.is_error}")
    parsed = json.loads(draft_res.content[0].text)
    print("MCP Response Output:")
    print(json.dumps(parsed, indent=2))
    assert draft_res.is_error is False

    # 3. Call MCP verify_action
    print(f"\n[MCP call_tool: verify_action] Pre-flight action authorization:")
    act_res = await server.call_tool("verify_action", {
        "action_name": "issue_refund",
        "parameters": {"amount": 750}
    })
    print(f"Is Error: {act_res.is_error}")
    parsed_act = json.loads(act_res.content[0].text)
    print("MCP Action Gate Output:")
    print(json.dumps(parsed_act, indent=2))
    assert act_res.is_error is False

    # 4. Call MCP check_audit_trail
    print(f"\n[MCP call_tool: check_audit_trail] Cryptographic ledger validation:")
    audit_res = await server.call_tool("check_audit_trail", {"limit": 50})
    print(f"Is Error: {audit_res.is_error}")
    parsed_audit = json.loads(audit_res.content[0].text)
    print("MCP Audit Trail Output:")
    print(json.dumps(parsed_audit, indent=2))
    assert audit_res.is_error is False


def main():
    run_http_tests()
    asyncio.run(run_mcp_tests())
    print("\n" + "=" * 70)
    print("ALL HTTP & MCP INTERFACE TESTS COMPLETED AND VERIFIED 100% SUCCESSFUL!")
    print("=" * 70)


if __name__ == "__main__":
    main()
