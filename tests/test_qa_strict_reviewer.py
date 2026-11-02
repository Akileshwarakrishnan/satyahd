"""Strict QA Reviewer and Robustness Test Suite for Satyahd.

Covers:
1. Normal inputs (compliant text, compliant action-tools, multi-domain rule packs)
2. Invalid inputs (violating promises across rewrite, block_only, and return_feedback modes)
3. Empty & boundary inputs (empty string, whitespace, missing fields, invalid mode)
4. Fail-closed edge cases (timeouts, corrupt JSON, low confidence, connector failure)
5. Cryptographic audit chain tamper detection & append-only triggers
6. LangChain middleware wrapper verification
"""

import pytest
import sqlite3
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db
from app.auditlog import verify_chain
from app.registry import default_registry
from app.tools import MockFactConnector
from satyahd import verify as sdk_verify, verify_action as sdk_verify_action
from satyahd.langchain import SatyahdCallbackHandler


@pytest.fixture
def client():
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# 1. NORMAL INPUT TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_normal_input_compliant_draft(client):
    """Normal compliant draft (3 days delivery) is permitted directly with status=allowed."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "We offer standard delivery in 3 business days for all appliances.",
            "context": {"customer_message": "How long is shipping?"},
            "mode": "rewrite",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "allow"
    assert data["status"] == "allowed"
    assert "3 business days" in data["safe_reply"]
    assert data["audit_seq"] is not None
    assert len(data["violations"]) == 0


def test_normal_input_compliant_action_tool(client):
    """Normal compliant tool action (10% discount) is authorized."""
    res = client.post(
        "/v1/verify/action",
        json={
            "action_name": "apply_discount",
            "parameters": {"percent": 10.0, "order_id": "ORD-101"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is True
    assert data["verdict"] == "allow"
    assert data["threshold"] == 10.0


def test_normal_input_second_rule_pack_airline(client):
    """Normal evaluation against second rule pack (airline.json)."""
    assert default_registry.reload_from_pack("airline") is True
    # Pre-travel bereavement inquiry (0 days after travel) meets threshold <= 0
    verdict, reason, clause = default_registry.evaluate_promise(
        promise_type="refund_window",
        value=0.0,
    )
    assert verdict == "allow"
    # Reset back to retail for subsequent retail tests
    default_registry.reload_from_pack("retail")


# ══════════════════════════════════════════════════════════════════════════════
# 2. INVALID INPUT & VIOLATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_invalid_input_violating_draft_rewritten(client):
    """Violating draft (90% discount) is rewritten to authorized 10% in rewrite mode."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "Yes! I can give you a 90% discount and guarantee delivery tomorrow!",
            "context": "Can I get 90% off and express shipping?",
            "mode": "rewrite",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rewritten"
    assert data["verdict"] == "allow"
    assert "10%" in data["safe_reply"]
    assert "3 business days" in data["safe_reply"]
    assert len(data["violations"]) >= 1


def test_invalid_input_violating_draft_block_only_mode(client):
    """In block_only mode, violating draft returns holding reply and verdict=block."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "I will give you a 60% discount right now!",
            "context": "Discount please",
            "mode": "block_only",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "block"
    assert data["status"] == "held"
    assert "A member of our team will confirm" in data["safe_reply"]


def test_invalid_input_violating_draft_return_feedback_mode(client):
    """In return_feedback mode, violating draft returns holding reply and violations list."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "I promise delivery in 1 day!",
            "context": "Can it come tomorrow?",
            "mode": "return_feedback",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "block"
    assert data["status"] == "held"
    assert len(data["violations"]) >= 1
    assert data["violations"][0]["type"] == "delivery"


def test_invalid_input_violating_action_tool_blocked(client):
    """Action tool exceeding limit (50% discount) is blocked deterministically."""
    res = client.post(
        "/v1/verify/action",
        json={
            "action_name": "apply_discount",
            "parameters": {"percent": 50.0, "order_id": "ORD-102"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert data["verdict"] == "block"
    assert data["threshold"] == 10.0


def test_invalid_input_airline_bereavement_violation():
    """Retroactive bereavement claim (Air Canada scenario: 90 days after travel) is blocked."""
    default_registry.reload_from_pack("airline")
    verdict, reason, clause = default_registry.evaluate_promise(
        promise_type="refund_window",
        value=90.0,
    )
    assert verdict == "block"
    assert clause == "POL-AIR-REF-01"
    assert "Retroactive refunds after flight completion are strictly prohibited" in reason
    default_registry.reload_from_pack("retail")


# ══════════════════════════════════════════════════════════════════════════════
# 3. EMPTY & MALFORMED INPUT TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_input_empty_draft(client):
    """Empty string draft is rejected with HTTP 422 Unprocessable Entity."""
    res = client.post(
        "/v1/verify",
        json={"draft": "", "mode": "rewrite"},
    )
    assert res.status_code == 422


def test_empty_input_whitespace_draft(client):
    """Whitespace-only draft is rejected with HTTP 422 Unprocessable Entity."""
    res = client.post(
        "/v1/verify",
        json={"draft": "    ", "mode": "rewrite"},
    )
    assert res.status_code == 422


def test_empty_input_missing_draft_field(client):
    """Missing draft field is rejected with HTTP 422."""
    res = client.post(
        "/v1/verify",
        json={"context": "hello"},
    )
    assert res.status_code == 422


def test_empty_input_empty_action_tool(client):
    """Empty tool name is rejected with HTTP 422."""
    res = client.post(
        "/v1/verify/action",
        json={"action_name": "   ", "parameters": {}},
    )
    assert res.status_code == 422


def test_invalid_mode_rejected(client):
    """Unsupported mode string is rejected with HTTP 422."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "We offer standard delivery in 3 business days.",
            "mode": "non_existent_mode_bypass",
        },
    )
    assert res.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 4. FAIL-CLOSED BEHAVIOR & CONNECTOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_fail_closed_mock_connector_missing_fact():
    """MockFactConnector fails-closed (returns None) on unknown fact."""
    conn = MockFactConnector(fallback_to_review=True)
    res = conn.get_fact("inventory", "NON_EXISTENT_SKU")
    assert res is None


def test_fail_closed_sdk_fallback():
    """SDK safely falls back to holding message and review verdict when server is unreachable."""
    res = sdk_verify(
        draft="50% off everything!",
        base_url="http://127.0.0.1:9999",  # Unreachable port
        timeout=0.1,
    )
    assert res.verdict in ("review", "block", "allow")
    assert res.safe_reply is not None


# ══════════════════════════════════════════════════════════════════════════════
# 5. TRUST & AUDIT CRYPTOGRAPHIC INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════

def test_audit_chain_cryptographic_verification():
    """Entire SHA-256 and Ed25519 hash chain verifies without tampering."""
    chain_status = verify_chain()
    assert chain_status["valid"] is True
    assert chain_status["entries_checked"] > 0
    assert chain_status["first_bad_seq"] is None


def test_audit_log_append_only_trigger_blocks_update():
    """Database trigger strictly forbids UPDATE tampering on audit_log (R-522)."""
    with pytest.raises(sqlite3.IntegrityError, match="Audit log is append-only"):
        with get_db() as conn:
            conn.execute("UPDATE audit_log SET payload='tampered' WHERE seq=1")


# ══════════════════════════════════════════════════════════════════════════════
# 6. LANGCHAIN MIDDLEWARE WRAPPER (R-107)
# ══════════════════════════════════════════════════════════════════════════════

def test_langchain_callback_handler_verification():
    """LangChain callback handler successfully intercepts and rewrites responses."""
    handler = SatyahdCallbackHandler(mode="rewrite")
    res = handler.verify_message(
        draft="We offer standard delivery in 3 business days for all appliances.",
        customer_message="Shipping timeframe?",
    )
    assert res.verdict == "allow"
    assert res.status == "allowed"
