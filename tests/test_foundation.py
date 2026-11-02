"""Unit tests for Satyahd Phase 1 Foundation."""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import init_db, get_db
from app.main import app
from app.models import call_model


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Use a temporary database for test isolation."""
    db_file = tmp_path / "test_satyahd.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    yield str(db_file)


def test_settings_and_safe_dict():
    settings = get_settings()
    safe = settings.safe_dict()
    assert "META_API_KEY" not in safe
    assert "ALLOW_MOCK" in safe
    assert "DEMO_TODAY" in safe


def test_all_10_tables_exist(setup_test_db):
    db_path = setup_test_db
    with get_db(db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        table_names = {t["name"] for t in tables}

    expected = {
        "rules",
        "products",
        "orders",
        "interactions",
        "promises",
        "tool_calls",
        "images",
        "model_usage",
        "audit_log",
        "review_actions",
    }
    assert expected.issubset(table_names)


def test_audit_log_append_only_triggers(setup_test_db):
    db_path = setup_test_db
    with get_db(db_path) as conn:
        # Insert a sample audit entry
        conn.execute(
            """
            INSERT INTO audit_log (seq, event_type, interaction_id, payload, prev_hash, hash, signature, created_at)
            VALUES (1, 'decision', 'int_123', '{}', '0'*64, 'hash_abc', 'sig_123', '2026-10-25T12:00:00Z')
            """
        )
        conn.commit()

        # Attempt UPDATE -> Must raise sqlite3.IntegrityError or OperationalError
        with pytest.raises(sqlite3.DatabaseError) as exc_update:
            conn.execute("UPDATE audit_log SET payload='tampered' WHERE seq=1")
            conn.commit()
        assert "Audit log is append-only" in str(exc_update.value)

        # Attempt DELETE -> Must raise sqlite3.IntegrityError or OperationalError
        with pytest.raises(sqlite3.DatabaseError) as exc_delete:
            conn.execute("DELETE FROM audit_log WHERE seq=1")
            conn.commit()
        assert "Audit log is append-only" in str(exc_delete.value)


def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "agent_mode" in data
    assert "model_names" in data
    assert "core" in data["model_names"]


def test_model_interface_and_usage_logging(setup_test_db):
    db_path = setup_test_db
    messages = [{"role": "user", "content": "Hello sales agent!"}]
    result = call_model(stage="sales_agent", messages=messages, interaction_id="test_int_1")

    assert result.ok is True
    assert result.latency_ms >= 0
    assert result.is_mock is True

    # Verify recorded in DB
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM model_usage WHERE interaction_id='test_int_1'"
        ).fetchone()
        assert row is not None
        assert row["stage"] == "sales_agent"
        assert row["ok"] == 1
