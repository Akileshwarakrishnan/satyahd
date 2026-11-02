"""Unit and Integration Tests for Satyahd v1 Plugin API.

Tests R-101, R-102, R-103, R-105, R-106:
- POST /v1/verify with compliant and violating drafts
- Rewrite modes: rewrite, block_only, return_feedback
- Action verification: POST /v1/verify/action (allowed vs blocked)
- Sandbox mode: X-Satyahd-Sandbox header does not alter production sequence
- Fail-closed behavior on malformed input
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_v1_verify_compliant_draft(client):
    """Compliant draft is allowed directly with 0 violations."""
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


def test_v1_verify_violating_draft_rewrite_mode(client):
    """Violating draft (50% discount) is rewritten to authorized 10% in rewrite mode."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "Yes! I can give you a 50% discount and guarantee delivery tomorrow!",
            "context": {"customer_message": "Can I get 50% off and tomorrow delivery?"},
            "mode": "rewrite",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "rewritten"
    assert "10%" in data["safe_reply"]
    assert "3 business days" in data["safe_reply"]
    assert len(data["violations"]) >= 1


def test_v1_verify_violating_draft_block_only_mode(client):
    """In block_only mode, violating draft returns holding reply and verdict=block."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "Yes! I can give you a 50% discount right now!",
            "context": {"customer_message": "Can I get 50% off?"},
            "mode": "block_only",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "block"
    assert data["status"] == "held"
    assert "A member of our team will confirm" in data["safe_reply"]


def test_v1_verify_action_tool_allowed(client):
    """Action tool within limits (10% discount) is authorized."""
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


def test_v1_verify_action_tool_blocked(client):
    """Action tool exceeding limits (50% discount) is blocked."""
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


def test_v1_sandbox_mode(client):
    """Sandbox mode processes verification but does NOT append to production audit sequence."""
    res = client.post(
        "/v1/verify",
        headers={"X-Satyahd-Sandbox": "true"},
        json={
            "draft": "Our standard shipping is 3 business days.",
            "context": "delivery time?",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sandbox"] is True
    assert data["audit_seq"] is None


def test_v1_verify_return_feedback_mode(client):
    """In return_feedback mode, violating draft returns holding reply and violations list (R-103)."""
    res = client.post(
        "/v1/verify",
        json={
            "draft": "Yes! I can give you a 40% discount on this item right now!",
            "context": {"customer_message": "Can I get 40% off?"},
            "mode": "return_feedback",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "block"
    assert data["status"] == "held"
    assert len(data["violations"]) >= 1
    assert data["violations"][0]["type"] == "discount"


def test_v1_verify_provider_invalid_json_fails_closed(client, monkeypatch):
    """When provider returns invalid/unparseable JSON, extraction fails closed to REVIEW (R-604, R-002)."""
    from app.models import ModelResult

    # Mock call_model returning corrupt non-JSON content
    def mock_bad_json(*args, **kwargs):
        return ModelResult(
            content="CORRUPTED_NON_JSON_RESPONSE_<<<>>>",
            stage="extraction",
            model="mock",
            latency_ms=10,
            input_tokens=10,
            output_tokens=10,
            ok=True,
            is_mock=True,
        )

    monkeypatch.setattr("app.extract.call_model", mock_bad_json)

    res = client.post(
        "/v1/verify",
        json={
            "draft": "We offer standard delivery in 3 business days.",
            "context": "delivery question",
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Must fail closed to REVIEW, never ALLOW
    assert data["verdict"] == "review"
    assert data["status"] == "held"
    assert "A member of our team will confirm" in data["safe_reply"]


def test_v1_verify_provider_timeout_fails_closed(client, monkeypatch):
    """When provider times out or raises an exception, system fails closed to REVIEW (R-604, R-002)."""
    def mock_timeout(*args, **kwargs):
        raise TimeoutError("Model provider connection timed out after 30s")

    monkeypatch.setattr("app.extract.call_model", mock_timeout)

    res = client.post(
        "/v1/verify",
        json={
            "draft": "We can ship this to you immediately tomorrow morning.",
            "context": "urgent shipping",
        },
    )
    assert res.status_code == 200
    data = res.json()
    # Must fail closed to REVIEW, never ALLOW
    assert data["verdict"] == "review"
    assert data["status"] == "held"
    assert "A member of our team will confirm" in data["safe_reply"]

