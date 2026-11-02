"""Tests for Agentic Verification with Deterministic Decisions.

Tests:
1. Authorization Gateway on Action Tools (apply_discount, issue_refund, promise_delivery)
2. Policy Clause Store and get_policy_clauses retrieval
3. Verifier Agent Planning (plan_verification)
4. Evidence Bundle creation (build_evidence_bundle)
5. Verifier Agent Self-Check Pass (run_self_check_pass)
6. Policy-Version Tracking and auto-increment
7. Replayable Test Cases and deterministic policy drift detection
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.extract import Promise, run_self_check_pass
from app.gateway import GatewayDecision, authorize_action
from app.main import app
from app.replay import replay_interaction, replay_recent_interactions
from app.rules import BusinessRules, bump_version, load_rules, save_rules
from app.tools import default_adapter
from app.verify import Verdict, build_evidence_bundle, collect_facts, plan_verification, verify


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def base_rules() -> BusinessRules:
    return BusinessRules(
        policy_version="1.0",
        max_discount_percent=10.0,
        refund_window_days=14,
        standard_shipping_days=3,
        allow_unlimited_refund=False,
        require_evidence_for_damage_refund=True,
        min_confidence=0.6,
    )


# ── 1. Authorization Gateway Tests ───────────────────────────────────────────

def test_gateway_authorize_discount_allowed(base_rules: BusinessRules):
    decision = authorize_action(
        tool_name="apply_discount",
        args={"order_id": "O1001", "percent": 10.0},
        rules=base_rules,
    )
    assert decision.authorized is True
    assert decision.verdict == "allow"
    assert decision.rule_name == "max_discount_percent"
    assert decision.threshold == 10.0
    assert "permitted" in decision.reason.lower()
    assert decision.executed_result is not None


def test_gateway_authorize_discount_blocked(base_rules: BusinessRules):
    decision = authorize_action(
        tool_name="apply_discount",
        args={"order_id": "O1001", "percent": 25.0},
        rules=base_rules,
    )
    assert decision.authorized is False
    assert decision.verdict == "block"
    assert decision.rule_name == "max_discount_percent"
    assert "exceeds" in decision.reason.lower()
    assert decision.executed_result is None


def test_gateway_authorize_refund_allowed(base_rules: BusinessRules):
    # O1001 is within 14 days
    decision = authorize_action(
        tool_name="issue_refund",
        args={"order_id": "O1001", "amount": 2999.0},
        rules=base_rules,
    )
    assert decision.authorized is True
    assert decision.verdict == "allow"
    assert decision.executed_result["status"] == "refund_approved"


def test_gateway_authorize_refund_blocked_outside_window(base_rules: BusinessRules):
    # O1002 is 20 days old (outside 14-day window)
    decision = authorize_action(
        tool_name="issue_refund",
        args={"order_id": "O1002", "amount": 1999.0},
        rules=base_rules,
    )
    assert decision.authorized is False
    assert decision.verdict == "block"
    assert "exceeds" in decision.reason.lower() or "outside" in decision.reason.lower()


def test_gateway_authorize_refund_damage_without_evidence_review(base_rules: BusinessRules):
    decision = authorize_action(
        tool_name="issue_refund",
        args={"order_id": "O1001", "reason": "item damaged in transit", "damage_photo": False},
        rules=base_rules,
    )
    assert decision.authorized is False
    assert decision.verdict == "review"
    assert "evidence" in decision.reason.lower()


def test_gateway_authorize_delivery_allowed(base_rules: BusinessRules):
    # P1 requires 3 days shipping and has stock 40
    decision = authorize_action(
        tool_name="promise_delivery",
        args={"product_id": "P1", "days": 4},
        rules=base_rules,
    )
    assert decision.authorized is True
    assert decision.verdict == "allow"
    assert decision.executed_result["status"] == "delivery_scheduled"


def test_gateway_authorize_delivery_blocked_below_shipping_time(base_rules: BusinessRules):
    # P1 requires 3 days, asking for 1 day
    decision = authorize_action(
        tool_name="promise_delivery",
        args={"product_id": "P1", "days": 1},
        rules=base_rules,
    )
    assert decision.authorized is False
    assert decision.verdict == "block"
    assert "below minimum shipping" in decision.reason.lower()


# ── 2. Policy Clauses Store & Retrieval Tests ─────────────────────────────────

def test_policy_clauses_retrieval():
    clauses = default_adapter.get_policy_clauses(topic="discount")
    assert len(clauses) >= 1
    assert any("POL-DISC" in c.get("id", "") for c in clauses)

    refund_clauses = default_adapter.get_policy_clauses(topic="refund_window")
    assert len(refund_clauses) >= 1

    search_clauses = default_adapter.get_policy_clauses(keyword="warranty")
    assert len(search_clauses) >= 1
    assert "warranty" in search_clauses[0].get("title", "").lower()


# ── 3. Plan, Retrieval & Evidence Bundle Tests ─────────────────────────────────

def test_plan_verification():
    promises = [
        Promise(type="discount", value=10.0, unit="percent", quote="10% discount"),
        Promise(type="delivery", value=3.0, unit="days", quote="in 3 days"),
    ]
    plan = plan_verification(promises)
    assert len(plan) == 2
    assert plan[0]["policy_topic"] == "discount"
    assert plan[1]["policy_topic"] == "delivery"


def test_evidence_bundle_and_citations(base_rules: BusinessRules):
    promises = [
        Promise(type="discount", value=50.0, unit="percent", quote="50% off", confidence=0.95),
    ]
    facts = collect_facts(promises)
    res = verify(promises, base_rules, facts)
    assert res.message_verdict == Verdict.BLOCK
    v_p = res.promises[0]
    assert v_p.policy_clause is not None
    assert "POL-DISC" in v_p.policy_clause
    assert "50" in v_p.evidence
    assert res.evidence_bundle["policy_version"] == "1.0"
    assert "sources" in res.evidence_bundle


# ── 4. Self-Check Pass Tests ──────────────────────────────────────────────────

def test_self_check_pass_retains_valid_promises():
    draft = "Our mixer grinder comes with 10% discount and 3 days delivery."
    customer_msg = "What deals do you have?"
    initial = [
        Promise(type="discount", value=10.0, unit="percent", quote="10% discount"),
    ]
    result = run_self_check_pass(draft, customer_msg, initial)
    assert len(result) >= 1
    assert result[0].quote == "10% discount"


# ── 5. Policy Version Tracking Tests ──────────────────────────────────────────

def test_policy_version_bumping():
    assert bump_version("1.0") == "1.1"
    assert bump_version("1.9") == "1.10"
    assert bump_version("2.14") == "2.15"


# ── 6. Replayable Test Cases Tests ────────────────────────────────────────────

def test_replay_interaction_deterministic(client: TestClient, tmp_path: Path):
    from app.db import get_db

    int_id = "test_replay_disc_01"
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO interactions (id, session_id, agent_id, mode, customer_message, proposed_reply, final_reply, status, created_at, policy_version)
            VALUES (?, 'sess_rep', 'B', 'careful', 'Can I get 20% off?', 'I can offer a 20% discount today.', 'Our best authorized discount is 10%.', 'rewritten', '2026-10-27T00:00:00Z', '1.0')
            """,
            (int_id,),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO promises (id, interaction_id, attempt, type, value, unit, quote, confidence, verdict, reason, rule_name, threshold)
            VALUES ('prm_rep_1', ?, 0, 'discount', 20.0, 'percent', '20% discount', 0.95, 'block', 'Discount 20% is above the maximum of 10%.', 'max_discount_percent', 10.0)
            """,
            (int_id,),
        )

    # Replay against base rules (max discount 10.0% -> should still block)
    replay = replay_interaction(int_id)
    assert replay["interaction_id"] == int_id
    assert replay["replayed"]["verdict"] == "block"
    assert replay["verdict_changed"] is False
    assert "deterministic parity" in replay["diff_summary"].lower()

    # Replay with higher authorized discount (e.g. 25%)
    lenient_rules = BusinessRules(
        policy_version="2.0",
        max_discount_percent=25.0,
        refund_window_days=14,
        standard_shipping_days=3,
    )
    lenient_replay = replay_interaction(int_id, rules=lenient_rules)
    assert lenient_replay["replayed"]["policy_version"] == "2.0"
    assert lenient_replay["replayed"]["verdict"] == "allow"
    assert lenient_replay["verdict_changed"] is True
    assert "policy update" in lenient_replay["diff_summary"].lower()


# ── 7. Gateway & Policies API Endpoints Tests ──────────────────────────────────

def test_gateway_authorize_api(client: TestClient):
    r = client.post(
        "/gateway/authorize",
        json={
            "action_tool": "apply_discount",
            "args": {"order_id": "O1001", "percent": 5.0},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["authorized"] is True
    assert data["verdict"] == "allow"


def test_list_policies_api(client: TestClient):
    r = client.get("/policies?topic=discount")
    assert r.status_code == 200
    data = r.json()
    assert "policy_version" in data
    assert data["total_clauses"] >= 1
