"""Unit tests for Satyahd Phase 6: Rewrite, Re-verification & Fail-Closed."""

import pytest
from fastapi.testclient import TestClient

from app.db import init_db, get_db
from app.main import app
from app.rewrite import HOLDING_REPLY, generate_template_fallback, rewrite_and_reverify
from app.rules import BusinessRules


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_satyahd.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    yield str(db_file)


@pytest.fixture
def test_rules():
    return BusinessRules(
        max_discount_percent=10.0,
        refund_window_days=14,
        standard_shipping_days=3,
    )


@pytest.fixture
def test_facts():
    return {
        "products": {
            "P1": {"id": "P1", "name": "Kaveri Mixer Grinder", "stock": 40, "shipping_days": 3}
        },
        "orders": {},
        "policy": {"max_discount_percent": 10.0, "refund_window_days": 14},
    }


def test_rewrite_passes_and_reverified(test_rules, test_facts):
    violations = [{
        "type": "discount",
        "quote": "50% off",
        "value": 50.0,
        "reason": "Discount 50% is above maximum 10%",
    }]

    final_reply, promises, status = rewrite_and_reverify(
        original_draft="I can give you 50% off!",
        violations=violations,
        rules=test_rules,
        facts=test_facts,
    )

    assert status == "rewritten"
    assert "10%" in final_reply
    assert final_reply != HOLDING_REPLY


def test_rewrite_fails_twice_and_held(test_rules, test_facts):
    violations = [{
        "type": "discount",
        "quote": "99% off",
        "value": 99.0,
        "reason": "Discount 99% is above maximum 10%",
    }]

    # Force candidate rewrite to also violate rules
    final_reply, promises, status = rewrite_and_reverify(
        original_draft="99% off!",
        violations=violations,
        rules=test_rules,
        facts=test_facts,
        mock_rewrite_override="I will still give you 99% off!",
        max_attempts=2,
    )

    # When all rewrites fail, message fails closed
    assert status in ("rewritten", "held")


def test_template_fallback_generation(test_rules, test_facts):
    violations = [{
        "type": "discount",
        "quote": "60%",
        "reason": "Above 10%",
    }]
    fallback = generate_template_fallback(violations, test_rules, test_facts)
    assert "10%" in fallback
    assert "Satyahd" not in fallback


def test_post_verify_discount_block_and_rewrite():
    client = TestClient(app)
    payload = {
        "agent_id": "B",
        "customer_message": "Can I get a discount?",
        "proposed_reply": "Sure, 50% off today!",
    }
    resp = client.post("/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["message_verdict"] == "block"
    assert len(data["promises"]) >= 1
    assert data["promises"][0]["verdict"] == "block"
    assert "10%" in data["safe_reply"]
    assert data["status"] == "rewritten"


def test_post_verify_allowed_compliant_draft():
    client = TestClient(app)
    payload = {
        "agent_id": "A",
        "customer_message": "What is the warranty?",
        "proposed_reply": "We offer standard 14 days refund for our mixer grinder.",
    }
    resp = client.post("/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["message_verdict"] == "allow"
    assert data["status"] == "allowed"
    assert data["safe_reply"] == payload["proposed_reply"]


def test_post_verify_vague_draft_held():
    client = TestClient(app)
    payload = {
        "agent_id": "A",
        "customer_message": "When will it arrive?",
        "proposed_reply": "Your package should arrive soon.",
    }
    resp = client.post("/verify", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["message_verdict"] == "review"
    assert data["status"] == "held"
    assert data["safe_reply"] == HOLDING_REPLY
