"""Tests for Stretch Features (Section 3.16 & 3.17).

Tests:
1. GET /receipt/{id} returns PNG bytes
2. GET /dispute/{id} returns full dispute report JSON
3. GET /models/usage returns per-model aggregated statistics
"""

from __future__ import annotations

import datetime
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db = tmp_path / "test_stretch.db"
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("ALLOW_MOCK", "true")
    init_db(str(db))

    iid = "int_stretch_001"
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db(str(db)) as conn:
        conn.execute(
            "INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, status, created_at) "
            "VALUES (?, 's_stretch', 'A', 'careful', 'Do you have mixer?', 'allowed', ?)",
            (iid, now_str),
        )
        conn.execute(
            "INSERT INTO promises (id, interaction_id, type, value, unit, quote, confidence, verdict, reason, lifecycle_state) "
            "VALUES ('prm_stretch_1', ?, 'delivery', 3.0, 'days', '3 days', 0.95, 'allow', 'Satisfies standard shipping', 'sent')",
            (iid,),
        )
        conn.execute(
            "INSERT INTO audit_log (seq, event_type, interaction_id, payload, prev_hash, hash, signature, created_at) "
            "VALUES (1, 'decision', ?, '{}', '0000000000000000000000000000000000000000000000000000000000000000', 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890', 'sig', ?)",
            (iid, now_str),
        )
        conn.execute(
            "INSERT INTO model_usage (id, interaction_id, stage, model, latency_ms, input_tokens, output_tokens, ok) "
            "VALUES ('mu_1', ?, 'sales_agent', 'Muse Spark', 45, 120, 40, 1)",
            (iid,),
        )

    return TestClient(app), iid


def test_get_receipt_png(client: tuple[TestClient, str]) -> None:
    c, iid = client
    r = c.get(f"/receipt/{iid}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    # Verify PNG magic bytes
    assert r.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(r.content) > 1000


def test_get_receipt_not_found(client: tuple[TestClient, str]) -> None:
    c, _ = client
    r = c.get("/receipt/nonexistent_id")
    assert r.status_code == 404


def test_get_dispute_report(client: tuple[TestClient, str]) -> None:
    c, iid = client
    r = c.get(f"/dispute/{iid}")
    assert r.status_code == 200
    data = r.json()
    assert data["interaction_id"] == iid
    assert "timeline" in data
    assert len(data["timeline"]) >= 3
    assert "cryptographic_proof" in data
    assert data["cryptographic_proof"]["audit_seq"] == 1


def test_get_models_usage_summary(client: tuple[TestClient, str]) -> None:
    c, _ = client
    r = c.get("/models/usage")
    assert r.status_code == 200
    data = r.json()
    assert "models" in data
    assert "by_stage" in data
    assert len(data["models"]) >= 1
    assert data["models"][0]["model"] == "Muse Spark"
    assert data["models"][0]["calls"] == 1
