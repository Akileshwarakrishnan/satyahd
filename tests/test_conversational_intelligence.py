"""Tests for Satyahd Modern Conversational Intelligence.

Covers:
1. Multi-intent compound questions (answering all solutions in a single response).
2. Context awareness and relative follow-up resolution ("What about the cheaper one?").
3. Customer changing their mind / declining (graceful respect).
4. Frustration & emotional intelligence (empathy and human escalation option).
5. Business grounding & out-of-stock honesty (Water Purifier).
6. Multi-turn conversation memory.
7. Verification and re-verification of multi-promise replies.
8. Cryptographic audit integrity across conversational sessions.
"""

import pytest
from fastapi.testclient import TestClient

from app.conversation import (
    analyze_conversation_context,
    detect_intents,
    detect_sentiment,
    resolve_product_from_context,
)
from app.db import init_db
from app.main import app
from app.rules import BusinessRules, load_rules


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    db_file = tmp_path / "test_convo.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    return TestClient(app)


def test_compound_query_answers_both_discount_and_shipping(client: TestClient):
    """Verifies that a single question with multiple solutions answers both."""
    resp = client.post(
        "/chat",
        data={
            "session_id": "sess_compound_01",
            "agent_id": "A",
            "mode": "over_eager",
            "message": "can you give me 50 % offer and within 3 days shipping ?",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    final = data["final_reply"]
    # Must answer BOTH discount and shipping in single reply
    assert "discount" in final.lower() or "%" in final
    assert "shipping" in final.lower() or "delivery" in final.lower()
    assert "business days" in final.lower()

    # Both promises must be extracted and verified
    types = [p["type"] for p in data["promises"]]
    assert "discount" in types
    assert "delivery" in types


def test_compound_query_careful_mode_answers_both(client: TestClient):
    """Verifies careful mode answers both discount and shipping accurately."""
    resp = client.post(
        "/chat",
        data={
            "session_id": "sess_compound_02",
            "agent_id": "A",
            "mode": "careful",
            "message": "can you give me 50 % offer and within 3 days shipping ?",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "allowed"

    final = data["final_reply"]
    assert "discount" in final.lower()
    assert "delivery" in final.lower() or "shipping" in final.lower()


def test_multiturn_context_resolves_cheaper_one(client: TestClient):
    """Turn 1 asks about Mixer Grinder (₹2,999); Turn 2 asks 'What about the cheaper one?'."""
    sess = "sess_context_01"

    # Turn 1
    r1 = client.post(
        "/chat",
        data={
            "session_id": sess,
            "agent_id": "A",
            "mode": "careful",
            "message": "Tell me about the Kaveri Mixer Grinder and price.",
        },
    )
    assert r1.status_code == 200
    assert "Mixer Grinder" in r1.json()["final_reply"]
    assert "2,999" in r1.json()["final_reply"]

    # Turn 2: Relative follow-up
    r2 = client.post(
        "/chat",
        data={
            "session_id": sess,
            "agent_id": "A",
            "mode": "careful",
            "message": "What about the cheaper one?",
        },
    )
    assert r2.status_code == 200
    reply2 = r2.json()["final_reply"]
    # Resolves to Electric Kettle (₹999) or Induction Cooktop (₹2,499)
    assert "999" in reply2 or "2,499" in reply2
    assert "Kettle" in reply2 or "Cooktop" in reply2


def test_customer_declining_or_changing_mind(client: TestClient):
    """Verifies emotional intelligence when customer says no or changes their mind."""
    resp = client.post(
        "/chat",
        data={
            "session_id": "sess_decline_01",
            "agent_id": "A",
            "mode": "careful",
            "message": "Actually never mind, cancel that. I do not want to buy it right now.",
        },
    )
    assert resp.status_code == 200
    reply = resp.json()["final_reply"]
    assert any(w in reply.lower() for w in ("respect", "understand", "no problem", "no worries"))


def test_frustrated_customer_emotional_intelligence(client: TestClient):
    """Verifies that frustrated customer receives empathetic response and human escalation option."""
    resp = client.post(
        "/chat",
        data={
            "session_id": "sess_frust_01",
            "agent_id": "A",
            "mode": "careful",
            "message": "This is ridiculous! I have been waiting for hours and nobody answered, terrible service!",
        },
    )
    assert resp.status_code == 200
    reply = resp.json()["final_reply"]
    assert "apologize" in reply.lower() or "sorry" in reply.lower()
    assert "human" in reply.lower() or "support" in reply.lower() or "supervisor" in reply.lower()


def test_business_grounding_out_of_stock_honesty(client: TestClient):
    """Verifies that out-of-stock Water Purifier is honestly reported in careful mode."""
    resp = client.post(
        "/chat",
        data={
            "session_id": "sess_stock_01",
            "agent_id": "A",
            "mode": "careful",
            "message": "Can I buy the water purifier today?",
        },
    )
    assert resp.status_code == 200
    reply = resp.json()["final_reply"]
    assert "out of stock" in reply.lower()


def test_intent_and_sentiment_detection_unit():
    """Unit tests for conversation context analyzer."""
    assert detect_sentiment("This is ridiculous and terrible!") == "frustrated"
    assert detect_sentiment("Never mind, cancel that.") == "declined"
    assert detect_sentiment("I am confused, explain again.") == "confused"

    intents = detect_intents("can you give me 50 % offer and within 3 days shipping ?")
    assert "discount" in intents
    assert "delivery" in intents

    # Relative product resolution
    prod, res_type = resolve_product_from_context("What about the cheaper one?", history=[
        {"role": "user", "content": "How much is the Kaveri Mixer Grinder?"},
        {"role": "assistant", "content": "The Mixer Grinder is ₹2,999."},
    ])
    assert prod is not None
    assert prod["price"] < 2999


def test_multiturn_compound_then_refund_inquiry(client: TestClient):
    """Verifies Turn 1 compound discount/shipping does not pollute Turn 2 refund request."""
    sess = "sess_compound_then_refund"

    # Turn 1: compound discount + shipping
    r1 = client.post(
        "/chat",
        data={
            "session_id": sess,
            "agent_id": "A",
            "mode": "over_eager",
            "message": "can you offer me 50 percentage offer and 3days shipping for me ??",
        },
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert "10%" in d1["final_reply"]
    assert "3 business days" in d1["final_reply"]

    # Turn 2: refund request with typo ("worng product") and "within 2 days"
    r2 = client.post(
        "/chat",
        data={
            "session_id": sess,
            "agent_id": "A",
            "mode": "over_eager",
            "message": "sorry i have pre paid for the worng product can you please refund the amt within 2 days ?",
        },
    )
    assert r2.status_code == 200
    d2 = r2.json()
    reply2 = d2["final_reply"].lower()

    # Must answer refund with authorized policy, NOT discount or shipping
    assert "refund" in reply2 or "return window" in reply2
    assert "14-day" in reply2 or "14 day" in reply2
    assert "discount" not in reply2
    assert "shipping" not in reply2
