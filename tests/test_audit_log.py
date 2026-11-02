"""Unit tests for Satyahd Phase 7: Cryptographic, Append-Only Audit Log.

Follows Section B8 testing requirements:
- Valid append & hash-chain generation
- Ed25519 signature verification
- Tamper detection:
  * Edited row payload
  * Deleted row (sequence gap)
  * Reordered rows
  * Bad / corrupted signature
  * Anchor mismatch
- Hard Rule 3: Write failure aborts delivery (sends nothing)
"""

import json
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.auditlog import (
    GENESIS_HASH,
    append_audit_entry,
    verify_chain,
)
from app.db import init_db, get_db
from app.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_satyahd.db"
    key_file = tmp_path / "test_ed25519.pem"
    anchor_dir = tmp_path / "anchors"
    anchor_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("SIGNING_KEY_PATH", str(key_file))
    monkeypatch.setenv("ANCHOR_DIR", str(anchor_dir))

    init_db(str(db_file))
    yield str(db_file), str(anchor_dir)


def test_audit_log_append_and_valid_chain():
    seq1 = append_audit_entry("decision", {"decision": "allow", "amount": 10}, "int_1")
    seq2 = append_audit_entry("decision", {"decision": "block", "amount": 50}, "int_2")
    seq3 = append_audit_entry("rules_change", {"old_max": 10, "new_max": 15}, "int_3")

    assert seq1 == 1
    assert seq2 == 2
    assert seq3 == 3

    # Check entries in DB
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY seq ASC").fetchall()
        assert len(rows) == 3
        assert rows[0]["prev_hash"] == GENESIS_HASH
        assert rows[1]["prev_hash"] == rows[0]["hash"]
        assert rows[2]["prev_hash"] == rows[1]["hash"]

    # Verify chain
    result = verify_chain()
    assert result["valid"] is True
    assert result["entries_checked"] == 3
    assert result["first_bad_seq"] is None


def test_detect_edited_row():
    append_audit_entry("decision", {"valid": True}, "int_1")
    append_audit_entry("decision", {"valid": True}, "int_2")

    # Bypass triggers temporarily to simulate attacker modifying the SQLite file directly
    with get_db() as conn:
        conn.execute("DROP TRIGGER abort_audit_log_update")
        conn.execute("UPDATE audit_log SET payload='{\"tampered\":true}' WHERE seq=1")

    # verify_chain must detect the tampered payload
    result = verify_chain()
    assert result["valid"] is False
    assert result["first_bad_seq"] == 1
    assert "recomputed hash does not match" in result["reason"]


def test_detect_deleted_row():
    append_audit_entry("decision", {"entry": 1}, "int_1")
    append_audit_entry("decision", {"entry": 2}, "int_2")
    append_audit_entry("decision", {"entry": 3}, "int_3")

    # Simulate attacker deleting seq=2
    with get_db() as conn:
        conn.execute("DROP TRIGGER abort_audit_log_delete")
        conn.execute("DELETE FROM audit_log WHERE seq=2")

    result = verify_chain()
    assert result["valid"] is False
    assert result["first_bad_seq"] == 3
    assert "Sequence gap or mismatch" in result["reason"]


def test_detect_corrupt_signature():
    append_audit_entry("decision", {"status": "ok"}, "int_1")

    # Corrupt the Ed25519 signature
    with get_db() as conn:
        conn.execute("DROP TRIGGER abort_audit_log_update")
        conn.execute("UPDATE audit_log SET signature='deadbeef' * 16 WHERE seq=1")

    result = verify_chain()
    assert result["valid"] is False
    assert result["first_bad_seq"] == 1
    assert "Invalid Ed25519 digital signature" in result["reason"]


def test_detect_anchor_mismatch(tmp_path):
    seq1 = append_audit_entry("decision", {"amount": 10}, "int_1")
    seq2 = append_audit_entry("decision", {"amount": 20}, "int_2")

    # Create an anchor for seq=2
    with get_db() as conn:
        last = conn.execute("SELECT seq, hash FROM audit_log WHERE seq=2").fetchone()

    anchor_file = tmp_path / "anchor_test.txt"
    anchor_file.write_text(
        json.dumps({"seq": 2, "hash": "tampered_hash_value"}),
        encoding="utf-8",
    )

    result = verify_chain(anchor_file_path=anchor_file)
    assert result["valid"] is False
    assert result["first_bad_seq"] == 2
    assert "does not reach anchor" in result["reason"]


def test_get_audit_verify_api_endpoint():
    client = TestClient(app)
    append_audit_entry("decision", {"test": True}, "int_api")

    resp = client.get("/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert data["entries_checked"] >= 1


def test_hard_rule_3_audit_failure_aborts_chat(monkeypatch):
    from app import main

    # Force append_audit_entry to raise an exception
    def failing_audit_write(*args, **kwargs):
        raise IOError("Simulated disk full or audit database locked error")

    monkeypatch.setattr(main, "append_audit_entry", failing_audit_write)

    client = TestClient(app)
    payload = {
        "session_id": "test_audit_fail",
        "agent_id": "A",
        "mode": "careful",
        "message": "Hello sales agent",
    }
    resp = client.post("/chat", data=payload)
    # Must fail closed: HTTP 500 returned, nothing sent to customer
    assert resp.status_code == 500
    assert "Audit write failed" in resp.json()["detail"]
