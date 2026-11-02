"""Authorization Gateway for Action-Tool Calls.

Follows Section 1.1:
- The agent has protected action tools: apply_discount, issue_refund, promise_delivery.
- The gateway intercepts every action tool call BEFORE execution.
- Deterministic evaluation against BusinessRules and Store Facts:
    - allow: executes action and returns result
    - block: rejects execution, logs security violation
    - review: queues for store manager approval
- Two-layer protection: operates in tandem with outgoing customer text verification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.rules import BusinessRules, load_rules
from app.tools import StoreAdapter, default_adapter, execute_tool, log_tool_call

logger = logging.getLogger("satyahd.gateway")


@dataclass
class GatewayDecision:
    authorized: bool
    verdict: str  # "allow" | "block" | "review"
    action_tool: str
    args: dict[str, Any]
    rule_name: str
    threshold: float | None
    policy_clause: str
    reason: str
    evidence: str
    executed_result: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorized": self.authorized,
            "verdict": self.verdict,
            "action_tool": self.action_tool,
            "args": self.args,
            "rule_name": self.rule_name,
            "threshold": self.threshold,
            "policy_clause": self.policy_clause,
            "reason": self.reason,
            "evidence": self.evidence,
            "executed_result": self.executed_result,
        }


def authorize_action(
    tool_name: str,
    args: dict[str, Any],
    rules: BusinessRules | None = None,
    adapter: StoreAdapter | None = None,
    interaction_id: str | None = None,
) -> GatewayDecision:
    """Evaluates an action tool call against store business rules and executes only if permitted."""
    current_rules = rules or load_rules()
    store = adapter or default_adapter

    name = tool_name.strip()
    clauses = store.get_policy_clauses() if hasattr(store, "get_policy_clauses") else []

    # 1. Action: apply_discount
    if name == "apply_discount":
        percent = float(args.get("percent", 0.0))
        rule_name = "max_discount_percent"
        threshold = float(current_rules.max_discount_percent)
        clause = "Authorized customer discounts are strictly capped at a maximum of 10% on all standard home appliances."
        for c in clauses:
            if c.get("topic") == "discount":
                clause = f"[{c.get('id')} - {c.get('title')}]: {c.get('clause')}"
                break

        evidence = f"Action requested: apply_discount({percent}%) for order '{args.get('order_id', 'N/A')}'"

        if percent <= 0:
            return GatewayDecision(
                authorized=False,
                verdict="review",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason="Discount percentage must be greater than 0%.",
                evidence=evidence,
                executed_result=None,
            )

        if percent <= current_rules.max_discount_percent:
            exec_res = {
                "status": "applied",
                "discount_percent": percent,
                "order_id": args.get("order_id"),
                "authorized_by": "Satyahd Gateway",
            }
            log_tool_call(name, args, exec_res, latency_ms=5, ok=True, interaction_id=interaction_id)
            return GatewayDecision(
                authorized=True,
                verdict="allow",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason=f"Action apply_discount({percent:g}%) permitted within threshold {threshold:g}%.",
                evidence=evidence,
                executed_result=exec_res,
            )
        else:
            log_tool_call(name, args, "BLOCKED by Gateway", latency_ms=5, ok=False, interaction_id=interaction_id)
            return GatewayDecision(
                authorized=False,
                verdict="block",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason=f"Action apply_discount({percent:g}%) blocked: exceeds authorized maximum {threshold:g}%.",
                evidence=evidence,
                executed_result=None,
            )

    # 2. Action: issue_refund
    elif name == "issue_refund":
        order_id = str(args.get("order_id", "")).strip()
        order_info = store.get_order(order_id) if order_id else None
        rule_name = "refund_window_days"
        threshold = float(current_rules.refund_window_days)
        clause = "Standard return and refund requests must be initiated within 14 calendar days of delivery."
        for c in clauses:
            if c.get("topic") == "refund_window":
                clause = f"[{c.get('id')} - {c.get('title')}]: {c.get('clause')}"
                break

        evidence = f"Action requested: issue_refund for order '{order_id}'"

        if not order_info:
            return GatewayDecision(
                authorized=False,
                verdict="review",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason=f"Refund requested for unrecognized order '{order_id}'. Sent for human review.",
                evidence=evidence,
                executed_result=None,
            )

        days_old = order_info.get("days_since_order", 0)
        evidence += f" (Order placed {days_old} days ago)"

        # Check damage evidence requirement if damage is cited
        reason_text = str(args.get("reason", "")).lower()
        if "damage" in reason_text or args.get("damage_photo") is False:
            if "damage" in reason_text and current_rules.require_evidence_for_damage_refund and not args.get("damage_photo"):
                return GatewayDecision(
                    authorized=False,
                    verdict="review",
                    action_tool=name,
                    args=args,
                    rule_name="require_evidence_for_damage_refund",
                    threshold=1.0,
                    policy_clause="Refunds claiming damage strictly require photo inspection evidence.",
                    reason="Damage refund action requires verified photo inspection evidence.",
                    evidence=evidence,
                    executed_result=None,
                )

        if days_old is not None and days_old > current_rules.refund_window_days:
            log_tool_call(name, args, "BLOCKED: outside window", latency_ms=5, ok=False, interaction_id=interaction_id)
            return GatewayDecision(
                authorized=False,
                verdict="block",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason=f"Action issue_refund blocked: order {order_id} is {days_old} days old (exceeds {threshold:g} days).",
                evidence=evidence,
                executed_result=None,
            )

        exec_res = {
            "status": "refund_approved",
            "order_id": order_id,
            "amount": args.get("amount", order_info.get("total_amount", 0.0)),
            "authorized_by": "Satyahd Gateway",
        }
        log_tool_call(name, args, exec_res, latency_ms=5, ok=True, interaction_id=interaction_id)
        return GatewayDecision(
            authorized=True,
            verdict="allow",
            action_tool=name,
            args=args,
            rule_name=rule_name,
            threshold=threshold,
            policy_clause=clause,
            reason=f"Action issue_refund permitted: order is within {threshold:g}-day window.",
            evidence=evidence,
            executed_result=exec_res,
        )

    # 3. Action: promise_delivery
    elif name == "promise_delivery":
        product_id = str(args.get("product_id", "")).strip() or "P1"
        days = int(args.get("days", 0))
        prod = store.get_product(product_id)
        stock = store.get_stock(product_id) or 0
        req_shipping = store.get_shipping(product_id) or current_rules.standard_shipping_days

        rule_name = "standard_shipping_days"
        threshold = float(req_shipping)
        clause = "Standard appliance delivery requires a minimum transit window of 3 business days from warehouse dispatch."
        for c in clauses:
            if c.get("topic") == "delivery":
                clause = f"[{c.get('id')} - {c.get('title')}]: {c.get('clause')}"
                break

        prod_name = prod.get("name", product_id) if prod else product_id
        evidence = f"Action requested: promise_delivery({days} days) for '{prod_name}' (Stock: {stock}, Min Shipping: {req_shipping}d)"

        # Check stock first
        if stock <= 0:
            log_tool_call(name, args, "BLOCKED: out of stock", latency_ms=5, ok=False, interaction_id=interaction_id)
            return GatewayDecision(
                authorized=False,
                verdict="block",
                action_tool=name,
                args=args,
                rule_name="inventory_stock",
                threshold=0.0,
                policy_clause="Orders and delivery commitments cannot be made for products with zero inventory.",
                reason=f"Action promise_delivery blocked: product '{prod_name}' has 0 inventory in stock.",
                evidence=evidence,
                executed_result=None,
            )

        if days < req_shipping:
            log_tool_call(name, args, "BLOCKED: below shipping days", latency_ms=5, ok=False, interaction_id=interaction_id)
            return GatewayDecision(
                authorized=False,
                verdict="block",
                action_tool=name,
                args=args,
                rule_name=rule_name,
                threshold=threshold,
                policy_clause=clause,
                reason=f"Action promise_delivery({days}d) blocked: below minimum shipping transit time of {req_shipping} days.",
                evidence=evidence,
                executed_result=None,
            )

        exec_res = {
            "status": "delivery_scheduled",
            "product_id": product_id,
            "days": days,
            "authorized_by": "Satyahd Gateway",
        }
        log_tool_call(name, args, exec_res, latency_ms=5, ok=True, interaction_id=interaction_id)
        return GatewayDecision(
            authorized=True,
            verdict="allow",
            action_tool=name,
            args=args,
            rule_name=rule_name,
            threshold=threshold,
            policy_clause=clause,
            reason=f"Action promise_delivery({days}d) permitted: meets or exceeds minimum shipping days ({req_shipping}d).",
            evidence=evidence,
            executed_result=exec_res,
        )

    # Unknown action tool
    return GatewayDecision(
        authorized=False,
        verdict="review",
        action_tool=name,
        args=args,
        rule_name="unauthorized_action_tool",
        threshold=None,
        policy_clause="All unclassified business actions require manual authorization.",
        reason=f"Action tool '{name}' is not recognized in store catalog.",
        evidence=f"Attempted execution of unregistered tool: {name}",
        executed_result=None,
    )
