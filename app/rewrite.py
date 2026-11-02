"""Rewrite and Re-verification Engine for Satyahd.

Follows Section 3.8:
- Inputs: original draft, violations (type, quote, reason), and allowed values
- LLM writes polite reply in at most 2 sentences using ONLY permitted values
- NEVER mentions internal rules, logs, or 'Satyahd', and adds NO new promises
- Re-extracted and re-verified through extraction + rule engine
- Up to 2 rewrite attempts
- Deterministic template fallback if LLM fails
- If rewrite fails to pass verification, returns standard holding reply:
  'Thanks for your message. A member of our team will confirm the details and get back to you shortly.'
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import get_settings
from app.extract import Promise, extract_promises
from app.models import call_model
from app.rules import BusinessRules
from app.verify import Verdict, verify

logger = logging.getLogger("satyahd.rewrite")

HOLDING_REPLY = "Thanks for your message. A member of our team will confirm the details and get back to you shortly."

REWRITE_SYSTEM_PROMPT = """You are a polite, helpful customer communication assistant for 'Kaveri Home Appliances'.
The previous draft reply violated store business guidelines. Your task is to rewrite the reply so that it complies with the permitted values.

STRICT INSTRUCTIONS:
1. Write a polite, natural reply of at most TWO to THREE sentences.
2. Address ALL questions asked by the customer in a single cohesive answer (e.g., if customer asked about both discount and shipping, answer both with authorized values).
3. Use ONLY the permitted values provided below.
4. NEVER mention internal rules, policies, guardrails, guidelines, the log, or the word 'Satyahd'.
5. Do NOT introduce any new promises, discounts, or terms not explicitly authorized.
6. Sound natural, friendly, and helpful to the customer.
"""


def generate_template_fallback(
    violations: list[dict[str, Any]],
    rules: BusinessRules,
    facts: dict[str, Any],
    customer_message: str = "",
) -> str:
    """Deterministic fallback templates per violation if model rewrite is unavailable."""
    if not violations:
        return f"Our standard store policies apply with {rules.refund_window_days} days return window."

    shipping_days = rules.standard_shipping_days
    if facts.get("products"):
        first_prod = next(iter(facts["products"].values()))
        prod_shipping = int(first_prod.get("shipping_days", 0))
        shipping_days = max(rules.standard_shipping_days, prod_shipping)

    v_types = {v.get("type") for v in violations if v.get("type")}
    cust_lower = customer_message.lower()

    # Detect all active customer intents for compound queries
    has_catalog_kw = any(kw in cust_lower for kw in ("has this product", "have this product", "this product", "this item", "sell this", "carry this", "do youre shop", "do your shop", "what products", "what do you sell", "in your shop", "in your store", "what appliances", "available in your shop", "is this available", "catalog"))
    has_discount_kw = any(kw in cust_lower for kw in ("discount", "off", "%", "deal", "deals", "price", "thallubadi", "half price", "offer"))
    has_refund_kw = any(kw in cust_lower for kw in ("refund", "return", "cancel", "money back", "pre paid", "prepaid", "wrong product", "worng product"))
    has_shipping_kw = any(kw in cust_lower for kw in ("ship", "deliver", "delivery", "dispatch", "courier", "transit", "arrive", "reach"))
    has_water_purifier = (
        "water purifier" in cust_lower
        or "purifier" in cust_lower
        or bool(re.search(r"\bro\b", cust_lower))
        or any("water purifier" in str(v.get("reason", "")).lower() for v in violations)
    )
    has_stock_kw = any(kw in cust_lower for kw in ("stock", "unit", "inventory", "available"))

    # Water Purifier out-of-stock priority
    if has_water_purifier:
        if has_discount_kw or has_shipping_kw:
            return f"Our Kaveri Water Purifier is currently out of stock at our warehouse. For our available appliances, our best authorized discount is {rules.max_discount_percent:g}% and standard delivery is {shipping_days} business days."
        return "Our Kaveri Water Purifier (₹8,499) is currently out of stock at our warehouse. We have our Kaveri Mixer Grinder, Induction Cooktop, Electric Kettle, and Ceiling Fan available in stock."

    # Product/catalog availability inquiry priority
    if has_catalog_kw and not (has_discount_kw and "%" in cust_lower):
        return "At Kaveri Home Appliances, we specialize in 5 quality appliances: our Kaveri Mixer Grinder, Induction Cooktop, Water Purifier, Electric Kettle, and Ceiling Fan. If the product you are asking about is not one of these, we do not currently carry it in stock."

    # Single-intent refund priority when only refund is requested
    if has_refund_kw and not has_discount_kw and not has_shipping_kw:
        return f"We offer full refunds within our standard {rules.refund_window_days}-day return window for eligible appliances in original condition."

    # Customer explicitly asked for both discount and shipping/delivery
    if has_discount_kw and (has_shipping_kw or "tomorrow" in cust_lower or ("delivery" in v_types and "discount" in v_types)):
        return f"Our best authorized discount is {rules.max_discount_percent:g}% today, and standard shipping for our appliances is {shipping_days} business days. Let me know if you would like to proceed with your order."

    # Customer explicitly asked for discount and refund
    if has_discount_kw and has_refund_kw:
        return f"Our best authorized discount is {rules.max_discount_percent:g}% today, and we offer full refunds within our standard {rules.refund_window_days}-day return window for eligible appliances. Let me know if you would like to proceed."

    # Single violation / intent fallbacks
    if has_discount_kw or "discount" in v_types:
        return f"Our best authorized discount is {rules.max_discount_percent:g}% today. Let me know if you would like to proceed with your order."
    elif has_shipping_kw or "delivery" in v_types:
        return f"Standard delivery for our appliances is {shipping_days} business days. We will dispatch your item as quickly as possible."
    elif has_refund_kw or "refund_window" in v_types:
        return f"We offer full refunds within our standard {rules.refund_window_days}-day return window for eligible appliances in original condition."
    elif has_stock_kw or "stock" in v_types:
        return "We currently have verified inventory available in our warehouse ready for dispatch with standard 3 business days delivery."

    return "Thank you for inquiring with Kaveri Home Appliances. Let us know how we can best assist you with your purchase."


def generate_rewrite_candidate(
    original_draft: str,
    violations: list[dict[str, Any]],
    rules: BusinessRules,
    facts: dict[str, Any],
    customer_message: str = "",
    interaction_id: str | None = None,
    force_template: bool = False,
) -> str:
    """Calls the model client or template fallback to generate a compliant rewrite draft."""
    settings = get_settings()

    if force_template or not violations:
        return generate_template_fallback(violations, rules, facts, customer_message)

    # Prepare permitted values context
    allowed_context = (
        f"PERMITTED VALUES:\n"
        f"- Maximum discount: {rules.max_discount_percent:g}%\n"
        f"- Refund window: {rules.refund_window_days} days\n"
        f"- Standard delivery: {rules.standard_shipping_days} days\n"
    )

    violations_str = "\n".join(
        f"- Violated [{v.get('type')}]: '{v.get('quote')}' -> {v.get('reason')}"
        for v in violations
    )

    user_prompt = (
        f"Customer message: \"{customer_message}\"\n\n"
        f"Original non-compliant draft: \"{original_draft}\"\n\n"
        f"Violations to fix:\n{violations_str}\n\n"
        f"{allowed_context}\n"
        f"Provide the rewritten compliant customer reply:"
    )

    messages = [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # In mock mode, generate compliant rewrite matching customer inquiry and violation
    if settings.ALLOW_MOCK:
        cust_lower = customer_message.lower()
        has_discount_viol = any(v.get("type") == "discount" for v in violations)
        has_delivery_viol = any(v.get("type") == "delivery" for v in violations)
        has_refund_viol = any(v.get("type") == "refund_window" for v in violations)
        has_stock_viol = any(v.get("type") == "stock" for v in violations)

        has_shipping_kw = any(kw in cust_lower for kw in ("ship", "deliver", "delivery", "dispatch", "courier", "transit", "reach", "arrive"))
        has_refund_kw = any(kw in cust_lower for kw in ("refund", "return", "cancel", "money back", "pre paid", "prepaid", "wrong product", "worng product"))

        is_discount_intent = any(kw in cust_lower for kw in ("discount", "off", "%", "deal", "deals", "cheaper", "price", "thallubadi"))
        is_delivery_intent = has_shipping_kw or ("tomorrow" in cust_lower) or (any(kw in cust_lower for kw in ("day", "days")) and not has_refund_kw)
        is_refund_intent = has_refund_kw
        is_stock_intent = any(kw in cust_lower for kw in ("stock", "unit", "inventory", "available"))

        # 1. Compound multi-intent questions (address all customer requests in single reply)
        if (is_discount_intent and is_delivery_intent) or (has_discount_viol and has_delivery_viol):
            return generate_template_fallback(violations, rules, facts, customer_message)
        if (is_discount_intent and is_refund_intent) or (has_discount_viol and has_refund_viol):
            return generate_template_fallback(violations, rules, facts, customer_message)
        if (is_delivery_intent and is_stock_intent) or (has_delivery_viol and has_stock_viol):
            return generate_template_fallback(violations, rules, facts, customer_message)

        # 2. Single-intent questions
        if is_discount_intent and has_discount_viol:
            return f"Our best authorized discount is {rules.max_discount_percent:g}% today. Let me know if you would like to proceed with your order."
        elif is_delivery_intent and has_delivery_viol:
            return generate_template_fallback([v for v in violations if v.get("type") == "delivery"], rules, facts, customer_message)
        elif is_refund_intent and has_refund_viol:
            return generate_template_fallback([v for v in violations if v.get("type") == "refund_window"], rules, facts, customer_message)
        elif is_stock_intent and has_stock_viol:
            return generate_template_fallback([v for v in violations if v.get("type") == "stock"], rules, facts, customer_message)
        elif has_discount_viol:
            return f"Our best authorized discount is {rules.max_discount_percent:g}% today. Let me know if you would like to proceed with your order."
        return generate_template_fallback(violations, rules, facts, customer_message)

    res = call_model(
        stage="rewrite",
        messages=messages,
        temperature=0.0,
        max_tokens=200,
        interaction_id=interaction_id,
    )

    if not res.ok or not res.content.strip():
        logger.warning("Rewrite model call failed. Falling back to deterministic template.")
        return generate_template_fallback(violations, rules, facts, customer_message)

    return res.content.strip()


def rewrite_and_reverify(
    original_draft: str,
    violations: list[dict[str, Any]],
    rules: BusinessRules,
    facts: dict[str, Any],
    customer_message: str = "",
    interaction_id: str | None = None,
    max_attempts: int = 2,
    mock_rewrite_override: str | None = None,
) -> tuple[str, list[Promise], str]:
    """Executes the rewrite and re-verification loop.
    
    Returns:
        (final_reply, verified_promises, final_status)
        Where final_status is 'rewritten' or 'held'.
    """
    attempt = 0
    candidate_reply = ""

    while attempt < max_attempts:
        attempt += 1
        logger.info("Rewrite attempt %d/%d for interaction %s", attempt, max_attempts, interaction_id)

        if mock_rewrite_override is not None:
            candidate_reply = mock_rewrite_override
        else:
            candidate_reply = generate_rewrite_candidate(
                original_draft=original_draft,
                violations=violations,
                rules=rules,
                facts=facts,
                customer_message=customer_message,
                interaction_id=interaction_id,
            )

        # Re-extract promises from candidate reply
        re_extracted, ext_status = extract_promises(
            draft=candidate_reply,
            customer_message=customer_message,
            interaction_id=interaction_id,
        )

        if ext_status != "ok":
            logger.warning("Re-extracted promises failed parsing on attempt %d", attempt)
            continue

        # Re-verify through pure rule engine
        re_result = verify(re_extracted, rules, facts)

        if re_result.message_verdict == Verdict.ALLOW:
            logger.info("Rewrite passed re-verification on attempt %d", attempt)
            return candidate_reply, re_result.promises, "rewritten"
        else:
            logger.warning(
                "Rewrite failed re-verification on attempt %d with verdict %s",
                attempt,
                re_result.message_verdict,
            )
            violations = re_result.violations

    # Fallback to template on final attempt before giving up
    template_reply = generate_template_fallback(violations, rules, facts)
    re_extracted, ext_status = extract_promises(
        draft=template_reply,
        customer_message=customer_message,
        interaction_id=interaction_id,
    )
    if ext_status == "ok":
        re_result = verify(re_extracted, rules, facts)
        if re_result.message_verdict == Verdict.ALLOW:
            logger.info("Template fallback passed re-verification.")
            return template_reply, re_result.promises, "rewritten"

    logger.warning("All rewrite attempts failed. Holding message.")
    return HOLDING_REPLY, [], "held"
