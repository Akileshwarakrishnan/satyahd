"""Rule Engine and Verification module for Satyahd.

Follows Section 3.7:
- Pure Python function: verify(promises, rules, facts) -> VerificationResult
- Deterministic decision table (discount, refund_window, delivery, stock, other)
- Confidence checks: confidence < min_confidence forces review
- Plain-English reasons with exact numbers
- Message verdict aggregation: any block -> block, else any review -> review, else allow
- Fact collector to populate the facts dictionary before calling verify()
- Completely pure: no clocks, network, or random numbers inside verify()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.extract import Promise, PromiseType
from app.rules import BusinessRules
from app.tools import StoreAdapter, default_adapter

logger = logging.getLogger("satyahd.verify")


class Verdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REVIEW = "review"


@dataclass
class VerificationResult:
    message_verdict: Verdict
    promises: list[Promise]
    reasons: list[str] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)
    evidence_bundle: dict[str, Any] = field(default_factory=dict)
    policy_version: str = "1.0"

    @property
    def is_allowed(self) -> bool:
        return self.message_verdict == Verdict.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.message_verdict == Verdict.BLOCK

    @property
    def is_review(self) -> bool:
        return self.message_verdict == Verdict.REVIEW


def plan_verification(
    promises: list[Promise],
    action_tools: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Step 2.2: Generates a deterministic verification plan deciding required facts and policy lookups."""
    plan: list[dict[str, Any]] = []
    for p in promises:
        step: dict[str, Any] = {
            "step": f"Inspect {p.type} commitment",
            "quote": p.quote,
            "required_facts": [],
            "policy_topic": None,
        }
        if p.type == PromiseType.DISCOUNT.value:
            step["required_facts"] = ["rules.max_discount_percent"]
            step["policy_topic"] = "discount"
        elif p.type == PromiseType.REFUND_WINDOW.value:
            step["required_facts"] = ["rules.refund_window_days", "orders.order_date"]
            if p.damage_basis:
                step["required_facts"].append("images.damage_visible")
            step["policy_topic"] = "refund_window"
        elif p.type == PromiseType.DELIVERY.value:
            step["required_facts"] = ["products.shipping_days", "products.stock"]
            step["policy_topic"] = "delivery"
        elif p.type == PromiseType.STOCK.value:
            step["required_facts"] = ["products.stock"]
            step["policy_topic"] = "stock"
        else:
            step["required_facts"] = ["human_review"]
            step["policy_topic"] = "general"
        plan.append(step)

    if action_tools:
        for at in action_tools:
            name = at.get("name", "")
            plan.append({
                "step": f"Authorize action-tool: {name}",
                "args": at.get("args", {}),
                "required_facts": ["gateway_authorization", "rules_compliance"],
                "policy_topic": name.replace("apply_", "").replace("issue_", "").replace("promise_", ""),
            })

    return plan


def build_evidence_bundle(
    promises: list[Promise],
    facts: dict[str, Any],
    rules: BusinessRules,
    action_tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Step 3: Creates an evidence bundle containing promises, retrieved facts and policy clauses."""
    return {
        "policy_version": getattr(rules, "policy_version", "1.0"),
        "rules_snapshot": rules.model_dump(),
        "promises_count": len(promises),
        "facts_retrieved": {
            "products": list(facts.get("products", {}).keys()),
            "orders": list(facts.get("orders", {}).keys()),
            "has_image_evidence": bool(facts.get("image_evidence")),
        },
        "policy_clauses": [
            {"id": c.get("id"), "topic": c.get("topic"), "title": c.get("title"), "clause": c.get("clause")}
            for c in facts.get("policy_clauses", [])
        ],
        "action_tools_intercepted": action_tools or [],
        "sources": {
            "products": "data/products.json",
            "orders": "data/orders.json",
            "policies": "data/policy_clauses.json",
            "rules": "data/rules.json",
        },
    }


def collect_facts(
    promises: list[Promise],
    adapter: StoreAdapter | None = None,
    image_evidence: dict[str, Any] | None = None,
    order_ref_override: str | None = None,
    interaction_id: str | None = None,
) -> dict[str, Any]:
    """Pre-fetches all facts required by the extracted promises.
    
    The rule engine never calls tools itself (Section 3.5 & 3.7).
    """
    store = adapter or default_adapter
    facts: dict[str, Any] = {
        "products": {},
        "orders": {},
        "policy": store.get_policy(),
        "image_evidence": image_evidence or {},
    }

    # Fetch referenced orders
    referenced_order_ids: set[str] = set()
    if order_ref_override:
        referenced_order_ids.add(order_ref_override)
    for p in promises:
        if p.order_ref:
            referenced_order_ids.add(p.order_ref)

    for oid in referenced_order_ids:
        order_info = store.get_order(oid)
        if order_info:
            facts["orders"][oid] = order_info
            if order_info.get("product_id"):
                p_info = store.get_product(order_info["product_id"])
                if p_info:
                    facts["products"][p_info["id"]] = p_info

    # Fetch referenced products
    for p in promises:
        pref = p.product_ref
        if pref and pref not in facts["products"]:
            p_info = store.get_product(pref)
            if p_info:
                facts["products"][pref] = p_info
                facts["products"][p_info["id"]] = p_info

    # If no specific product is referenced, populate standard products for fallback lookups
    if not facts["products"]:
        for pid in ("P1", "P2", "P3", "P4", "P5"):
            prod = store.get_product(pid)
            if prod:
                facts["products"][pid] = prod

    # Retrieve relevant policy clauses (Step 2.3)
    policy_clauses: list[dict[str, Any]] = []
    if hasattr(store, "get_policy_clauses"):
        topics = {p.type for p in promises}
        if any(p.damage_basis for p in promises):
            topics.add("damage")
        for t in topics:
            matched = store.get_policy_clauses(topic=t)
            policy_clauses.extend(matched)
        if not policy_clauses:
            policy_clauses = store.get_policy_clauses()
    facts["policy_clauses"] = policy_clauses

    return facts


def verify_discount_promise(promise: Promise, rules: BusinessRules) -> tuple[Verdict, str]:
    """Evaluates discount promise against rules.max_discount_percent."""
    if promise.vague or promise.value is None:
        return (
            Verdict.REVIEW,
            f"Discount promise '{promise.quote}' is vague or missing a specific percentage.",
        )

    val = float(promise.value)
    if val <= rules.max_discount_percent:
        return (
            Verdict.ALLOW,
            f"Discount {val:g}% is within the authorized maximum of {rules.max_discount_percent:g}%.",
        )
    else:
        return (
            Verdict.BLOCK,
            f"Discount {val:g}% is above the maximum of {rules.max_discount_percent:g}%.",
        )


def verify_refund_window_promise(
    promise: Promise,
    rules: BusinessRules,
    facts: dict[str, Any],
) -> tuple[Verdict, str]:
    """Evaluates refund promise against refund_window_days and order age."""
    # Unlimited refunds ('any time', 'whenever', 'no questions asked')
    if promise.unlimited:
        if rules.allow_unlimited_refund:
            return (
                Verdict.ALLOW,
                "Unlimited refund claim allowed per store exception policy.",
            )
        return (
            Verdict.BLOCK,
            "Unlimited refunds ('any time', 'no questions asked') are not authorized.",
        )

    # Damage basis check (Section 3.10)
    if promise.damage_basis:
        if rules.require_evidence_for_damage_refund:
            img_evidence = facts.get("image_evidence", {})
            damage_visible = img_evidence.get("damage_visible", False)
            img_conf = float(img_evidence.get("confidence", 0.0))

            if not damage_visible or img_conf < rules.min_confidence:
                return (
                    Verdict.REVIEW,
                    "Damage-based refund claimed but requires verified damage image evidence.",
                )

    # Vague wording without numbers
    if promise.vague or promise.value is None:
        return (
            Verdict.REVIEW,
            f"Refund window claim '{promise.quote}' is vague.",
        )

    val = int(promise.value)
    # Check promised days against maximum refund window
    if val > rules.refund_window_days:
        return (
            Verdict.BLOCK,
            f"Refund window of {val} days exceeds the authorized maximum of {rules.refund_window_days} days.",
        )

    # If an order is referenced in facts, verify actual order age
    order_id = promise.order_ref
    order_facts = None
    if order_id and order_id in facts.get("orders", {}):
        order_facts = facts["orders"][order_id]
    elif facts.get("orders"):
        # Use first known order if only one present
        order_facts = next(iter(facts["orders"].values()))

    if order_facts:
        days_old = order_facts.get("days_since_order")
        if days_old is not None and days_old > rules.refund_window_days:
            return (
                Verdict.BLOCK,
                f"Order {order_facts.get('id', '')} was placed {days_old} days ago, which is outside the {rules.refund_window_days}-day refund window.",
            )

    return (
        Verdict.ALLOW,
        f"Refund window of {val} days is within the authorized {rules.refund_window_days} days.",
    )


def verify_delivery_promise(
    promise: Promise,
    rules: BusinessRules,
    facts: dict[str, Any],
) -> tuple[Verdict, str]:
    """Evaluates delivery timeline against product shipping days and inventory."""
    if promise.vague or promise.value is None:
        return (
            Verdict.REVIEW,
            f"Delivery promise '{promise.quote}' uses vague wording ('soon' or imprecise timeline).",
        )

    promised_days = int(promise.value)

    # Check referenced product
    p_info = None
    if promise.product_ref and promise.product_ref in facts.get("products", {}):
        p_info = facts["products"][promise.product_ref]
    elif facts.get("products"):
        # Default to first known product
        p_info = next(iter(facts["products"].values()))

    required_shipping_days = (
        max(int(rules.standard_shipping_days), int(p_info.get("shipping_days", 0)))
        if p_info
        else int(rules.standard_shipping_days)
    )

    # Check if item is out of stock
    if p_info and int(p_info.get("stock", 0)) <= 0:
        return (
            Verdict.BLOCK,
            f"Delivery cannot be promised for '{p_info.get('name', 'Product')}' because it is currently out of stock.",
        )

    if promised_days < required_shipping_days:
        return (
            Verdict.BLOCK,
            f"Delivery in {promised_days} day(s) is below the minimum required shipping time of {required_shipping_days} days.",
        )

    return (
        Verdict.ALLOW,
        f"Delivery timeline of {promised_days} day(s) satisfies the required {required_shipping_days} day(s).",
    )


def verify_stock_promise(
    promise: Promise,
    facts: dict[str, Any],
) -> tuple[Verdict, str]:
    """Evaluates claimed stock against real inventory units in facts."""
    p_info = None
    if promise.product_ref and promise.product_ref in facts.get("products", {}):
        p_info = facts["products"][promise.product_ref]
    elif facts.get("products"):
        p_info = next(iter(facts["products"].values()))

    if not p_info:
        return (
            Verdict.REVIEW,
            f"Product referenced in stock claim '{promise.quote}' is unknown.",
        )

    real_stock = int(p_info.get("stock", 0))
    p_name = p_info.get("name", "Product")

    if real_stock <= 0:
        return (
            Verdict.BLOCK,
            f"Stock claim for '{p_name}' blocked: item is out of stock (0 units available).",
        )

    # Plain 'in stock' claim (no specific units claimed)
    if promise.value is None:
        return (
            Verdict.ALLOW,
            f"Stock claim for '{p_name}' verified: {real_stock} units currently available.",
        )

    claimed_units = int(promise.value)
    if claimed_units > real_stock:
        return (
            Verdict.BLOCK,
            f"Claimed {claimed_units} units of '{p_name}' exceeds real inventory of {real_stock} units.",
        )

    return (
        Verdict.ALLOW,
        f"Stock claim of {claimed_units} units for '{p_name}' is within real inventory of {real_stock} units.",
    )


def find_relevant_clause(
    promise_type: str,
    facts: dict[str, Any],
    damage_basis: bool = False,
) -> str:
    """Finds matching policy clause text from evidence facts."""
    clauses = facts.get("policy_clauses", [])
    target_topic = "damage" if damage_basis else promise_type
    for c in clauses:
        if str(c.get("topic", "")).lower() == target_topic.lower():
            return f"[{c.get('id', 'POL')} - {c.get('title', 'Policy')}]: \"{c.get('clause', '')}\""
    if clauses:
        c0 = clauses[0]
        return f"[{c0.get('id', 'POL')} - {c0.get('title', 'Policy')}]: \"{c0.get('clause', '')}\""
    return "Standard Kaveri store operating terms."


def verify(
    promises: list[Promise],
    rules: BusinessRules,
    facts: dict[str, Any],
) -> VerificationResult:
    """Pure, deterministic verification engine (Section 3.7 & Step 4).
    
    No clocks, no random values, no external network calls inside.
    """
    plan = plan_verification(promises)
    evidence_bundle = build_evidence_bundle(promises, facts, rules)
    policy_ver = getattr(rules, "policy_version", "1.0")

    if not promises:
        return VerificationResult(
            message_verdict=Verdict.ALLOW,
            promises=[],
            reasons=["No promises detected in draft reply."],
            plan=plan,
            evidence_bundle=evidence_bundle,
            policy_version=policy_ver,
        )

    verified_promises: list[Promise] = []
    overall_reasons: list[str] = []
    violations: list[dict[str, Any]] = []

    has_block = False
    has_review = False

    for orig_p in promises:
        p = orig_p.model_copy()

        # Step 1: Minimum confidence threshold check
        if p.confidence < rules.min_confidence:
            v = Verdict.REVIEW
            r = f"Extraction confidence {p.confidence:.2f} is below minimum required {rules.min_confidence:.2f}."
            p.rule_name = "min_confidence"
            p.threshold = float(rules.min_confidence)
        # Step 2: Evaluate promise type
        elif p.type == PromiseType.DISCOUNT.value:
            v, r = verify_discount_promise(p, rules)
            p.rule_name = "max_discount_percent"
            p.threshold = float(rules.max_discount_percent)
        elif p.type == PromiseType.REFUND_WINDOW.value:
            v, r = verify_refund_window_promise(p, rules, facts)
            p.rule_name = "refund_window_days"
            p.threshold = float(rules.refund_window_days)
        elif p.type == PromiseType.DELIVERY.value:
            v, r = verify_delivery_promise(p, rules, facts)
            p.rule_name = "standard_shipping_days"
            p.threshold = float(rules.standard_shipping_days)
        elif p.type == PromiseType.STOCK.value:
            v, r = verify_stock_promise(p, facts)
            p.rule_name = "inventory_stock"
            p_ref = p.product_ref or "P1"
            p_stock = facts.get("products", {}).get(p_ref, {}).get("stock", 0)
            p.threshold = float(p_stock)
        else:
            # Type 'other' always goes to review
            v = Verdict.REVIEW
            r = p.reason or f"Promise category '{p.type}' requires human review."
            p.rule_name = "unclassified_claim"
            p.threshold = None

        # Citing Policy Clause & Factual Evidence (Section 1.1 & Phase 11.1)
        clause_citation = find_relevant_clause(p.type, facts, p.damage_basis)
        p.policy_clause = clause_citation
        p.evidence = f"Draft quote: '{p.quote}' | Value: {p.value} {p.unit or ''}".strip()
        p.verdict = v.value
        p.reason = r
        verified_promises.append(p)
        overall_reasons.append(r)

        if v == Verdict.BLOCK:
            has_block = True
            violations.append({
                "type": p.type,
                "quote": p.quote,
                "value": p.value,
                "reason": r,
                "policy_clause": clause_citation,
            })
        elif v == Verdict.REVIEW:
            has_review = True

    # Section 3.7: Aggregation logic: any block -> block; else any review -> review; else allow
    if has_block:
        final_verdict = Verdict.BLOCK
    elif has_review:
        final_verdict = Verdict.REVIEW
    else:
        final_verdict = Verdict.ALLOW

    return VerificationResult(
        message_verdict=final_verdict,
        promises=verified_promises,
        reasons=overall_reasons,
        violations=violations,
        plan=plan,
        evidence_bundle=evidence_bundle,
        policy_version=policy_ver,
    )
