"""Tests for Requirement 11 — Explainable Verdicts.

Verifies that verdicts provide:
- Exact promise and quoted value
- Governing corporate business rule name
- Authorised threshold comparison
- Clear, plain-English calculation explanation
"""

from __future__ import annotations

from pathlib import Path
import pytest
from app.extract import Promise, extract_promises
from app.rules import BusinessRules
from app.verify import Verdict, collect_facts, verify


@pytest.fixture()
def rules() -> BusinessRules:
    return BusinessRules(
        max_discount_percent=10.0,
        refund_window_days=14,
        standard_shipping_days=3,
        allow_unlimited_refund=False,
        require_evidence_for_damage_refund=True,
        min_confidence=0.6,
    )


def test_explainable_discount_violation(rules: BusinessRules) -> None:
    p = Promise(
        type="discount",
        value=50.0,
        unit="percent",
        quote="50% discount",
        confidence=0.95,
    )
    res = verify([p], rules, facts={})
    assert res.message_verdict == Verdict.BLOCK
    v_p = res.promises[0]
    assert v_p.rule_name == "max_discount_percent"
    assert v_p.threshold == 10.0
    assert "above the maximum" in v_p.reason or "exceeds" in v_p.reason
    assert "50" in v_p.reason
    assert "10" in v_p.reason


def test_explainable_delivery_violation(rules: BusinessRules) -> None:
    p = Promise(
        type="delivery",
        value=1.0,
        unit="days",
        quote="tomorrow",
        confidence=0.95,
    )
    res = verify([p], rules, facts={})
    assert res.message_verdict == Verdict.BLOCK
    v_p = res.promises[0]
    assert v_p.rule_name == "standard_shipping_days"
    assert v_p.threshold == 3.0
    assert "1 day" in v_p.reason
    assert "3 days" in v_p.reason


def test_explainable_refund_window_violation(rules: BusinessRules) -> None:
    p = Promise(
        type="refund_window",
        value=30.0,
        unit="days",
        quote="30 days refund",
        confidence=0.95,
    )
    res = verify([p], rules, facts={})
    assert res.message_verdict == Verdict.BLOCK
    v_p = res.promises[0]
    assert v_p.rule_name == "refund_window_days"
    assert v_p.threshold == 14.0
    assert "30 days" in v_p.reason
    assert "14 days" in v_p.reason


def test_explainable_allowed_discount(rules: BusinessRules) -> None:
    p = Promise(
        type="discount",
        value=10.0,
        unit="percent",
        quote="10% discount",
        confidence=0.95,
    )
    res = verify([p], rules, facts={})
    assert res.message_verdict == Verdict.ALLOW
    v_p = res.promises[0]
    assert v_p.rule_name == "max_discount_percent"
    assert v_p.threshold == 10.0
    assert "within the authorized maximum" in v_p.reason
