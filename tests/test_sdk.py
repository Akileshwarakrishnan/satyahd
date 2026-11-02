"""Unit Tests for Satyahd Universal Python SDK.

Tests R-104:
- satyahd.verify() with compliant and violating drafts
- satyahd.verify_action() with permitted and blocked tools
- Fail-closed fallback: when server is unreachable, SDK returns fallback message and verdict="review"
"""

from fastapi.testclient import TestClient
import pytest
import satyahd
from app.main import app


@pytest.fixture
def sdk_client():
    test_cli = TestClient(app)
    return satyahd.SatyahdClient(base_url="http://testserver", http_client=test_cli)


def test_sdk_verify_live(sdk_client):
    """SDK verify() against local Satyahd instance."""
    res = sdk_client.verify(
        draft="Standard delivery is 3 business days for all orders.",
        customer_message="How fast can you ship?",
        mode="rewrite",
    )
    assert res.is_allowed is True
    assert "3 business days" in res.safe_reply


def test_sdk_verify_rewriting(sdk_client):
    """SDK verify() rewrites unauthorized 50% discount to 10%."""
    res = sdk_client.verify(
        draft="I can give you 50% off right now!",
        customer_message="Can I get a discount?",
        mode="rewrite",
    )
    assert res.is_allowed is True
    assert "10%" in res.safe_reply


def test_sdk_verify_action_allowed(sdk_client):
    """SDK verify_action() permits 10% discount."""
    act = sdk_client.verify_action(
        tool_name="apply_discount",
        arguments={"percent": 10.0, "order_id": "ORD-1"},
    )
    assert act.allowed is True
    assert act.verdict == "allow"


def test_sdk_verify_action_blocked(sdk_client):
    """SDK verify_action() blocks 50% discount."""
    act = sdk_client.verify_action(
        tool_name="apply_discount",
        arguments={"percent": 50.0, "order_id": "ORD-1"},
    )
    assert act.allowed is False
    assert act.verdict == "block"


def test_sdk_fail_closed_on_unreachable_server():
    """When Satyahd server is unreachable, SDK fails closed safely."""
    client = satyahd.SatyahdClient(
        base_url="http://127.0.0.1:9999",  # non-existent port
        timeout=0.5,
        fail_closed_message="Custom holding message",
    )
    res = client.verify(draft="I promise 50% discount!")
    assert res.verdict == "review"
    assert res.status == "held"
    assert res.safe_reply == "Custom holding message"
    assert res.is_allowed is False
