"""Promise Extraction module for Satyahd.

Follows Section 3.4:
- Reads agent draft + customer message (to resolve context like 'it')
- Returns JSON validated by Pydantic models with temperature 0
- Structured promise fields: type, value, unit, unlimited, product_ref, order_ref, quote, confidence, vague, damage_basis
- Normalization rules for numbers, fractions, time offsets, negative statements, and conditional promises
- Exact substring quote check: downgrades confidence to 0.3 if quote is not an exact substring of draft
- Auto-retry: 1 retry with validation error appended on invalid JSON; fails closed if retry fails
- Regex safety net: catches missed numbers or keywords (free, refund, tomorrow, guarantee) and adds vague 'other' promises
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import call_model

logger = logging.getLogger("satyahd.extract")


class PromiseType(str, Enum):
    DISCOUNT = "discount"
    REFUND_WINDOW = "refund_window"
    DELIVERY = "delivery"
    STOCK = "stock"
    OTHER = "other"


class Promise(BaseModel):
    type: str = Field(description="Promise category: discount, refund_window, delivery, stock, or other")
    value: float | None = Field(default=None, description="Extracted numerical metric value")
    unit: str | None = Field(default=None, description="Metric unit: percent, days, units, or null")
    unlimited: bool = Field(default=False, description="Whether promise has no conditions ('any time', 'whenever')")
    product_ref: str | None = Field(default=None, description="Referenced product name or ID")
    order_ref: str | None = Field(default=None, description="Referenced order ID")
    quote: str = Field(description="Exact substring quoted from the draft reply")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence score (0 to 1)")
    vague: bool = Field(default=False, description="Whether phrasing is imprecise ('soon', 'quickly', 'some discount')")
    damage_basis: bool = Field(default=False, description="Whether the promise cites damage as justification")
    verdict: str | None = Field(default=None, description="Allow, Block, or Review")
    reason: str | None = Field(default=None, description="Plain English verdict reason")
    rule_name: str | None = Field(default=None, description="Governing business rule name")
    threshold: float | None = Field(default=None, description="Authorised threshold value")
    policy_clause: str | None = Field(default=None, description="Official policy clause text cited")
    evidence: str | None = Field(default=None, description="Factual evidence cited")
    lifecycle_state: str = Field(default="proposed", description="Lifecycle state: proposed, approved, sent, fulfilled, failed, expired, flagged")
    due_date: str | None = Field(default=None, description="Target fulfillment date (ISO format)")


class ExtractionEnvelope(BaseModel):
    promises: list[Promise] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You are an expert promise extraction engine for an e-commerce guardrail system.
Your job is to read an AI sales agent's draft reply and any preceding customer message, and extract EVERY commitment or promise made to the customer into structured JSON.

Normalization and Parsing Rules:
1. Numbers in words: Convert words to numbers ('twenty percent' -> 20, 'fifty percent' -> 50).
2. 'half price' -> type: discount, value: 50, unit: percent.
3. 'free', 'no charge', 'zero cost' -> type: discount, value: 100, unit: percent.
4. 'tomorrow' and 'in 24 hours' -> type: delivery, value: 1, unit: days.
5. 'same day' -> type: delivery, value: 0, unit: days.
6. 'next week' -> type: delivery, value: 7, unit: days.
7. Vague terms: 'soon', 'quickly', 'usually', 'some discount' -> vague: true.
8. Unlimited claims: 'any time', 'whenever', 'no questions asked' -> unlimited: true.
9. Negative statements: Refusals ('we cannot refund', 'no discounts are available') are NOT promises. Do not extract them.
10. Conditional promises: 'buy two and I will give 20 percent' -> extract with stated value (value: 20, unit: percent).
11. Damage claims: If a promise is justified by item damage ('since it arrived damaged, full refund'), set damage_basis: true.
12. Exact Substring Quote: The 'quote' field MUST be an EXACT, character-for-character substring of the draft reply.
13. Fabric & Material Compositions: Percentages or weights specifying garment blends, material composition, fabric feel, or opacity (e.g. '100% French Organic Linen', '78% Cotton, 4% Elastane', '100% Opaque', '165 GSM') describe physical product specifications and are NOT commercial discounts or promises. NEVER extract fabric compositions or garment opacity as discount promises.
14. Output Format: Return JSON ONLY in this format:
{"promises": [
  {
    "type": "discount" | "refund_window" | "delivery" | "stock" | "other",
    "value": number | null,
    "unit": "percent" | "days" | "units" | null,
    "unlimited": true | false,
    "product_ref": string | null,
    "order_ref": string | null,
    "quote": "exact substring from draft",
    "confidence": 0.0 to 1.0,
    "vague": true | false,
    "damage_basis": true | false
  }
]}
"""

# Regex pattern for numbers followed by units, plus core promise keywords
REGEX_SAFETY_PATTERN = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:%|percent\b|days?\b|hours?\b)|\b(?:free|refund|tomorrow|guarantee)\b)",
    re.IGNORECASE,
)

SELF_CHECK_SYSTEM_PROMPT = """You are a verification self-check inspector for an e-commerce guardrail system.
You will be given:
1. An AI sales agent's draft reply
2. The customer's message
3. The list of promises extracted in pass 1

Your task is to answer: "Did I miss any promise?"
Check specifically for:
- Missed discount percentages or dollar/free claims
- Missed delivery timelines ('tomorrow', 'same day', '24 hours')
- Missed refund windows or warranty guarantees
- Missed stock claims

If any promises were missed, return them as JSON adhering to the schema:
{"promises": [ ... ]}
If NO promises were missed, return:
{"promises": []}
"""


def run_self_check_pass(
    draft: str,
    customer_message: str,
    extracted_promises: list[Promise],
    interaction_id: str | None = None,
) -> list[Promise]:
    """Second-pass check: calls Muse Spark with minimal reasoning to detect any missed commitments."""
    if not draft or not draft.strip():
        return extracted_promises

    try:
        user_prompt = (
            f"Customer message: \"{customer_message}\"\n\n"
            f"Agent draft: \"{draft}\"\n\n"
            f"Pass 1 extracted promises:\n"
            f"{json.dumps([p.model_dump() for p in extracted_promises], indent=2)}"
        )
        res = call_model(
            stage="self_check",
            messages=[
                {"role": "system", "content": SELF_CHECK_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=None,
            max_tokens=300,
            interaction_id=interaction_id,
        )
        content = res.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        data = json.loads(content)
        envelope = ExtractionEnvelope.model_validate(data)
        if envelope.promises:
            logger.info("Self-check pass detected %d missed promise(s)", len(envelope.promises))
            merged = list(extracted_promises)
            for p in envelope.promises:
                if p.quote in draft and not any(p.quote == ep.quote for ep in merged):
                    merged.append(p)
            return merged
    except Exception as exc:
        logger.debug("Self-check pass completed without extra additions: %s", exc)

    return extracted_promises


def run_regex_safety_net(draft: str, promises: list[Promise]) -> list[Promise]:
    """Scans draft for numbers with units or promise keywords missed by the extractor.
    
    Any hit not covered by an extracted quote adds a promise of type 'other' with vague=True,
    which will force a review verdict in the rule engine.
    """
    updated_promises = list(promises)
    matches = REGEX_SAFETY_PATTERN.finditer(draft)

    for match in matches:
        matched_text = match.group(0).strip()
        matched_start = match.start()
        matched_end = match.end()

        # Check if this match is part of a negative assertion (e.g. "cannot refund", "no discount")
        preceding_context = draft[max(0, matched_start - 20) : matched_start].lower()
        if any(neg in preceding_context for neg in ("cannot ", "can't ", "no ", "not ", "non-", "without ")):
            continue

        # Check if this match relates to non-delivery contexts (tracking, cancellation) or garment specifications (material blend, opacity, GSM)
        surrounding_context = draft[max(0, matched_start - 35) : min(len(draft), matched_end + 35)].lower()
        if any(ctx_kw in surrounding_context for ctx_kw in (
            "tracking", "cancel", "contact you", "hear back", "sms", "email",
            "linen", "cotton", "silk", "wool", "elastane", "spandex", "polyester", "poly",
            "chanderi", "mulberry", "merino", "fabric", "fiber", "blend", "composition",
            "opaque", "opacity", "gsm", "knit", "weave", "organic", "wash", "care"
        )):
            continue

        # Check if this span is already covered by any extracted promise quote
        is_covered = False
        for p in promises:
            if not p.quote:
                continue
            quote_clean = p.quote.strip()
            q_start = draft.find(quote_clean)
            if q_start != -1:
                q_end = q_start + len(quote_clean)
                # Within quote span or immediately adjacent clause (within 10 chars)
                if (q_start - 10 <= matched_start and matched_end <= q_end + 10):
                    is_covered = True
                    break
            if matched_text.lower() in p.quote.lower() or p.quote.lower() in matched_text.lower():
                is_covered = True
                break
            # Check if this keyword is the subject of an already captured promise type
            m_low = matched_text.lower()
            if p.type == "refund_window" and m_low in ("refund", "return"):
                is_covered = True
                break
            if p.type == "delivery" and (m_low in ("tomorrow", "delivery") or "day" in m_low or "hour" in m_low):
                is_covered = True
                break
            if p.type == "discount" and (m_low in ("discount", "free", "off") or "%" in m_low):
                is_covered = True
                break

            # Check if this matches a numeric value already captured
            if p.value is not None:
                num_m = re.search(r"\d+(?:\.\d+)?", matched_text)
                if num_m and float(num_m.group(0)) == float(p.value):
                    is_covered = True
                    break

        if not is_covered:
            logger.info("Regex safety net triggered on uncovered token: '%s'", matched_text)
            updated_promises.append(
                Promise(
                    type=PromiseType.OTHER.value,
                    value=None,
                    unit=None,
                    unlimited=False,
                    product_ref=None,
                    order_ref=None,
                    quote=matched_text,
                    confidence=0.5,
                    vague=True,
                    damage_basis=False,
                    reason=f"Regex safety net flagged uncovered keyword/metric: '{matched_text}'",
                )
            )

    return updated_promises


def verify_quotes_against_draft(draft: str, promises: list[Promise]) -> list[Promise]:
    """Ensures that every quote is an exact substring of the draft.
    
    If a quote is not an exact substring, its confidence is downgraded to 0.3 (forcing review).
    """
    for p in promises:
        if p.quote not in draft:
            logger.warning(
                "Quote '%s' is not an exact substring of draft. Downgrading confidence to 0.3.",
                p.quote,
            )
            p.confidence = 0.3
            p.reason = (p.reason or "") + " [Quote hallucinated: not an exact substring of draft]"
    return promises


def extract_promises(
    draft: str,
    customer_message: str = "",
    interaction_id: str | None = None,
    mock_override_content: str | None = None,
) -> tuple[list[Promise], str]:
    """Extracts structured promises from agent draft.
    
    Returns:
        (promises_list, status) where status is 'ok' or 'extraction_failed'.
    """
    if not draft or not draft.strip():
        return [], "ok"

    user_prompt = f"Customer message: \"{customer_message}\"\n\nAgent draft reply: \"{draft}\""
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    attempts = 0
    raw_content = ""

    while attempts < 2:
        attempts += 1
        try:
            if mock_override_content is not None:
                raw_content = mock_override_content
            else:
                model_res = call_model(
                    stage="extraction",
                    messages=messages,
                    temperature=0.0,
                    max_tokens=500,
                    interaction_id=interaction_id,
                )
                raw_content = model_res.content
        except Exception as call_exc:
            logger.error("call_model failed during extraction: %s. Failing closed.", call_exc)
            return [], "extraction_failed"

        # Attempt to parse JSON and validate Pydantic model
        try:
            # Strip markdown fences if present
            cleaned = raw_content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            data = json.loads(cleaned)
            envelope = ExtractionEnvelope.model_validate(data)
            promises = envelope.promises

            # 1. Exact Substring Quote Check
            promises = verify_quotes_against_draft(draft, promises)

            # 2. Regex Safety Net
            promises = run_regex_safety_net(draft, promises)

            return promises, "ok"

        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Extraction JSON parsing failed on attempt %d: %s", attempts, exc)
            if attempts == 1:
                # Retry once with validation error appended
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({
                    "role": "user",
                    "content": f"Your previous output was invalid JSON or schema: {exc}. Output ONLY valid JSON adhering strictly to the schema.",
                })
                continue
            else:
                logger.error("Extraction failed after retry. Failing closed.")
                return [], "extraction_failed"

    return [], "extraction_failed"
