"""Unit tests for Satyahd Phase 5: Deterministic Rule Engine.

Follows Section B8 testing requirements:
At least 25 unit tests covering every row of the decision table,
every boundary condition, message verdict aggregation, and determinism.
"""

import pytest

from app.extract import Promise, PromiseType
from app.rules import BusinessRules
from app.verify import Verdict, verify


@pytest.fixture
def default_rules() -> BusinessRules:
    return BusinessRules(
        max_discount_percent=10.0,
        refund_window_days=14,
        standard_shipping_days=3,
        allow_unlimited_refund=False,
        require_evidence_for_damage_refund=True,
        min_confidence=0.6,
    )


@pytest.fixture
def default_facts() -> dict:
    return {
        "products": {
            "P1": {"id": "P1", "name": "Kaveri Mixer Grinder", "stock": 40, "shipping_days": 3},
            "P2": {"id": "P2", "name": "Induction Cooktop", "stock": 12, "shipping_days": 3},
            "P3": {"id": "P3", "name": "Water Purifier", "stock": 0, "shipping_days": 3},
        },
        "orders": {
            "O1001": {"id": "O1001", "product_id": "P1", "order_date": "2026-10-27", "days_since_order": 5},
            "O1002": {"id": "O1002", "product_id": "P2", "order_date": "2026-10-12", "days_since_order": 20},
        },
        "policy": {
            "max_discount_percent": 10.0,
            "refund_window_days": 14,
            "standard_shipping_days": 3,
        },
        "image_evidence": {},
    }


# ---------------------------------------------------------------------------
# 1. Discount Tests & Boundaries
# ---------------------------------------------------------------------------

def test_discount_boundary_exact_passes(default_rules, default_facts):
    p = Promise(type="discount", value=10.0, unit="percent", quote="10% discount", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW
    assert res.promises[0].verdict == "allow"
    assert "within the authorized maximum" in res.promises[0].reason


def test_discount_boundary_over_blocks(default_rules, default_facts):
    p = Promise(type="discount", value=10.01, unit="percent", quote="10.01% off", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert res.promises[0].verdict == "block"
    assert "above the maximum" in res.promises[0].reason


def test_discount_below_passes(default_rules, default_facts):
    p = Promise(type="discount", value=5.0, unit="percent", quote="5% discount", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_discount_zero_passes(default_rules, default_facts):
    p = Promise(type="discount", value=0.0, unit="percent", quote="0% discount", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_discount_vague_review(default_rules, default_facts):
    p = Promise(type="discount", value=None, unit="percent", quote="some discount", vague=True, confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW
    assert "vague or missing" in res.promises[0].reason


def test_discount_missing_value_review(default_rules, default_facts):
    p = Promise(type="discount", value=None, unit="percent", quote="a discount", vague=False, confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW


# ---------------------------------------------------------------------------
# 2. Refund Window Tests & Boundaries
# ---------------------------------------------------------------------------

def test_refund_boundary_exact_passes(default_rules, default_facts):
    p = Promise(type="refund_window", value=14.0, unit="days", quote="14 days refund", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW
    assert res.promises[0].verdict == "allow"


def test_refund_boundary_over_blocks(default_rules, default_facts):
    p = Promise(type="refund_window", value=15.0, unit="days", quote="15 days refund", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "exceeds the authorized maximum" in res.promises[0].reason


def test_refund_within_window_passes(default_rules, default_facts):
    p = Promise(type="refund_window", value=7.0, unit="days", quote="7 days refund", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_refund_order_inside_window_passes(default_rules, default_facts):
    p = Promise(type="refund_window", value=14.0, unit="days", order_ref="O1001", quote="refund", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_refund_order_outside_window_blocks(default_rules, default_facts):
    # O1002 is 20 days old -> outside 14 days
    p = Promise(type="refund_window", value=14.0, unit="days", order_ref="O1002", quote="refund", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "outside the 14-day refund window" in res.promises[0].reason


def test_refund_unlimited_blocks_by_default(default_rules, default_facts):
    p = Promise(type="refund_window", value=None, unit="days", unlimited=True, quote="refund any time", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "Unlimited refunds" in res.promises[0].reason


def test_refund_unlimited_allows_when_enabled(default_rules, default_facts):
    rules = default_rules.model_copy(update={"allow_unlimited_refund": True})
    p = Promise(type="refund_window", value=None, unit="days", unlimited=True, quote="refund whenever", confidence=0.9)
    res = verify([p], rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_refund_damage_basis_without_evidence_review(default_rules, default_facts):
    p = Promise(type="refund_window", value=14.0, unit="days", damage_basis=True, quote="broken return", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW
    assert "requires verified damage image evidence" in res.promises[0].reason


def test_refund_damage_basis_with_valid_evidence_allows(default_rules, default_facts):
    facts = dict(default_facts)
    facts["image_evidence"] = {"damage_visible": True, "confidence": 0.95}
    p = Promise(type="refund_window", value=14.0, unit="days", damage_basis=True, quote="broken return", confidence=0.9)
    res = verify([p], default_rules, facts)
    assert res.message_verdict == Verdict.ALLOW


def test_refund_damage_basis_with_low_confidence_evidence_review(default_rules, default_facts):
    facts = dict(default_facts)
    facts["image_evidence"] = {"damage_visible": True, "confidence": 0.4}  # below 0.6
    p = Promise(type="refund_window", value=14.0, unit="days", damage_basis=True, quote="broken return", confidence=0.9)
    res = verify([p], default_rules, facts)
    assert res.message_verdict == Verdict.REVIEW


# ---------------------------------------------------------------------------
# 3. Delivery Tests & Boundaries
# ---------------------------------------------------------------------------

def test_delivery_boundary_exact_passes(default_rules, default_facts):
    p = Promise(type="delivery", value=3.0, unit="days", product_ref="P1", quote="3 days delivery", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW
    assert res.promises[0].verdict == "allow"


def test_delivery_boundary_under_blocks(default_rules, default_facts):
    p = Promise(type="delivery", value=2.0, unit="days", product_ref="P1", quote="2 days delivery", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "below the minimum required shipping time" in res.promises[0].reason


def test_delivery_above_shipping_passes(default_rules, default_facts):
    p = Promise(type="delivery", value=5.0, unit="days", product_ref="P1", quote="5 days delivery", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_delivery_vague_review(default_rules, default_facts):
    p = Promise(type="delivery", value=None, unit="days", product_ref="P1", vague=True, quote="soon", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW
    assert "vague wording" in res.promises[0].reason


def test_delivery_out_of_stock_blocks(default_rules, default_facts):
    # P3 has stock 0
    p = Promise(type="delivery", value=3.0, unit="days", product_ref="P3", quote="3 days", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "currently out of stock" in res.promises[0].reason


# ---------------------------------------------------------------------------
# 4. Stock Tests & Boundaries
# ---------------------------------------------------------------------------

def test_stock_claim_equal_to_real_passes(default_rules, default_facts):
    # P1 real stock is 40
    p = Promise(type="stock", value=40.0, unit="units", product_ref="P1", quote="40 units in stock", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_stock_claim_one_above_blocks(default_rules, default_facts):
    # P1 real stock is 40, claimed 41
    p = Promise(type="stock", value=41.0, unit="units", product_ref="P1", quote="41 units in stock", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "exceeds real inventory of 40 units" in res.promises[0].reason


def test_stock_in_stock_positive_passes(default_rules, default_facts):
    p = Promise(type="stock", value=None, unit="units", product_ref="P1", quote="in stock", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_stock_out_of_stock_blocks(default_rules, default_facts):
    p = Promise(type="stock", value=None, unit="units", product_ref="P3", quote="in stock", confidence=0.9)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "out of stock (0 units available)" in res.promises[0].reason


def test_stock_unknown_product_review(default_rules):
    empty_facts = {"products": {}, "orders": {}}
    p = Promise(type="stock", value=10.0, unit="units", product_ref="UNKNOWN_ITEM", quote="10 units", confidence=0.9)
    res = verify([p], default_rules, empty_facts)
    assert res.message_verdict == Verdict.REVIEW
    assert "unknown" in res.promises[0].reason.lower()


# ---------------------------------------------------------------------------
# 5. Type 'Other' & Confidence Threshold Tests
# ---------------------------------------------------------------------------

def test_other_promise_type_always_review(default_rules, default_facts):
    p = Promise(type="other", value=None, quote="special warranty", confidence=0.95)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW


def test_low_confidence_forces_review(default_rules, default_facts):
    # Discount 5% is valid, but confidence 0.5 < 0.6
    p = Promise(type="discount", value=5.0, unit="percent", quote="5% discount", confidence=0.5)
    res = verify([p], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW
    assert "below minimum required" in res.promises[0].reason


# ---------------------------------------------------------------------------
# 6. Message Verdict Aggregation & Determinism Tests
# ---------------------------------------------------------------------------

def test_verdict_aggregation_block_trumps_all(default_rules, default_facts):
    p1 = Promise(type="discount", value=50.0, unit="percent", quote="50% off", confidence=0.9)  # BLOCK
    p2 = Promise(type="discount", value=5.0, unit="percent", quote="5% off", confidence=0.9)   # ALLOW
    p3 = Promise(type="other", quote="unclear", confidence=0.9)                               # REVIEW

    res = verify([p1, p2, p3], default_rules, default_facts)
    assert res.message_verdict == Verdict.BLOCK
    assert len(res.violations) == 1


def test_verdict_aggregation_review_over_allow(default_rules, default_facts):
    p1 = Promise(type="discount", value=5.0, unit="percent", quote="5% off", confidence=0.9)   # ALLOW
    p2 = Promise(type="other", quote="unclear", confidence=0.9)                               # REVIEW

    res = verify([p1, p2], default_rules, default_facts)
    assert res.message_verdict == Verdict.REVIEW


def test_verdict_aggregation_all_allow(default_rules, default_facts):
    p1 = Promise(type="discount", value=5.0, unit="percent", quote="5% off", confidence=0.9)
    p2 = Promise(type="delivery", value=3.0, unit="days", product_ref="P1", quote="3 days", confidence=0.9)

    res = verify([p1, p2], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_verdict_aggregation_empty_promises_allow(default_rules, default_facts):
    res = verify([], default_rules, default_facts)
    assert res.message_verdict == Verdict.ALLOW


def test_engine_determinism_repeated_calls(default_rules, default_facts):
    """Run exact verification multiple times to prove pure functional determinism."""
    p_block = Promise(type="discount", value=50.0, unit="percent", quote="50% off", confidence=0.95)
    p_allow = Promise(type="delivery", value=3.0, unit="days", product_ref="P1", quote="3 days", confidence=0.95)

    res1 = verify([p_block, p_allow], default_rules, default_facts)
    res2 = verify([p_block, p_allow], default_rules, default_facts)

    assert res1.message_verdict == res2.message_verdict
    assert len(res1.promises) == len(res2.promises)
    assert res1.promises[0].verdict == res2.promises[0].verdict
    assert res1.promises[0].reason == res2.promises[0].reason
    assert res1.promises[1].verdict == res2.promises[1].verdict
    assert res1.promises[1].reason == res2.promises[1].reason
