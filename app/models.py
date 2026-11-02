"""Model Client Interface for Satyahd.

All Meta and open-weights model calls live behind this interface.
Supports:
- Live Meta Model API (OpenAI-compatible /chat/completions) with timeout & retries
- Mock mode (ALLOW_MOCK=true) labeled clearly as MOCK
- Automatic model_usage logging per stage into SQLite
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings
from app.db import get_db

logger = logging.getLogger("satyahd.models")


@dataclass
class ModelResult:
    content: str
    stage: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    ok: bool
    is_mock: bool
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)


def log_model_usage(
    stage: str,
    model: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    ok: bool,
    interaction_id: str | None = None,
) -> None:
    """Records every model call and calculated cost into the model_usage database table."""
    try:
        settings = get_settings()
        cost_usd = (
            (input_tokens / 1_000_000 * settings.COST_PER_M_INPUT_TOKENS)
            + (output_tokens / 1_000_000 * settings.COST_PER_M_OUTPUT_TOKENS)
        )
        usage_id = f"mu_{uuid.uuid4().hex[:12]}"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO model_usage (
                    id, interaction_id, stage, model, latency_ms, input_tokens, output_tokens, ok, cost_usd
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage_id,
                    interaction_id,
                    stage,
                    model,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    1 if ok else 0,
                    cost_usd,
                ),
            )
    except Exception as exc:
        logger.error("Failed to record model_usage: %s", exc)


def _generate_mock_response(
    stage: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> str:
    """Deterministic mock responses for rapid local development and testing."""
    # Look at the latest user or system instruction
    last_content = ""
    for msg in reversed(messages):
        if msg.get("role") in ("user", "system"):
            content = msg.get("content", "")
            if isinstance(content, str):
                last_content = content
                break

    last_lower = last_content.lower()

    if stage == "sales_agent":
        if "over-eager" in last_lower or "over_eager" in last_lower:
            return "[MOCK] Yes! I can give you a 50% discount and deliver tomorrow! We have 500 units in stock."
        return "[MOCK] Hello! We have the Kaveri Mixer Grinder in stock with 3 days standard shipping. How may I assist you?"

    elif stage == "pre_filter":
        # Check simple promise keywords
        has_keywords = any(kw in last_lower for kw in [
            "free", "refund", "discount", "off", "tomorrow", "today", "days", "hours", "guarantee", "stock", "%"
        ])
        return "has_promise" if has_keywords else "no_promise"

    elif stage == "extraction":
        # Extract draft text across all conversation messages
        all_text = " ".join(str(m.get("content", "")) for m in messages)
        draft_match = re.search(r'Agent draft reply:\s*"(.*?)"', all_text, re.DOTALL)
        draft_text = draft_match.group(1) if draft_match else all_text
        draft_lower = draft_text.lower()

        # Check for negative statements (not promises)
        if "cannot refund" in draft_lower or "no discount" in draft_lower or "cannot offer" in draft_lower:
            return json.dumps({"promises": []})

        mock_promises = []

        # 1. Discount promises (English + Tamil + Tanglish)
        if "half price" in draft_lower or "paathi vela" in draft_lower or "பாதி விலை" in draft_lower:
            mock_promises.append({
                "type": "discount",
                "value": 50.0,
                "unit": "percent",
                "unlimited": False,
                "product_ref": None,
                "order_ref": None,
                "quote": "half price" if "half price" in draft_lower else ("paathi vela" if "paathi vela" in draft_lower else "பாதி விலை"),
                "confidence": 0.95,
                "vague": False,
                "damage_basis": False,
            })
        elif (re.search(r"(?<!feel\s)\bfree\b", draft_lower) and "feel free" not in draft_lower) or "no charge" in draft_lower or "zero cost" in draft_lower or "இலவசம்" in draft_lower or "ilavasam" in draft_lower:
            q = "free" if "free" in draft_lower and "feel free" not in draft_lower else ("no charge" if "no charge" in draft_lower else ("இலவசம்" if "இலவசம்" in draft_lower else "zero cost"))
            mock_promises.append({
                "type": "discount",
                "value": 100.0,
                "unit": "percent",
                "unlimited": False,
                "product_ref": None,
                "order_ref": None,
                "quote": q,
                "confidence": 0.98,
                "vague": False,
                "damage_basis": False,
            })
        elif "twenty percent" in draft_lower:
            mock_promises.append({
                "type": "discount",
                "value": 20.0,
                "unit": "percent",
                "unlimited": False,
                "product_ref": None,
                "order_ref": None,
                "quote": "twenty percent",
                "confidence": 0.95,
                "vague": False,
                "damage_basis": False,
            })
        elif "fifty percent" in draft_lower:
            mock_promises.append({
                "type": "discount",
                "value": 50.0,
                "unit": "percent",
                "unlimited": False,
                "product_ref": None,
                "order_ref": None,
                "quote": "fifty percent",
                "confidence": 0.95,
                "vague": False,
                "damage_basis": False,
            })
        else:
            pct_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|விழுக்காடு\b|thallubadi\b|தள்ளுபடி\b)", draft_text, re.IGNORECASE)
            if pct_m:
                val = float(pct_m.group(1))
                mock_promises.append({
                    "type": "discount",
                    "value": val,
                    "unit": "percent",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": pct_m.group(0),
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })

        # 2. Delivery promises (English + Tamil + Tanglish)
        has_refund_terms = any(kw in draft_lower for kw in ("refund", "return", "திரும்ப", "thirumba", "பணம்", "panam"))
        is_delivery_context = "tracking" not in draft_lower and "cancel" not in draft_lower and "contact" not in draft_lower and not has_refund_terms
        if is_delivery_context:
            if "same day" in draft_lower or "இன்றே" in draft_lower or "inikkey" in draft_lower or "innikku" in draft_lower:
                q = "same day" if "same day" in draft_lower else ("இன்றே" if "இன்றே" in draft_lower else ("inikkey" if "inikkey" in draft_lower else "innikku"))
                mock_promises.append({
                    "type": "delivery",
                    "value": 0.0,
                    "unit": "days",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": q,
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })
            elif "tomorrow" in draft_lower or "நாளை" in draft_lower or "naalaikku" in draft_lower or "naalai" in draft_lower:
                m_del = re.search(r"(?:tomorrow|நாளை(?:க்கு)?|naalai(?:kku)?)", draft_text, re.IGNORECASE)
                q = m_del.group(0) if m_del else "tomorrow"
                mock_promises.append({
                    "type": "delivery",
                    "value": 1.0,
                    "unit": "days",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": q,
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })
            elif "in 24 hours" in draft_lower or "24 மணி" in draft_lower:
                m_del = re.search(r"(?:in 24 hours|24 மணி)", draft_text, re.IGNORECASE)
                q = m_del.group(0) if m_del else "in 24 hours"
                mock_promises.append({
                    "type": "delivery",
                    "value": 1.0,
                    "unit": "days",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": q,
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })
            elif re.search(r"\b(\d+(?:\.\d+)?)\s*(?:-?\s*days?|business\s*days?|நாட்கள்|naatkal)", draft_text, re.IGNORECASE) and not has_refund_terms:
                m_days = re.search(r"(\d+(?:\.\d+)?)\s*(?:-?\s*days?|business\s*days?|நாட்கள்|naatkal)", draft_text, re.IGNORECASE)
                val = float(m_days.group(1))
                mock_promises.append({
                    "type": "delivery",
                    "value": val,
                    "unit": "days",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": m_days.group(0),
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })
            elif "soon" in draft_lower or "quickly" in draft_lower or "should arrive soon" in draft_lower or "சீக்கிரம்" in draft_lower or "seekiram" in draft_lower:
                m_del = re.search(r"(?:should arrive soon|சீக்கிரம்|seekiram|soon|quickly)", draft_text, re.IGNORECASE)
                q = m_del.group(0) if m_del else "soon"
                mock_promises.append({
                    "type": "delivery",
                    "value": None,
                    "unit": "days",
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": q,
                    "confidence": 0.85,
                    "vague": True,
                    "damage_basis": False,
                })

        # 3. Refund / return promises (English + Tamil + Tanglish)
        has_return_refund = any(kw in draft_lower for kw in ("refund", "return", "திரும்ப", "thirumba", "money back"))
        if "any time" in draft_lower or (has_return_refund and "whenever" in draft_lower) or "no questions asked" in draft_lower or "எப்பொழுது வேண்டுமானாலும்" in draft_lower or "eppovenaalum" in draft_lower:
            m_ref = re.search(r"(?:any time|whenever|no questions asked|எப்பொழுது வேண்டுமானாலும்|eppovenaalum)", draft_text, re.IGNORECASE)
            q = m_ref.group(0) if m_ref else "any time"
            mock_promises.append({
                "type": "refund_window",
                "value": None,
                "unit": "days",
                "unlimited": True,
                "product_ref": None,
                "order_ref": None,
                "quote": q,
                "confidence": 0.95,
                "vague": False,
                "damage_basis": False,
            })
        elif "refund" in draft_lower or "return" in draft_lower or "திரும்ப" in draft_lower or "thirumba" in draft_lower:
            m = re.search(r"(\d+\s*(?:-?\s*days?|நாட்கள்|naatkal)?(?:\s*kulla)?\s*(?:refund|return\s*window|return|திரும்ப|thirumba)|\d+-day\s*return\s*window|\d+\s*days?|\d+\s*நாட்கள்|\d+\s*naatkal)", draft_text, re.IGNORECASE)
            days_m = re.search(r"(\d+)\s*-?\s*(?:days?|நாட்கள்|naatkal)?", draft_text)
            has_damage = "damage" in draft_lower or "broken" in draft_lower or "defect" in draft_lower or "சேதம்" in draft_lower or "setham" in draft_lower
            val = float(days_m.group(1)) if days_m else 14.0
            mock_promises.append({
                "type": "refund_window",
                "value": val,
                "unit": "days",
                "unlimited": False,
                "product_ref": None,
                "order_ref": None,
                "quote": m.group(0) if m else ("return window" if "return" in draft_lower else ("திரும்ப" if "திரும்ப" in draft_lower else "refund")),
                "confidence": 0.90,
                "vague": False,
                "damage_basis": has_damage,
            })

        # 4. Stock promises
        pref = None
        if "water purifier" in all_text.lower() or "purifier" in all_text.lower():
            pref = "P3"
        elif "mixer" in all_text.lower():
            pref = "P1"
        elif "induction" in all_text.lower():
            pref = "P2"
        elif "kettle" in all_text.lower():
            pref = "P4"

        is_negative_stock = "out of stock" in draft_lower or "not in stock" in draft_lower or "not available" in draft_lower or "zero units" in draft_lower
        if not is_negative_stock:
            stock_m = re.search(r"(\d+)\s*units", draft_text)
            if stock_m:
                mock_promises.append({
                    "type": "stock",
                    "value": float(stock_m.group(1)),
                    "unit": "units",
                    "unlimited": False,
                    "product_ref": pref,
                    "order_ref": None,
                    "quote": stock_m.group(0),
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })
            elif ("in stock" in draft_lower and "out of stock" not in draft_lower and "not in stock" not in draft_lower) or ("available" in draft_lower and "not available" not in draft_lower):
                m_stk = re.search(r"(?:in stock|available)", draft_text, re.IGNORECASE)
                mock_promises.append({
                    "type": "stock",
                    "value": None,
                    "unit": "units",
                    "unlimited": False,
                    "product_ref": pref,
                    "order_ref": None,
                    "quote": m_stk.group(0) if m_stk else "in stock",
                    "confidence": 0.95,
                    "vague": False,
                    "damage_basis": False,
                })

        # 5. Escalation / compensation / review triggers
        review_triggers = [
            "compensation", "replacement", "senior review", "senior agent",
            "quality team", "logistics team", "supervisor", "wrong item", "investigate",
            "check with our team"
        ]
        for trigger in review_triggers:
            if trigger in draft_lower:
                trig_m = re.search(re.escape(trigger), draft_text, re.IGNORECASE)
                q = trig_m.group(0) if trig_m else trigger
                mock_promises.append({
                    "type": "other",
                    "value": None,
                    "unit": None,
                    "unlimited": False,
                    "product_ref": None,
                    "order_ref": None,
                    "quote": q,
                    "confidence": 0.90,
                    "vague": True,
                    "damage_basis": False,
                })
                break

        return json.dumps({"promises": mock_promises})

    elif stage == "rewrite":
        all_raw = " ".join(str(m.get("content", "")) for m in messages)
        all_lower = all_raw.lower()

        # Dynamically read permitted values from the prompt context
        deliv_m = re.search(r"Standard delivery:\s*(\d+)\s*days", all_raw, re.IGNORECASE)
        deliv_days = deliv_m.group(1) if deliv_m else "3"

        disc_m = re.search(r"Maximum discount:\s*(\d+(?:\.\d+)?)\s*%", all_raw, re.IGNORECASE)
        disc_pct = disc_m.group(1) if disc_m else "10"

        ref_m = re.search(r"Refund window:\s*(\d+)\s*days", all_raw, re.IGNORECASE)
        ref_days = ref_m.group(1) if ref_m else "14"

        # Extract customer message and violations specifically
        cust_match = re.search(r'Customer message:\s*"(.*?)"', all_raw, re.DOTALL)
        cust_msg = cust_match.group(1).lower() if cust_match else all_lower

        viol_types = set(re.findall(r"Violated\s*\[(\w+)\]", all_raw))

        has_shipping_kw = any(kw in cust_msg for kw in ("ship", "deliver", "delivery", "dispatch", "courier", "transit", "reach", "arrive"))
        has_refund_kw = any(kw in cust_msg for kw in ("refund", "return", "cancel", "money back", "pre paid", "prepaid", "wrong product", "worng product"))
        has_discount_kw = any(kw in cust_msg for kw in ("discount", "off", "%", "deal", "deals", "half price", "price", "offer", "thallubadi"))
        has_water_purifier = (
            "water purifier" in cust_msg
            or "purifier" in cust_msg
            or bool(re.search(r"\bro\b", cust_msg))
        )
        has_stock_kw = any(kw in cust_msg for kw in ("stock", "unit", "units", "inventory", "available"))

        has_catalog_kw = any(kw in cust_msg for kw in ("has this product", "have this product", "this product", "this item", "sell this", "carry this", "do youre shop", "do your shop", "what products", "what do you sell", "in your shop", "in your store", "what appliances", "available in your shop", "is this available", "catalog"))

        # Water Purifier out-of-stock priority
        if has_water_purifier:
            if has_discount_kw or has_shipping_kw:
                return f"Our Kaveri Water Purifier is currently out of stock at our warehouse. For our available appliances, our best authorized discount is {disc_pct}% and standard delivery is {deliv_days} business days."
            return "Our Kaveri Water Purifier (₹8,499) is currently out of stock at our warehouse. We have our Kaveri Mixer Grinder, Induction Cooktop, Electric Kettle, and Ceiling Fan available in stock."

        # Catalog availability inquiry priority
        if has_catalog_kw and not (has_discount_kw and "%" in cust_msg):
            return "At Kaveri Home Appliances, we specialize in 5 quality appliances: our Kaveri Mixer Grinder, Induction Cooktop, Water Purifier, Electric Kettle, and Ceiling Fan. If the product you are asking about is not in our catalog, we do not currently carry it in stock."

        # Single-intent refund priority
        if has_refund_kw and not has_discount_kw and not has_shipping_kw:
            return f"We offer full refunds within our standard {ref_days}-day return window for eligible appliances in original condition."

        # Compound combinations for multi-intent questions
        if has_discount_kw and (has_shipping_kw or "tomorrow" in cust_msg or ("delivery" in viol_types and "discount" in viol_types)):
            return f"Our best authorized discount is {disc_pct}% today, and standard shipping for our appliances is {deliv_days} business days. Let me know if you would like to proceed with your order."
        elif has_discount_kw and has_refund_kw:
            return f"Our best authorized discount is {disc_pct}% today, and we offer full refunds within our standard {ref_days}-day return window for eligible appliances. Let me know if you would like to proceed with your order."
        elif has_discount_kw or "discount" in viol_types:
            return f"Our best authorized discount is {disc_pct}% today. Let me know if you would like to proceed with your order."
        elif has_shipping_kw or "delivery" in viol_types:
            return f"Standard delivery for our appliances is {deliv_days} business days. We will dispatch your item as quickly as possible."
        elif has_refund_kw or "refund_window" in viol_types:
            return f"We offer full refunds within our standard {ref_days}-day return window for eligible appliances in original condition."
        elif has_stock_kw or "stock" in viol_types:
            return "We currently have verified inventory available in our warehouse ready for dispatch with standard 3 business days delivery."
        return f"Our best authorized discount is {disc_pct}% today. Let me know if you would like to proceed with your order."

    elif stage == "self_check":
        return json.dumps({"promises": []})

    elif stage == "image_describe":
        return json.dumps({
            "damage_visible": True,
            "damage_type": "cracked",
            "description": "Cracked front control panel on appliance.",
            "confidence": 0.92,
        })

    elif stage == "red_team":
        return "Can I get 60% off and immediate same day delivery?"

    return "[MOCK] Standard response."


# Per-Role Model Configuration per Meta Model API Docs
STAGE_CONFIGS: dict[str, dict[str, Any]] = {
    "sales_agent": {
        "reasoning_effort": "medium",
        "temperature": 0.7,
        "max_tokens": 300,
    },
    "pre_filter": {
        "reasoning_effort": "minimal",  # Minimal reasoning reduces latency & cost
        "temperature": None,           # Reasoning models reject custom temperature
        "max_tokens": 100,
    },
    "extraction": {
        "reasoning_effort": "minimal",  # Minimal reasoning for fast extraction
        "structured_output": True,       # Use structured JSON schema / json_object
        "temperature": None,           # Avoid temperature 0 incompatibility
        "max_tokens": 400,
    },
    "self_check": {
        "reasoning_effort": "minimal",  # Second-pass verification of missed commitments
        "structured_output": True,
        "temperature": None,
        "max_tokens": 300,
    },
    "rewrite": {
        "reasoning_effort": "minimal",  # Minimal reasoning for bounded rewriting
        "temperature": None,
        "max_tokens": 200,
    },
    "red_team": {
        "reasoning_effort": "medium",
        "temperature": 0.8,
        "max_tokens": 350,
    },
    "image_describe": {
        "reasoning_effort": "minimal",
        "temperature": None,
        "max_tokens": 250,
    },
}


def call_model(
    stage: str,
    messages: list[dict[str, Any]],
    model_name: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    interaction_id: str | None = None,
    force_mock: bool = False,
    provider_name: str | None = None,
) -> ModelResult:
    """Unified entry point for calling model providers.
    
    Stages: sales_agent, pre_filter, extraction, tool_calling, rewrite,
            image_describe, sam_mask, image_generate, red_team.
    """
    from app.providers.registry import call_provider_with_fallback

    settings = get_settings()
    target_model = model_name or settings.MODEL_NAME
    api_key = settings.MODEL_API_KEY or settings.META_API_KEY
    use_mock = force_mock or settings.ALLOW_MOCK or not api_key or api_key.startswith("mock_")

    chosen_provider = "mock" if use_mock else (provider_name or "meta")

    prov_res = call_provider_with_fallback(
        stage=stage,
        messages=messages,
        provider_name=chosen_provider,
        fallback_provider_name="mock",
        model_name=target_model,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        interaction_id=interaction_id,
    )

    return ModelResult(
        content=prov_res.content,
        stage=prov_res.stage,
        model=prov_res.model,
        latency_ms=prov_res.latency_ms,
        input_tokens=prov_res.input_tokens,
        output_tokens=prov_res.output_tokens,
        ok=prov_res.ok,
        is_mock=prov_res.is_mock,
        tool_calls=prov_res.tool_calls,
        raw_response=prov_res.raw_response,
    )


# ── SAM 3.1 & Muse Image Handlers (Section A Technical Corrections) ──────────

def call_sam_segmentation(
    image_bytes: bytes,
    prompt: str = "damaged area",
    interaction_id: str | None = None,
) -> dict[str, Any]:
    """Calls SAM 3.1 via the Meta Responses API to generate segmentation mask."""
    settings = get_settings()
    api_key = settings.MODEL_API_KEY or settings.META_API_KEY
    if settings.ALLOW_MOCK or not api_key or api_key.startswith("mock_"):
        # Deterministic mock response for SAM 3.1
        log_model_usage("sam_mask", f"{settings.SAM_MODEL} [MOCK]", 40, 10, 10, True, interaction_id)
        return {
            "model": settings.SAM_MODEL,
            "mask_path": None,
            "overlay_path": None,
            "detected": True,
            "prompt": prompt,
            "status": "mock_success",
        }

    # Live SAM 3.1 call via Meta Responses API
    url = f"{settings.META_API_BASE.rstrip('/')}/responses"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        import base64
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "model": settings.SAM_MODEL,
            "input": [{"type": "image", "data": b64_img}, {"type": "text", "text": prompt}],
        }
        with httpx.Client(timeout=float(settings.MODEL_TIMEOUT_SECONDS)) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning("SAM 3.1 Responses API call failed, falling back: %s", exc)
    return {"model": settings.SAM_MODEL, "mask_path": None, "overlay_path": None, "status": "unavailable"}


def call_image_generation(
    prompt: str,
    interaction_id: str | None = None,
) -> dict[str, Any]:
    """Generates synthetic appliance images via Meta muse-image-1.0 endpoint."""
    settings = get_settings()
    api_key = settings.MODEL_API_KEY or settings.META_API_KEY
    if settings.ALLOW_MOCK or not api_key or api_key.startswith("mock_"):
        log_model_usage("image_generate", f"{settings.IMAGE_MODEL} [MOCK]", 50, 20, 50, True, interaction_id)
        return {
            "model": settings.IMAGE_MODEL,
            "prompt": prompt,
            "url": None,
            "status": "mock_success",
        }

    url = f"{settings.META_API_BASE.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        payload = {"model": settings.IMAGE_MODEL, "prompt": prompt, "n": 1, "size": "1024x1024"}
        with httpx.Client(timeout=float(settings.MODEL_TIMEOUT_SECONDS)) as client:
            resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.warning("Muse Image generation failed: %s", exc)
    return {"model": settings.IMAGE_MODEL, "status": "failed"}
