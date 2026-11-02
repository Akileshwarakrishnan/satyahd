"""Unit tests for Satyahd Phase 2: Rules Loader, Store Adapter & Tools."""

import json
import pytest
from pathlib import Path

from app.config import BASE_DIR, get_settings
from app.db import init_db, get_db
from app.rules import BusinessRules, load_rules, save_rules
from app.tools import JsonStoreAdapter, execute_tool


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Provide isolated SQLite database and JSON files."""
    db_file = tmp_path / "test_satyahd.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    yield


# ---------------------------------------------------------------------------
# Business Rules Tests
# ---------------------------------------------------------------------------

def test_load_valid_rules():
    rules = load_rules()
    assert rules.max_discount_percent == 10.0
    assert rules.refund_window_days == 14
    assert rules.standard_shipping_days == 3
    assert rules.allow_unlimited_refund is False
    assert rules.require_evidence_for_damage_refund is True
    assert rules.min_confidence == 0.6


def test_rules_out_of_range_rejections():
    # Discount > 100
    with pytest.raises(ValueError) as exc:
        BusinessRules(max_discount_percent=101)
    assert "max_discount_percent must be between 0 and 100" in str(exc.value)

    # Discount < 0
    with pytest.raises(ValueError) as exc:
        BusinessRules(max_discount_percent=-1)
    assert "max_discount_percent must be between 0 and 100" in str(exc.value)

    # Refund window > 365
    with pytest.raises(ValueError) as exc:
        BusinessRules(refund_window_days=400)
    assert "refund_window_days must be between 0 and 365" in str(exc.value)

    # Shipping days > 60
    with pytest.raises(ValueError) as exc:
        BusinessRules(standard_shipping_days=90)
    assert "standard_shipping_days must be between 0 and 60" in str(exc.value)

    # Min confidence > 1.0
    with pytest.raises(ValueError) as exc:
        BusinessRules(min_confidence=1.5)
    assert "min_confidence must be between 0.0 and 1.0" in str(exc.value)


def test_save_and_reload_rules(tmp_path):
    temp_rules_file = tmp_path / "rules.json"
    updated = {
        "max_discount_percent": 15,
        "refund_window_days": 30,
        "standard_shipping_days": 5,
        "allow_unlimited_refund": False,
        "require_evidence_for_damage_refund": True,
        "min_confidence": 0.7,
    }
    saved = save_rules(updated, file_path=temp_rules_file)
    assert saved.max_discount_percent == 15.0

    reloaded = load_rules(file_path=temp_rules_file)
    assert reloaded.max_discount_percent == 15.0
    assert reloaded.refund_window_days == 30


# ---------------------------------------------------------------------------
# Store Adapter & Tools Tests
# ---------------------------------------------------------------------------

def test_store_adapter_product_lookup():
    adapter = JsonStoreAdapter()

    # Exact ID match
    p1 = adapter.get_product("P1")
    assert p1 is not None
    assert p1["id"] == "P1"
    assert p1["name"] == "Kaveri Mixer Grinder"
    assert p1["stock"] == 40

    # Substring case-insensitive match
    cooktop = adapter.get_product("cooktop")
    assert cooktop is not None
    assert cooktop["id"] == "P2"

    # Out of stock product
    purifier = adapter.get_product("P3")
    assert purifier is not None
    assert purifier["stock"] == 0

    # Non-existent product
    assert adapter.get_product("non_existent_item") is None


def test_store_adapter_stock_lookup():
    adapter = JsonStoreAdapter()
    assert adapter.get_stock("P1") == 40
    assert adapter.get_stock("P3") == 0
    assert adapter.get_stock("P4") == 75
    assert adapter.get_stock("UNKNOWN") is None


def test_store_adapter_order_lookup_deterministic_age():
    adapter = JsonStoreAdapter()

    # O1001 ordered 2026-10-27, DEMO_TODAY is 2026-11-01 -> 5 days
    o1 = adapter.get_order("O1001")
    assert o1 is not None
    assert o1["product_id"] == "P1"
    assert o1["days_since_order"] == 5

    # O1002 ordered 2026-10-12, DEMO_TODAY is 2026-11-01 -> 20 days (outside 14-day window)
    o2 = adapter.get_order("O1002")
    assert o2 is not None
    assert o2["days_since_order"] == 20

    # O1003 ordered 2026-10-30 -> 2 days
    o3 = adapter.get_order("O1003")
    assert o3 is not None
    assert o3["days_since_order"] == 2

    # O1004 ordered 2026-10-22 -> 10 days
    o4 = adapter.get_order("O1004")
    assert o4 is not None
    assert o4["days_since_order"] == 10

    # Unknown order
    assert adapter.get_order("O9999") is None


def test_store_adapter_shipping_and_policy():
    adapter = JsonStoreAdapter()
    assert adapter.get_shipping("P1") == 3
    policy = adapter.get_policy()
    assert policy["max_discount_percent"] == 10.0
    assert policy["refund_window_days"] == 14


def test_execute_tool_and_logging():
    # Insert interaction record first to satisfy foreign key relationship
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO interactions (id, session_id, agent_id, mode, customer_message, status, created_at)
            VALUES ('tool_test_int_1', 'sess_1', 'A', 'careful', 'check stock', 'received', '2026-11-01T10:00:00Z')
            """
        )

    result = execute_tool(
        name="get_stock",
        args={"product_id": "P1"},
        interaction_id="tool_test_int_1",
    )
    assert result == 40

    # Verify tool call was recorded in database
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tool_calls WHERE interaction_id='tool_test_int_1'"
        ).fetchone()
        assert row is not None
        assert row["name"] == "get_stock"
        assert row["result"] == "40"
        assert row["ok"] == 1
