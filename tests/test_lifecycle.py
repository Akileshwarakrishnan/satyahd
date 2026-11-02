"""Tests for Requirement 9 — Promise Lifecycle Tracking and Fulfillment Monitoring."""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.extract import Promise
from app.lifecycle import (
    LifecycleState,
    check_commitments_fulfillment,
    get_commitments_summary,
    update_promise_lifecycle,
)
from app.main import app


@pytest.fixture()
def db_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "test_lifecycle.db"
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("ALLOW_MOCK", "true")
    init_db(str(db))
    return db


def test_initial_promise_lifecycle_states(db_file: Path) -> None:
    client = TestClient(app)
    # Chat with over-eager agent -> gets rewritten -> promise lifecycle becomes 'sent'
    r = client.post(
        "/chat",
        data={
            "session_id": "sess_life_1",
            "agent_id": "B",
            "mode": "over_eager",
            "message": "Can I get 50% discount?",
        },
    )
    assert r.status_code == 200
    iid = r.json()["interaction_id"]

    with get_db(str(db_file)) as conn:
        promises = conn.execute("SELECT * FROM promises WHERE interaction_id=?", (iid,)).fetchall()

    assert len(promises) >= 1
    # Safe rewritten promise delivered to customer should be 'sent'
    sent_promises = [p for p in promises if p["lifecycle_state"] == "sent"]
    assert len(sent_promises) >= 1


def test_update_promise_lifecycle_transitions(db_file: Path) -> None:
    # Insert test promise in 'sent' state
    import uuid
    pid = f"prm_{uuid.uuid4().hex[:12]}"
    iid = f"int_{uuid.uuid4().hex[:12]}"
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_db(str(db_file)) as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, status, created_at) "
            "VALUES (?, 's1', 'A', 'careful', 'hi', 'allowed', ?)",
            (iid, now_str),
        )
        conn.execute(
            "INSERT INTO promises (id, interaction_id, type, value, unit, quote, confidence, verdict, reason, lifecycle_state) "
            "VALUES (?, ?, 'discount', 10.0, 'percent', '10%', 1.0, 'allow', 'ok', 'sent')",
            (pid, iid),
        )

    # 1. Transition 'sent' -> 'fulfilled'
    res = update_promise_lifecycle(pid, "fulfilled", actor="warehouse_system")
    assert res["new_state"] == "fulfilled"

    with get_db(str(db_file)) as conn:
        row = conn.execute("SELECT * FROM promises WHERE id=?", (pid,)).fetchone()
    assert row["lifecycle_state"] == "fulfilled"
    assert row["fulfilled_at"] is not None

    # 2. Terminal state 'fulfilled' cannot transition back to 'proposed'
    with pytest.raises(ValueError, match="Illegal transition"):
        update_promise_lifecycle(pid, "proposed", actor="system")


def test_fulfillment_monitor_expired_delivery(db_file: Path) -> None:
    import uuid
    pid = f"prm_{uuid.uuid4().hex[:12]}"
    iid = f"int_{uuid.uuid4().hex[:12]}"
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Past delivery deadline (yesterday)
    yesterday_str = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).date().isoformat()

    with get_db(str(db_file)) as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, status, created_at) "
            "VALUES (?, 's2', 'A', 'careful', 'delivery query', 'allowed', ?)",
            (iid, now_str),
        )
        conn.execute(
            "INSERT INTO promises (id, interaction_id, type, value, unit, quote, confidence, verdict, reason, lifecycle_state, due_date) "
            "VALUES (?, ?, 'delivery', 3.0, 'days', '3 days', 1.0, 'allow', 'ok', 'sent', ?)",
            (pid, iid, yesterday_str),
        )

    # Run monitor against today
    today_str = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    scan = check_commitments_fulfillment(current_date_str=today_str)

    assert scan["scanned_commitments"] >= 1
    assert scan["flagged_commitments"] >= 1
    flagged_ids = [f["promise_id"] for f in scan["flagged_details"]]
    assert pid in flagged_ids

    # Verify state in DB changed to 'flagged'
    with get_db(str(db_file)) as conn:
        row = conn.execute("SELECT * FROM promises WHERE id=?", (pid,)).fetchone()
    assert row["lifecycle_state"] == "flagged"
    assert "expired" in row["flagged_reason"].lower()


def test_commitments_summary_api(db_file: Path) -> None:
    client = TestClient(app)
    r = client.get("/promises")
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "total" in data["summary"]
    assert "sent" in data["summary"]
    assert "fulfilled" in data["summary"]
