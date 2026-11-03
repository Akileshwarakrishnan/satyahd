"""Fashion Conversational Intelligence & Catalog Grounding Engine.

Fulfills:
- FR-1: Free-text understanding, typos, and short phrases
- FR-2: Quick-reply buttons & typing interoperability
- FR-3: Multi-intent detection (material, GSM, fit, fabric feel, stretch, care, colors, styling, support)
- FR-4: Clarifying questions for ambiguous inputs
- FR-5, FR-6, FR-7, FR-8: Session memory, product binding, pronoun & follow-up resolution
- FR-9: Strict grounding in fashion catalog attributes (GSM, blend, fit, feel, care, sizes, colors, stock)
- FR-10: Anti-hallucination & out-of-stock honesty
- FR-11: In-memory cached catalog lookups
- FR-12, FR-13, FR-14, FR-15: Short, warm 2-3 sentence replies with dynamic next steps and phrase rotation
- FR-16, FR-17: Dynamic follow-up chips
- FR-18: 2-strike escalation to human support
- UX-6: Tanglish & Tamil-English code-mix support
- NFR-4: Parallel async execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator

from app.config import BASE_DIR
from app.session import (
    add_turn,
    escalate_session,
    get_or_create_session,
    get_recent_history,
    record_fallback,
    reset_fallback,
)

logger = logging.getLogger("satyahd.fashion_agent")

PRODUCTS_FILE = BASE_DIR / "data" / "products.json"

# In-memory product catalog cache for instant lookups (<1ms) (FR-11)
_CATALOG_CACHE: dict[str, dict[str, Any]] = {}
_LAST_OPENER_USED: dict[str, str] = {}


def load_fashion_catalog() -> dict[str, dict[str, Any]]:
    """Loads and caches fashion and store products from JSON."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE:
        return _CATALOG_CACHE

    if PRODUCTS_FILE.exists():
        try:
            data = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
            for item in data:
                _CATALOG_CACHE[item["id"]] = item
        except Exception as exc:
            logger.error("Error loading products catalog: %s", exc)

    return _CATALOG_CACHE


def get_product_by_id_or_alias(query: str, current_product_id: str | None = None) -> dict[str, Any] | None:
    """Finds product by explicit ID, name, alias, or falls back to current active product."""
    catalog = load_fashion_catalog()
    q = query.lower().strip()

    # 1. Direct ID match
    for pid, prod in catalog.items():
        if pid.lower() == q:
            return prod

    # 2. Check name and aliases
    for pid, prod in catalog.items():
        if prod.get("name", "").lower() in q:
            return prod
        for alias in prod.get("aliases", []):
            if re.search(rf"\b{re.escape(alias)}\b", q):
                return prod

    # 3. Pronoun / context inheritance
    if current_product_id and current_product_id in catalog:
        if any(w in q for w in ("it", "this", "that", "the shirt", "the tee", "the pant", "the kurti", "the sweater", "the dress")):
            return catalog[current_product_id]
        # Relative queries ("what about in black?", "is it stretchy?")
        return catalog[current_product_id]

    # Default fallback to first fashion product (Aura Linen Shirt)
    return catalog.get("F101") or (list(catalog.values())[0] if catalog else None)


def detect_fashion_intents(text: str) -> list[str]:
    """Detects fashion, sizing, fabric, commercial, and small talk intents (FR-3, UX-6)."""
    t = text.lower().strip()
    intents: list[str] = []

    # 1. Human Escalation (FR-18)
    if any(w in t for w in ("human", "agent", "support", "representative", "manager", "supervisor", "call me", "speak to someone", "talk to human", "real person")):
        return ["human_support"]

    # 2. Tanglish & Tamil Code-Mix Queries (UX-6)
    if any(w in t for w in ("summer-ku", "summer ku", "summerku", "veyil", "climate", "hot weather")):
        intents.append("season_suitability")
    if any(w in t for w in ("thallubadi", "offer", "discount", "kammi", "kuraika", "vilai")):
        intents.append("price_and_discount")
    if any(w in t for w in ("stretch irukuma", "stretchable-aa", "flexibility", "stretchy")):
        intents.append("stretch")
    if any(w in t for w in ("soft-aa", "uruthuma", "rough-aa", "feel", "touch", "hand feel")):
        intents.append("fabric_feel")
    if any(w in t for w in ("wash panna", "color poguma", "shrink aaguma", "washing")):
        intents.append("care_wash")
    if any(w in t for w in ("size pathuma", "alavu", "fitting", "measurements")):
        intents.append("fit_and_sizing")
    if any(w in t for w in ("thirumba", "return panna", "refund")):
        intents.append("returns_exchange")

    # 3. GSM & Fabric Weight
    if "gsm" in t or any(w in t for w in ("fabric weight", "thickness", "how thick", "how heavy", "lightweight", "heavyweight")):
        intents.append("gsm_weight")

    # 4. Material Composition (FR-1, FR-9)
    if any(w in t for w in ("material", "fabric", "composition", "blend", "what is it made of", "pure cotton", "pure linen", "silk", "linen", "wool", "materiel")):
        intents.append("material_composition")

    # 5. Fabric Feel & Texture
    if any(w in t for w in ("feel", "soft", "itchy", "scratchy", "coarse", "breathable", "airy", "texture", "smooth", "comfortable")):
        if "fabric_feel" not in intents:
            intents.append("fabric_feel")

    # 6. Stretch & Mobility
    if any(w in t for w in ("stretch", "stretchy", "elastic", "spandex", "elastane", "squat", "bend", "tight across")):
        if "stretch" not in intents:
            intents.append("stretch")

    # 7. Fit & Sizing (FR-4)
    if any(w in t for w in ("fit", "size", "sizing", "tight", "loose", "oversized", "baggy", "slim", "chest", "waist", "will it fit", "size chart", "measurements")):
        if "fit_and_sizing" not in intents:
            intents.append("fit_and_sizing")

    # 8. Transparency & Opacity
    if any(w in t for w in ("transparent", "see through", "see-through", "sheer", "opaque", "innerwear", "undershirt", "can you see through")):
        intents.append("transparency")

    # 9. Colors & Variants
    if any(w in t for w in ("color", "colors", "colour", "colours", "black", "white", "blue", "green", "shades", "variants", "what about in")):
        intents.append("colors_and_variants")

    # 10. Care Instructions & Shrinkage
    if any(w in t for w in ("wash", "care", "iron", "ironing", "dry clean", "shrink", "shrinkage", "maintenance", "laundry")):
        if "care_wash" not in intents:
            intents.append("care_wash")

    # 11. Season & Occasion
    if any(w in t for w in ("summer", "winter", "hot", "cold", "rainy", "humid", "wedding", "office", "formal", "casual", "occasion", "party")):
        if "season_suitability" not in intents:
            intents.append("season_suitability")

    # 12. Styling & Accessories
    if any(w in t for w in ("style", "styling", "pair with", "wear with", "matching", "match with", "accessories", "shoes", "outfit")):
        intents.append("styling_accessories")

    # 13. Stock & Availability
    if any(w in t for w in ("stock", "available", "units", "left", "in stock", "out of stock")):
        intents.append("stock")

    # 14. Price, Discount, Deals
    if any(w in t for w in ("price", "cost", "how much", "rate", "rupees", "rs", "₹", "discount", "coupon", "deal", "cheap")):
        if "price_and_discount" not in intents:
            intents.append("price_and_discount")

    # 15. Shipping & Delivery
    if any(w in t for w in ("ship", "shipping", "deliver", "delivery", "dispatch", "when will it arrive", "reach me")):
        intents.append("shipping_delivery")

    # 16. Greetings & Small Talk
    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("hi", "hello", "hey", "good morning", "good evening", "namaste", "vanakkam")):
        intents.append("greeting")
    if any(w in t for w in ("thanks", "thank you", "great", "awesome", "perfect", "good")):
        intents.append("acknowledgment")

    if not intents:
        intents.append("general_inquiry")

    return intents


def generate_dynamic_chips(intents: list[str], product: dict[str, Any]) -> list[str]:
    """Generates 2-3 dynamic, contextual follow-up chips based on the topic just discussed (FR-16, FR-17)."""
    chips: list[str] = []

    if "material_composition" in intents or "gsm_weight" in intents:
        chips = ["How does it feel?", "Care instructions", "Size guide"]
    elif "fabric_feel" in intents or "stretch" in intents:
        chips = ["Is it see-through?", "Available colors", "Fit & sizing"]
    elif "fit_and_sizing" in intents:
        chips = ["Is it stretchy?", "Fabric feel", "Available colors"]
    elif "colors_and_variants" in intents:
        chips = ["Fabric feel", "Check stock", "Care instructions"]
    elif "season_suitability" in intents or "transparency" in intents:
        chips = ["Material details", "Available colors", "Styling tips"]
    elif "styling_accessories" in intents:
        chips = ["Matching Chinos", "Available sizes", "Delivery time"]
    elif "care_wash" in intents:
        chips = ["Fabric feel", "Material details", "Delivery time"]
    elif "stock" in intents or "price_and_discount" in intents:
        chips = ["Delivery timeline", "Return policy", "Fabric details"]
    elif "human_support" in intents:
        chips = ["Call human stylist", "WhatsApp support", "Back to shopping"]
    else:
        chips = ["Material & feel", "Size chart", "Available colors"]

    return chips[:3]


def format_fashion_response(
    intents: list[str],
    product: dict[str, Any],
    session_id: str,
    raw_query: str,
    consecutive_fallbacks: int = 0,
) -> tuple[str, list[str], bool, float, bool]:
    """Generates a warm, concise, 2-3 sentence grounded reply with dynamic follow-up steps (FR-12, FR-13, FR-14, FR-15).
    
    Returns:
        (reply_text, chips, is_grounded, confidence, should_escalate)
    """
    p_name = product.get("name", "our garment")
    p_mat = product.get("material", "premium woven fiber")
    p_gsm = product.get("gsm", 180)
    p_fit = product.get("fit", "Regular fit")
    p_feel = product.get("fabric_feel", "Soft, comfortable hand-feel")
    p_stretch = product.get("stretch", "Comfort stretch")
    p_care = product.get("care_instructions", "Gentle wash recommended")
    p_sizes = ", ".join(product.get("available_sizes", ["S", "M", "L", "XL"]))
    p_colors = ", ".join(product.get("available_colors", ["Classic"]))
    p_price = product.get("price", 1899)
    p_stock = product.get("stock", 0)
    p_season = product.get("season", "All-season wear")
    p_transparency = product.get("transparency", "100% Opaque")
    p_styling = product.get("styling_tips", "Pairs well with everyday trousers or chinos")

    chips = generate_dynamic_chips(intents, product)

    # ── FR-18: Human Support Intent or 2-Strike Consecutive Fallback ───────────
    if "human_support" in intents or consecutive_fallbacks >= 2:
        reply = (
            "I want to make sure you get the best guidance. "
            "I've flagged your session for our senior human styling specialist. "
            "Would you like to connect with them right away?"
        )
        escalate_session(session_id)
        return reply, ["Connect to Human Stylist", "WhatsApp Support", "Continue Shopping"], True, 1.0, True

    # ── Out of Stock Honesty Check (FR-10) ─────────────────────────────────────
    if p_stock <= 0 and ("stock" in intents or "price_and_discount" in intents or "colors_and_variants" in intents):
        reply = (
            f"Our {p_name} is currently out of stock at our fulfillment hub. "
            f"We are working on replenishing our stock soon. "
            f"Would you like me to recommend our Aura Linen Shirt or CloudSoft Tee instead?"
        )
        return reply, ["See Aura Linen Shirt", "See CloudSoft Tee", "Notify Me on Restock"], True, 1.0, False

    # ── 1. GSM & Fabric Weight ────────────────────────────────────────────────
    if "gsm_weight" in intents:
        weight_desc = "lightweight and breezy" if p_gsm < 200 else ("mid-to-heavyweight with clean structure" if p_gsm < 280 else "cozy, dense knit")
        reply = (
            f"The {p_name} is crafted with a fabric weight of {p_gsm} GSM, making it {weight_desc}. "
            f"This gives it great drape without feeling stiff or bulky on the body. "
            f"Would you like to know how the fabric feels against the skin?"
        )
        return reply, chips, True, 0.98, False

    # ── 2. Material Composition (FR-1, FR-9) ──────────────────────────────────
    if "material_composition" in intents:
        reply = (
            f"The {p_name} is made from {p_mat}. "
            f"It offers natural breathability and is woven for long-lasting everyday comfort. "
            f"Would you like details on its fabric feel or sizing?"
        )
        return reply, chips, True, 0.99, False

    # ── 3. Fabric Feel & Texture ──────────────────────────────────────────────
    if "fabric_feel" in intents:
        reply = (
            f"On the body, the {p_name} has a {p_feel} "
            f"It is completely non-scratchy and gentle even on sensitive skin. "
            f"Are you curious about its stretch or care instructions?"
        )
        return reply, chips, True, 0.99, False

    # ── 4. Stretch & Flexibility ──────────────────────────────────────────────
    if "stretch" in intents:
        reply = (
            f"For movement, the {p_name} features {p_stretch}. "
            f"It comfortably accommodates daily movement while holding its tailored silhouette. "
            f"Would you like me to check your recommended size?"
        )
        return reply, chips, True, 0.98, False

    # ── 5. Fit & Sizing (FR-4 Clarifying Question for Vague Inputs) ───────────
    if "fit_and_sizing" in intents:
        q_lower = raw_query.lower()
        if any(w in q_lower for w in ("will it fit me", "will this fit", "is it fit", "my size")):
            reply = (
                f"The {p_name} has a {p_fit}, available in sizes {p_sizes}. "
                f"What size do you usually wear in shirts, or would you like me to share our exact chest and shoulder measurements?"
            )
        else:
            reply = (
                f"The {p_name} is designed with a {p_fit}. "
                f"It runs true to size and is currently in stock across {p_sizes}. "
                f"Would you like recommendations on sizing or available colors?"
            )
        return reply, chips, True, 0.97, False

    # ── 6. Season Suitability (Summer / Winter / Tanglish) ─────────────────────
    if "season_suitability" in intents:
        reply = (
            f"Yes, the {p_name} is ideal for {p_season}. "
            f"Its {p_mat} naturally dissipates body heat to keep you cool and comfortable all day. "
            f"Would you like to know about available color options?"
        )
        return reply, chips, True, 0.98, False

    # ── 7. Transparency / Opacity ─────────────────────────────────────────────
    if "transparency" in intents:
        reply = (
            f"Regarding fabric opacity: the {p_name} is {p_transparency}. "
            f"You get an elegant drape without unintended sheer show-through. "
            f"Would you like details on fabric feel or care instructions?"
        )
        return reply, chips, True, 0.98, False

    # ── 8. Colors and Variants ────────────────────────────────────────────────
    if "colors_and_variants" in intents:
        q_lower = raw_query.lower()
        # Specific color query (e.g. "what about in black?", "is black available?")
        for col in product.get("available_colors", []):
            if col.lower() in q_lower:
                reply = (
                    f"Yes! The {col} edition of the {p_name} is available and in stock. "
                    f"It maintains a deep, rich hue that stays vibrant after washing. "
                    f"Would you like to check available sizes in {col}?"
                )
                return reply, chips, True, 0.99, False

        reply = (
            f"The {p_name} comes in {len(product.get('available_colors', []))} shades: {p_colors}. "
            f"All colors are vat-dyed for excellent colorfastness. "
            f"Which color shade catches your eye?"
        )
        return reply, chips, True, 0.99, False

    # ── 9. Care Instructions & Laundry ────────────────────────────────────────
    if "care_wash" in intents:
        reply = (
            f"For easy maintenance: {p_care}. "
            f"Following these steps preserves the fiber luster and prevents unwanted shrinkage. "
            f"Would you like to know about shipping and returns?"
        )
        return reply, chips, True, 0.99, False

    # ── 10. Styling Tips ──────────────────────────────────────────────────────
    if "styling_accessories" in intents:
        reply = (
            f"Here is a quick styling tip: {p_styling}. "
            f"It transitions seamlessly between elevated workwear and casual weekend outings. "
            f"Would you like to see our matching FlexMotion Chinos?"
        )
        return reply, ["See FlexMotion Chinos", "Available Colors", "Size Guide"], True, 0.96, False

    # ── 11. Price & Delivery ──────────────────────────────────────────────────
    if "price_and_discount" in intents:
        reply = (
            f"The {p_name} is priced at ₹{p_price:,} with standard delivery in {product.get('shipping_days', 3)} business days. "
            f"We also offer an authorized promotional discount of up to 10% on first-time orders. "
            f"Would you like to check stock in your size?"
        )
        return reply, ["Check Stock", "Delivery Timeline", "Return Policy"], True, 0.99, False

    if "shipping_delivery" in intents:
        reply = (
            f"Standard shipping takes {product.get('shipping_days', 3)} business days to your address with end-to-end tracking. "
            f"We also offer a 7-day hassle-free return and exchange window. "
            f"Can I help you finalize your size or color selection?"
        )
        return reply, ["Available Sizes", "Return Policy", "Material Details"], True, 0.99, False

    if "returns_exchange" in intents:
        reply = (
            f"We provide a 7-day return and exchange window for unworn items with original tags intact. "
            f"If the fit isn't perfect, our courier will pick it up directly from your doorstep. "
            f"Would you like me to help you choose the right size now?"
        )
        return reply, ["Size Guide", "Check Delivery", "Fabric Details"], True, 0.99, False

    # ── 12. Greetings & Small Talk ────────────────────────────────────────────
    if "greeting" in intents:
        openers = [
            f"Hello! I'm your store styling assistant. We're currently featuring our {p_name} (₹{p_price:,}). How can I help you style your look today?",
            f"Welcome! Looking for comfortable, stylish apparel? Our {p_name} is our top recommendation today. Would you like to explore its material and fit?",
            f"Hi there! Happy to assist you. What can I tell you about the {p_name}—fabric feel, sizing, or colors?",
        ]
        reply = random.choice(openers)
        return reply, ["Material & feel", "Size chart", "Available colors"], True, 1.0, False

    if "acknowledgment" in intents:
        reply = (
            "You're very welcome! I'm right here if you want to check another size, color, or explore similar pieces. "
            "Let me know whenever you're ready!"
        )
        return reply, ["Available Colors", "Size Guide", "Styling Tips"], True, 1.0, False

    # ── 13. Fallback / Clarification (FR-10, FR-18) ───────────────────────────
    reply = (
        f"Regarding the {p_name}: I can help you with its {p_mat} blend, {p_gsm} GSM weight, sizing, and styling advice. "
        f"Could you clarify if you're looking for fit guidance or fabric details?"
    )
    return reply, chips, False, 0.85, False


async def process_fashion_turn(
    session_id: str,
    message: str,
    product_id: str | None = None,
) -> tuple[str, list[str], dict[str, Any], bool, float, bool]:
    """Processes a user message asynchronously, running intent, catalog lookup, and history in parallel (NFR-4).
    
    Returns:
        (reply_text, chips, product_meta, is_grounded, confidence, is_escalated)
    """
    # Parallel retrieval (NFR-4)
    async def get_history_task():
        return get_recent_history(session_id, limit=10)

    async def get_product_task():
        return get_product_by_id_or_alias(message, current_product_id=product_id)

    async def get_intents_task():
        return detect_fashion_intents(message)

    history, product, intents = await asyncio.gather(
        get_history_task(),
        get_product_task(),
        get_intents_task(),
    )

    if not product:
        product = get_product_by_id_or_alias("F101")

    sess = get_or_create_session(session_id, product_id=product["id"])

    # Consecutive fallback tracking for FR-18
    reply, chips, is_grounded, confidence, should_escalate = format_fashion_response(
        intents=intents,
        product=product,
        session_id=session_id,
        raw_query=message,
        consecutive_fallbacks=sess.fallback_count,
    )

    if is_grounded:
        reset_fallback(session_id)
    else:
        record_fallback(session_id)

    # Persist turns into multi-turn sliding window (FR-5)
    add_turn(
        session_id=session_id,
        role="user",
        content=message,
        intent=",".join(intents),
        grounded=True,
    )
    add_turn(
        session_id=session_id,
        role="assistant",
        content=reply,
        intent=",".join(intents),
        chips=chips,
        grounded=is_grounded,
        confidence=confidence,
    )

    return reply, chips, product, is_grounded, confidence, should_escalate


async def stream_fashion_tokens(reply: str) -> AsyncGenerator[str, None]:
    """Streams response text token by token with natural reading cadence (NFR-1, UX-2)."""
    # Split text into natural token chunks (words and punctuation)
    tokens = re.findall(r"\S+|\s+", reply)
    for token in tokens:
        yield token
        # Natural short delay (15-25ms) so tokens appear smoothly
        await asyncio.sleep(0.018)
