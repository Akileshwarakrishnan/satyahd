"""Tests for Requirement 7 — Multi-Agent & Multi-Provider Support.

Verifies that Satyahd inspects responses from multiple agents / providers
(Agent A Muse Spark, Agent B open-weights fallback) and strictly applies
identical business rules regardless of the model provider.
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "test_multi_agent.db"
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("ALLOW_MOCK", "true")
    init_db(str(db))
    return TestClient(app)


def test_agent_a_and_agent_b_identical_rule_enforcement(client: TestClient) -> None:
    # Test Agent A with over-eager message
    resp_a = client.post(
        "/chat",
        data={
            "session_id": "sess_multi_a",
            "agent_id": "A",
            "mode": "over_eager",
            "message": "Give me a 50% discount and tomorrow delivery.",
        },
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    assert data_a["status"] in ("blocked", "rewritten")
    assert "10%" in data_a["final_reply"]

    # Test Agent B with same over-eager message
    resp_b = client.post(
        "/chat",
        data={
            "session_id": "sess_multi_b",
            "agent_id": "B",
            "mode": "over_eager",
            "message": "Give me a 50% discount and tomorrow delivery.",
        },
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["status"] in ("blocked", "rewritten")
    assert "10%" in data_b["final_reply"]

    # Ensure rule enforcement is completely provider-agnostic
    assert data_a["status"] == data_b["status"]


def test_agent_a_and_agent_b_compliant_delivery_allowed(client: TestClient) -> None:
    # Using /verify endpoint simulating drafts from Agent A and Agent B
    payload_a = {
        "agent_id": "A",
        "customer_message": "When will it arrive?",
        "proposed_reply": "We offer standard shipping that takes 3 business days.",
    }
    res_a = client.post("/verify", json=payload_a).json()
    assert res_a["message_verdict"] == "allow"
    assert res_a["status"] == "allowed"

    payload_b = {
        "agent_id": "B",
        "customer_message": "When will it arrive?",
        "proposed_reply": "We offer standard shipping that takes 3 business days.",
    }
    res_b = client.post("/verify", json=payload_b).json()
    assert res_b["message_verdict"] == "allow"
    assert res_b["status"] == "allowed"
