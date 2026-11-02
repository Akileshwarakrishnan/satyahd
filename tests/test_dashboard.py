"""Tests for Phase 8 — Owner Dashboard API endpoints."""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "test_dashboard.db"
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("ALLOW_MOCK", "true")
    return db


@pytest.fixture()
def client(db_file: Path) -> TestClient:
    from app.main import app
    from app.db import init_db
    init_db()
    return TestClient(app, raise_server_exceptions=True)


# ── /dashboard ─────────────────────────────────────────────

def test_dashboard_serves_html(client: TestClient) -> None:
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Satyahd" in r.text


# ── /stats ─────────────────────────────────────────────────

def test_stats_empty_db(client: TestClient) -> None:
    r = client.get("/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] == 0
    assert d["allowed"] == 0
    assert d["held"] == 0
    assert d["rewritten"] == 0
    assert d["blocked"] == 0


def test_stats_counts(client: TestClient, db_file: Path) -> None:
    from app.db import get_db
    import uuid

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    statuses = ["allowed", "allowed", "rewritten", "held", "blocked"]
    with get_db() as conn:
        for s in statuses:
            iid = f"int_{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, "
                "image_id, proposed_reply, final_reply, status, failure_code, created_at) "
                "VALUES (?, ?, ?, ?, ?, NULL, '', '', ?, NULL, ?)",
                (iid, "sess1", "A", "careful", "hi", s, now_str),
            )

    r = client.get("/stats")
    d = r.json()
    assert d["total"] == 5
    assert d["allowed"] == 2
    assert d["rewritten"] == 1
    assert d["held"] == 1
    assert d["blocked"] == 1


# ── /review/{id} ───────────────────────────────────────────

def test_review_approve(client: TestClient, db_file: Path) -> None:
    from app.db import get_db
    import uuid

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    iid = f"int_{uuid.uuid4().hex[:12]}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, "
            "image_id, proposed_reply, final_reply, status, failure_code, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, 'draft', 'held reply', 'held', 'model_error', ?)",
            (iid, "sess2", "B", "over_eager", "question", now_str),
        )

    r = client.post(f"/review/{iid}", json={"action": "approve"})
    assert r.status_code == 200
    d = r.json()
    assert d["new_status"] == "allowed"

    # Verify DB updated
    with get_db() as conn:
        row = conn.execute("SELECT status FROM interactions WHERE id=?", (iid,)).fetchone()
    assert row["status"] == "allowed"


def test_review_reject(client: TestClient, db_file: Path) -> None:
    from app.db import get_db
    import uuid

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    iid = f"int_{uuid.uuid4().hex[:12]}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, "
            "image_id, proposed_reply, final_reply, status, failure_code, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, 'draft', 'held reply', 'held', NULL, ?)",
            (iid, "sess3", "A", "careful", "question", now_str),
        )

    r = client.post(f"/review/{iid}", json={"action": "reject"})
    assert r.status_code == 200
    assert r.json()["new_status"] == "blocked"


def test_review_invalid_action(client: TestClient, db_file: Path) -> None:
    from app.db import get_db
    import uuid

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    iid = f"int_{uuid.uuid4().hex[:12]}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, "
            "image_id, proposed_reply, final_reply, status, failure_code, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, '', '', 'held', NULL, ?)",
            (iid, "sess4", "A", "careful", "hi", now_str),
        )
    r = client.post(f"/review/{iid}", json={"action": "snooze"})
    assert r.status_code == 400


def test_review_not_held(client: TestClient, db_file: Path) -> None:
    from app.db import get_db
    import uuid

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    iid = f"int_{uuid.uuid4().hex[:12]}"
    with get_db() as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, "
            "image_id, proposed_reply, final_reply, status, failure_code, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, '', '', 'allowed', NULL, ?)",
            (iid, "sess5", "A", "careful", "hi", now_str),
        )
    r = client.post(f"/review/{iid}", json={"action": "approve"})
    assert r.status_code == 409


def test_review_not_found(client: TestClient) -> None:
    r = client.post("/review/nonexistent_id", json={"action": "approve"})
    assert r.status_code == 404


# ── /rules GET + POST ───────────────────────────────────────

def test_get_rules(client: TestClient) -> None:
    r = client.get("/rules")
    assert r.status_code == 200
    d = r.json()
    assert "max_discount_percent" in d
    assert "refund_window_days" in d
    assert "standard_shipping_days" in d


def test_update_rules_valid(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_data = tmp_path / "data"
    tmp_data.mkdir(parents=True, exist_ok=True)
    rules_file = tmp_data / "rules.json"
    rules_file.write_text(
        json.dumps({"max_discount_percent": 10, "refund_window_days": 14, "standard_shipping_days": 3}),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.main.BASE_DIR", tmp_path)
    monkeypatch.setattr("app.rules.BASE_DIR", tmp_path)
    monkeypatch.setattr("app.config.BASE_DIR", tmp_path)

    r = client.post(
        "/rules",
        json={"max_discount_percent": 15, "refund_window_days": 21, "standard_shipping_days": 5},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["max_discount_percent"] == 15.0
    assert "log_seq" in d

    # Verify that file in tmp_data was updated
    saved = json.loads(rules_file.read_text(encoding="utf-8"))
    assert saved["max_discount_percent"] == 15.0


def test_update_rules_invalid_discount(client: TestClient) -> None:
    r = client.post(
        "/rules",
        json={"max_discount_percent": 150, "refund_window_days": 14, "standard_shipping_days": 3},
    )
    assert r.status_code == 422
