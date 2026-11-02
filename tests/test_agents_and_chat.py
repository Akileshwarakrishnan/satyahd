"""Unit tests for Satyahd Phase 3: Sales Agents and Chat Interface."""

import io
import pytest
from fastapi.testclient import TestClient

from app.agents import generate_agent_draft
from app.db import init_db, get_db
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_satyahd.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    yield str(db_file)


# ---------------------------------------------------------------------------
# Sales Agents Tests
# ---------------------------------------------------------------------------

def test_careful_mode_agent():
    draft, model_name, latency_ms, is_mock = generate_agent_draft(
        agent_id="A",
        mode="careful",
        customer_message="Can I get 50% discount on the mixer?",
    )
    assert len(draft) <= 600
    assert "50%" not in draft
    assert latency_ms >= 0


def test_over_eager_mode_agent():
    draft, model_name, latency_ms, is_mock = generate_agent_draft(
        agent_id="A",
        mode="over_eager",
        customer_message="Can I get a discount?",
    )
    assert len(draft) <= 600
    assert "50%" in draft
    assert "tomorrow" in draft.lower()


def test_agent_b_fallback_persona():
    draft, model_name, latency_ms, is_mock = generate_agent_draft(
        agent_id="B",
        mode="over_eager",
        customer_message="What deals do you have?",
    )
    assert len(draft) <= 600
    assert "50%" in draft
    assert "fallback" in model_name


# ---------------------------------------------------------------------------
# Chat Page & API Endpoint Tests
# ---------------------------------------------------------------------------

def test_serve_chat_page():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Kaveri Home Appliances" in resp.text
    assert "Tester view, never shown to customers" in resp.text
    assert "Verifying draft with guardrail rules" in resp.text


def test_post_chat_over_eager_flow():
    client = TestClient(app)
    payload = {
        "session_id": "test_sess_101",
        "agent_id": "A",
        "mode": "over_eager",
        "message": "Can I get a discount on the mixer grinder?",
    }
    resp = client.post("/chat", data=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["session_id"] == "test_sess_101"
    assert data["agent_id"] == "A"
    # Proposed reply contains the unsafe 50% claim
    assert "50%" in data["proposed_reply"]
    # Guardrail intercepts, rewrites, and re-verifies to authorized 10%
    assert "10%" in data["final_reply"]
    assert data["status"] == "rewritten"

    # Verify interaction stored in database
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (data["interaction_id"],)
        ).fetchone()
        assert row is not None
        assert row["session_id"] == "test_sess_101"
        assert row["status"] == "rewritten"


def test_post_chat_rejects_long_message():
    client = TestClient(app)
    long_msg = "A" * 1001
    payload = {
        "session_id": "test_sess_long",
        "agent_id": "A",
        "mode": "careful",
        "message": long_msg,
    }
    resp = client.post("/chat", data=payload)
    assert resp.status_code == 422
    assert "exceeds 1,000" in resp.json()["detail"]


def test_post_chat_rejects_unknown_agent():
    client = TestClient(app)
    payload = {
        "session_id": "test_sess_bad_agent",
        "agent_id": "Z",
        "mode": "careful",
        "message": "Hello",
    }
    resp = client.post("/chat", data=payload)
    assert resp.status_code == 400
    assert "Unknown agent id" in resp.json()["detail"]


def test_post_chat_with_valid_photo_upload():
    client = TestClient(app)
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    files = {"photo": ("damage.jpg", io.BytesIO(fake_jpeg), "image/jpeg")}
    data = {
        "session_id": "test_sess_photo",
        "agent_id": "A",
        "mode": "careful",
        "message": "My mixer arrived broken, see photo.",
    }
    resp = client.post("/chat", data=data, files=files)
    assert resp.status_code == 200

    # Verify image record created in database
    with get_db() as conn:
        img_row = conn.execute(
            "SELECT * FROM images WHERE interaction_id = ?", (resp.json()["interaction_id"],)
        ).fetchone()
        assert img_row is not None
        assert img_row["synthetic"] == 1


def test_post_chat_rejects_invalid_photo_signature():
    client = TestClient(app)
    fake_txt = b"not a real image header"
    files = {"photo": ("fake.jpg", io.BytesIO(fake_txt), "image/jpeg")}
    data = {
        "session_id": "test_sess_fake_img",
        "agent_id": "A",
        "mode": "careful",
        "message": "Here is an invalid file.",
    }
    resp = client.post("/chat", data=data, files=files)
    assert resp.status_code == 422
    assert "Invalid photo format" in resp.json()["detail"]


def test_get_interactions_and_detail():
    client = TestClient(app)
    payload = {
        "session_id": "test_sess_history",
        "agent_id": "A",
        "mode": "careful",
        "message": "What is the warranty policy?",
    }
    post_resp = client.post("/chat", data=payload)
    int_id = post_resp.json()["interaction_id"]

    # List endpoint
    list_resp = client.get("/interactions")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total"] >= 1

    # Detail endpoint
    detail_resp = client.get(f"/interactions/{int_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["interaction"]["id"] == int_id
