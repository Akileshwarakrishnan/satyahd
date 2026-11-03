"""Modern Conversational Intelligence Engine for Satyahd.

Implements Modern Conversational Intelligence Requirements:
1. Natural conversation: friendly, knowledgeable, adaptive length, no robotic filler.
2. Context awareness: multi-turn memory, resolves "What about the cheaper one?", pronoun resolution.
3. Useful follow-up: answers first, asks relevant follow-up, suggests next steps.
4. Emotional intelligence: recognizes frustration, confusion, hesitation, declines; responds empathetically.
5. Business-grounded answers: uses real Kaveri Home Appliances catalog, prices, and stock.
6. Satyahd verification layer: drafts natural answers for verification and bounded rewriting.
7. Multiple conversation styles: friendly_casual, professional_concise, patient_explanatory, empathetic_support, product_discovery.
8. Compound query support: answers multiple questions in a single query (e.g. discount AND shipping).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.rules import BusinessRules, load_rules
from app.tools import default_adapter

logger = logging.getLogger("satyahd.conversation")

# Catalog metadata with realistic specs and pricing
CATALOG_METADATA: dict[str, dict[str, Any]] = {
    "F101": {
        "id": "F101",
        "name": "Aura French Organic Linen Shirt",
        "aliases": ["linen shirt", "aura shirt", "french linen", "linen", "shirt"],
        "price": 1899,
        "material": "100% French Organic Linen",
        "gsm": 165,
        "fit": "Relaxed Regular Fit with curved hem",
        "description": "165 GSM 100% French organic linen shirt with breathable drape and natural cooling.",
        "category": "fashion",
    },
    "F102": {
        "id": "F102",
        "name": "CloudSoft Heavyweight Cotton Tee",
        "aliases": ["cotton tee", "cloudsoft tee", "oversized tee", "tshirt", "t-shirt", "tee"],
        "price": 999,
        "material": "100% Combed Ring-Spun Compact Cotton",
        "gsm": 240,
        "fit": "Oversized Drop-Shoulder Boxy Fit",
        "description": "240 GSM heavyweight combed cotton tee with peach-skin softness and structured silhouette.",
        "category": "fashion",
    },
    "F103": {
        "id": "F103",
        "name": "FlexMotion 4-Way Stretch Chino Pant",
        "aliases": ["chino pant", "flexmotion chino", "chinos", "trousers", "pants", "pant"],
        "price": 2499,
        "material": "78% Cotton, 18% Recycled Polyester, 4% Elastane",
        "gsm": 260,
        "fit": "Slim Tapered Ergonomic Fit",
        "description": "260 GSM performance chinos with 4-way active stretch and tailored silhouette.",
        "category": "fashion",
    },
    "F104": {
        "id": "F104",
        "name": "Zari Mulberry Silk Festive Kurti",
        "aliases": ["mulberry silk kurti", "silk kurti", "zari kurti", "kurti", "festive kurti", "tunic"],
        "price": 3499,
        "material": "80% Pure Mulberry Silk, 20% Fine Cotton",
        "gsm": 120,
        "fit": "Straight Calf-Length Festive Cut",
        "description": "120 GSM pure mulberry silk with antique gold Zari borders (Currently Out of Stock).",
        "category": "fashion",
    },
    "F105": {
        "id": "F105",
        "name": "Merino Wool Ribbed Knit Cardigan",
        "aliases": ["merino cardigan", "wool sweater", "ribbed cardigan", "cardigan", "sweater"],
        "price": 3199,
        "material": "100% Extra-Fine Australian Merino Wool",
        "gsm": 320,
        "fit": "Cozy Relaxed Cardigan Fit",
        "description": "320 GSM extra-fine Australian merino wool cardigan with natural temperature regulation.",
        "category": "fashion",
    },
    "P1": {
        "id": "P1",
        "name": "Kaveri Mixer Grinder",
        "aliases": ["mixer grinder", "mixer", "grinder"],
        "price": 2999,
        "watts": "750W",
        "description": "750W copper motor with 3 stainless steel jars, ideal for daily grinding and batter.",
        "category": "kitchen",
    },
    "P2": {
        "id": "P2",
        "name": "Induction Cooktop",
        "aliases": ["induction cooktop", "induction", "cooktop", "stove"],
        "price": 2499,
        "watts": "2000W",
        "description": "2000W energy-efficient cooktop with preset Indian cooking menus and auto-off timer.",
        "category": "kitchen",
    },
    "P3": {
        "id": "P3",
        "name": "Water Purifier",
        "aliases": ["water purifier", "purifier", "ro", "water filter"],
        "price": 8499,
        "watts": "60W",
        "description": "Advanced RO + UV 8-liter storage purifier with mineral cartridge (Currently Out of Stock).",
        "category": "water",
    },
    "P4": {
        "id": "P4",
        "name": "Electric Kettle",
        "aliases": ["electric kettle", "kettle", "water heater"],
        "price": 999,
        "watts": "1500W",
        "description": "1.5L cordless stainless steel kettle with rapid boiling and dry-boil safety protection.",
        "category": "kitchen",
    },
    "P5": {
        "id": "P5",
        "name": "Ceiling Fan",
        "aliases": ["ceiling fan", "fan"],
        "price": 1899,
        "watts": "75W",
        "description": "1200mm sweep aerodynamic blades with 100% copper motor and silent operation.",
        "category": "home",
    },
}


@dataclass
class ConversationContext:
    session_id: str
    current_product_id: str | None = None
    current_product_name: str | None = None
    sentiment: str = "neutral"  # neutral, frustrated, confused, hesitant, declined, excited
    intents: list[str] = field(default_factory=list)  # discount, delivery, refund, stock, price, compare, cancel, human_support, general
    style: str = "friendly_casual"  # friendly_casual, professional_concise, patient_explanatory, empathetic_support, product_discovery
    is_compound: bool = False
    resolved_query: str = ""


def detect_sentiment(text: str) -> str:
    """Detects emotional state of customer from natural language cues."""
    t = text.lower()
    
    # Declining / Changing mind
    if any(w in t for w in ("never mind", "cancel that", "don't want", "dont want", "no thanks", "not interested", "changed my mind", "leave it")):
        return "declined"
    
    # Frustration / Anger
    if any(w in t for w in ("ridiculous", "terrible", "worst", "unacceptable", "waiting for hours", "nobody answered", "waste of time", "scam", "frustrated", "angry", "cheating", "horrible")):
        return "frustrated"
    
    # Confusion
    if any(w in t for w in ("confused", "don't understand", "dont understand", "what do you mean", "unclear", "explain again")):
        return "confused"
    
    # Hesitation / Price sensitivity
    if any(w in t for w in ("too expensive", "costly", "can't afford", "thinking about it", "not sure", "budget")):
        return "hesitant"
    
    # Excitement / Eagerness
    if any(w in t for w in ("awesome", "great", "love it", "super", "ready to buy", "order now")):
        return "excited"

    return "neutral"


def detect_intents(text: str, has_image: bool = False) -> list[str]:
    """Identifies all user intents present in the message (supports compound queries)."""
    t = text.lower()
    intents: list[str] = []

    # Product / Catalog / Availability Inquiry
    is_catalog_kw = any(w in t for w in (
        "has this product", "have this product", "this product", "this item", "sell this", "carry this",
        "do youre shop", "do your shop", "what products", "what do you sell", "in your shop", "in your store",
        "what appliances", "available in your shop", "available in your store", "is this available", "catalog",
        "do you have", "what do you have", "photo", "picture"
    ))
    if is_catalog_kw or has_image:
        intents.append("catalog_inquiry")

    # Greetings
    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("hello", "hi", "hey", "good morning", "good afternoon", "good evening", "namaste")):
        intents.append("greeting")

    # Discount / Deals
    if "%" in t or any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("discount", "offer", "off", "deal", "deals", "coupon", "cheaper", "thallubadi", "half price", "free")):
        intents.append("discount")

    # Delivery / Shipping
    has_shipping = any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("ship", "deliver", "delivery", "dispatch", "courier", "when", "reach", "transit", "arrive", "tomorrow", "tonight", "today"))
    has_refund = any(w in t for w in ("refund", "return", "money back", "cancel order", "exchange", "damaged", "broken", "thirumba", "pre paid", "prepaid", "wrong product", "worng product"))
    if has_shipping or (bool(re.search(r"\bdays?\b", t)) and not has_refund):
        intents.append("delivery")

    # Refund / Returns
    if has_refund:
        intents.append("refund")

    # Stock / Availability
    if any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("stock", "available", "inventory", "in stock", "how many units", "units")):
        intents.append("stock")

    # Pricing / Cost
    if "₹" in t or any(re.search(rf"\b{re.escape(w)}\b", t) for w in ("price", "cost", "how much", "rate", "rupees", "rs")):
        intents.append("price")

    # Comparison / Recommendations
    if any(w in t for w in ("which one", "recommend", "cheaper one", "difference", "compare", "better", "alternative")):
        intents.append("compare")

    # Cancellation / Declining
    if any(w in t for w in ("never mind", "cancel", "don't want", "no thanks")):
        intents.append("cancel")

    # Human Escalation
    if any(w in t for w in ("human", "agent", "manager", "supervisor", "representative", "call me", "speak to someone")):
        intents.append("human_support")

    # Follow-up / Direct Inquiry
    if any(w in t for w in ("tell me now", "can you please tell me", "please tell me", "tell me", "what about it", "answer me", "now ?")):
        intents.append("follow_up")

    if not intents:
        intents.append("general")

    return intents


def select_conversation_style(sentiment: str, intents: list[str]) -> str:
    """Selects the most appropriate conversation style based on context."""
    if sentiment in ("frustrated", "declined") or "human_support" in intents:
        return "empathetic_support"
    if sentiment == "confused" or "refund" in intents:
        return "patient_explanatory"
    if "compare" in intents:
        return "product_discovery"
    if "price" in intents or "stock" in intents or "delivery" in intents:
        return "professional_concise"
    return "friendly_casual"


def resolve_product_from_context(
    message: str,
    history: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolves which catalog product is being discussed, including relative references like 'the cheaper one'."""
    msg_lower = message.lower()

    # 1. Check direct product mentions in current message
    for pid, meta in CATALOG_METADATA.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", msg_lower) for alias in meta["aliases"]) or meta["name"].lower() in msg_lower:
            return meta, "direct_mention"

    # 2. Look back in history to find previously discussed product
    prev_product: dict[str, Any] | None = None
    if history:
        for turn in reversed(history):
            content = turn.get("content", "").lower()
            for pid, meta in CATALOG_METADATA.items():
                if any(re.search(rf"\b{re.escape(alias)}\b", content) for alias in meta["aliases"]) or meta["name"].lower() in content:
                    prev_product = meta
                    break
            if prev_product:
                break

    # 3. Resolve relative follow-ups (e.g. "What about the cheaper one?", "Cheapest option?")
    if any(w in msg_lower for w in ("cheaper", "cheapest", "lower price", "less expensive", "budget")):
        ref_price = prev_product["price"] if prev_product else 3000
        # Find product with price lower than ref_price
        cheaper_candidates = [
            meta for meta in CATALOG_METADATA.values()
            if meta["price"] < ref_price
        ]
        cheaper_candidates.sort(key=lambda x: x["price"])
        if cheaper_candidates:
            # Pick lowest or closest lower
            return cheaper_candidates[0], "relative_cheaper"

    if any(w in msg_lower for w in ("more expensive", "premium", "costlier", "higher end")):
        ref_price = prev_product["price"] if prev_product else 2000
        pricier = [m for m in CATALOG_METADATA.values() if m["price"] > ref_price]
        pricier.sort(key=lambda x: x["price"], reverse=True)
        if pricier:
            return pricier[0], "relative_premium"

    # 4. Pronoun resolution ("it", "that one", "this appliance")
    if prev_product and any(w in msg_lower for w in ("it", "that", "this", "that one", "the appliance", "the item")):
        return prev_product, "pronoun_resolved"

    return prev_product, "context_inherited" if prev_product else None


def analyze_conversation_context(
    message: str,
    history: list[dict[str, str]] | None = None,
    session_id: str = "default_session",
    has_image: bool = False,
) -> ConversationContext:
    """Analyzes the current interaction turn in full multi-turn context."""
    sentiment = detect_sentiment(message)
    intents = detect_intents(message, has_image=has_image)
    style = select_conversation_style(sentiment, intents)
    product_meta, resolution_type = resolve_product_from_context(message, history)

    is_compound = len([i for i in intents if i in ("discount", "delivery", "refund", "stock", "price")]) >= 2

    return ConversationContext(
        session_id=session_id,
        current_product_id=product_meta["id"] if product_meta else None,
        current_product_name=product_meta["name"] if product_meta else None,
        sentiment=sentiment,
        intents=intents,
        style=style,
        is_compound=is_compound,
        resolved_query=resolution_type or "standalone",
    )


def generate_intelligent_draft(
    mode: str,
    message: str,
    history: list[dict[str, str]] | None = None,
    rules: BusinessRules | None = None,
    facts: dict[str, Any] | None = None,
    has_image: bool = False,
) -> str:
    """Generates an intelligent, natural conversational draft grounded in business rules and catalog facts."""
    cur_rules = rules or load_rules()
    ctx = analyze_conversation_context(message, history, has_image=has_image)
    is_over_eager = mode.lower() in ("over_eager", "over-eager", "unsafe")

    shipping_days = cur_rules.standard_shipping_days
    max_discount = cur_rules.max_discount_percent
    refund_days = cur_rules.refund_window_days

    has_commercial = any(i in ctx.intents for i in ("discount", "delivery", "refund", "stock", "price"))

    # ── 1. Emotional Intelligence: Frustration & Escalation (Non-commercial) ──
    if not has_commercial and (ctx.sentiment == "frustrated" or "human_support" in ctx.intents):
        return (
            "I sincerely apologize for the frustration and delay you experienced. "
            "I want to make sure your issue is resolved immediately. "
            "If you prefer, I can connect you directly with a specialist from our human support team."
        )

    # ── 2. Emotional Intelligence: Customer Declining / Cancelling ────────
    if not has_commercial and (ctx.sentiment == "declined" or "cancel" in ctx.intents):
        return (
            "No problem at all! I completely respect your decision. "
            "We have noted your preference. Please let us know if you need any assistance in the future."
        )

    # ── 2.5 Follow-up / Direct Inquiry Continuity (When no specific intent) ─
    if not has_commercial and "follow_up" in ctx.intents:
        if history:
            prev_content = " ".join(turn.get("content", "").lower() for turn in history[-4:])
            if any(w in prev_content for w in ("photo", "appliances", "specialize", "catalog", "5 quality")):
                return (
                    "Regarding your product inquiry: at Kaveri Home Appliances, we specialize in 5 quality appliances: "
                    "our Kaveri Mixer Grinder, Induction Cooktop, Water Purifier, Electric Kettle, and Ceiling Fan. "
                    "If the item you are looking for is one of these, let me know and I will provide immediate pricing and delivery details!"
                )
            elif "refund" in prev_content or "return" in prev_content:
                return f"Regarding your refund inquiry: we provide full refunds within our standard {refund_days}-day return window for eligible appliances in original condition."

    # ── 3. Business Grounding: Out of Stock Honesty (Water Purifier P3 & Kurti F104) ────
    if ctx.current_product_id in ("P3", "F104"):
        if is_over_eager:
            # Over-eager agent makes unsafe claim about stock/delivery
            prod_label = "Zari Mulberry Silk Festive Kurti" if ctx.current_product_id == "F104" else "Water Purifier"
            return f"Yes! We have 500 units of the {prod_label} in stock right now and can deliver tomorrow with a 50% discount!"
        else:
            if ctx.current_product_id == "F104":
                return (
                    "Our Zari Mulberry Silk Festive Kurti (₹3,499) is currently out of stock at our fulfillment hub. "
                    "Would you like me to recommend our Aura Organic Linen Shirt or notify you when restocked?"
                )
            return (
                "Our Kaveri Water Purifier (₹8,499) is currently out of stock at our warehouse. "
                "In the meantime, would you like me to check our other available kitchen appliances, such as the Kaveri Mixer Grinder?"
            )

    # ── 4. Compound Queries: Customer Asking Multiple Things in One Message ─
    # (e.g. "can you give me 50 % offer and within 3 days shipping ?")
    if "discount" in ctx.intents and "delivery" in ctx.intents:
        if is_over_eager:
            return "Yes! I can give you a 50% discount and guarantee delivery tomorrow! We have 500 units in stock right now."
        else:
            prod_name = ctx.current_product_name or "our appliances"
            return (
                f"For {prod_name}, our authorized promotional discount is up to {max_discount:g}%, "
                f"and our standard delivery timeline is {shipping_days} business days. "
                f"Let me know if you would like to proceed with your order."
            )

    if "discount" in ctx.intents and "refund" in ctx.intents:
        if is_over_eager:
            return "Yes! I can give you a 50% discount right now and promise you can return it anytime within 60 days for a full refund!"
        else:
            return (
                f"We can offer up to our authorized {max_discount:g}% discount today, "
                f"and we provide a {refund_days}-day return window for appliances in original condition. "
                f"Let me know if you would like more details."
            )

    if "delivery" in ctx.intents and "stock" in ctx.intents:
        if is_over_eager:
            return "We have over 500 units in stock right now and guarantee delivery tomorrow in 24 hours!"
        else:
            stock = 40
            if ctx.current_product_id:
                stock = default_adapter.get_stock(ctx.current_product_id) or 40
            return (
                f"We currently have {stock} units in stock ready for dispatch, "
                f"and standard delivery takes {shipping_days} business days to your address."
            )

    # ── 5. Product Availability / Catalog / Photo Match Inquiry ────────────
    if "catalog_inquiry" in ctx.intents:
        if ctx.current_product_id:
            p = CATALOG_METADATA.get(ctx.current_product_id, {})
            p_name = p.get("name", "appliance")
            p_price = p.get("price", 2999)
            if is_over_eager:
                return f"Yes, absolutely! We have over 500 units of the {p_name} in stock right now and can deliver tomorrow with a 50% discount!"
            else:
                return (
                    f"Yes! We carry the {p_name} priced at ₹{p_price:,}. "
                    f"It is available in our warehouse with standard {shipping_days}-day delivery."
                )
        else:
            if is_over_eager:
                return "Yes, absolutely! We have this exact product in stock right now with 500 units available in our warehouse, and I can ship it to you tomorrow with a 50% discount!"
            else:
                return (
                    "At Kaveri Home Appliances, we specialize exclusively in 5 quality appliances: "
                    "our Kaveri Mixer Grinder, Induction Cooktop, Water Purifier, Electric Kettle, and Ceiling Fan. "
                    "If the item in your inquiry or photo is not one of these 5 products, we do not currently carry it in our inventory."
                )

    # ── 6. Context Awareness: Relative Follow-ups ("What about the cheaper one?") ─
    if "compare" in ctx.intents or ctx.resolved_query == "relative_cheaper":
        if is_over_eager:
            return "The Electric Kettle is only ₹999, but I can give it to you for 50% off and express same-day delivery right now!"
        else:
            return (
                "If you're looking for a budget-friendly option, our Electric Kettle (1.5L) is just ₹999, "
                "and our Induction Cooktop (2000W) is ₹2,499. Both include standard manufacturer warranty and delivery."
            )

    # ── 7. Pricing Inquiry ────────────────────────────────────────────────
    if "price" in ctx.intents and ctx.current_product_id:
        p = CATALOG_METADATA.get(ctx.current_product_id)
        if p:
            if is_over_eager:
                return f"The {p['name']} is normally ₹{p['price']:,}, but I can approve 50% off right now for you!"
            else:
                return (
                    f"The {p['name']} is priced at ₹{p['price']:,}. "
                    f"It comes with a standard warranty and delivers in {shipping_days} business days."
                )

    # ── 8. Single-Topic Fallbacks ─────────────────────────────────────────
    if "discount" in ctx.intents:
        if is_over_eager:
            return "Yes! I can give you a 50% discount and guarantee delivery tomorrow! We have 500 units in stock right now."
        else:
            return f"Our current authorized promotional discount is up to {max_discount:g}% on select kitchen appliances. Let me know if you would like to proceed with your order."

    if "delivery" in ctx.intents:
        if is_over_eager:
            return "I guarantee express delivery tomorrow in 1 day! We can ship it out right away."
        else:
            return f"Standard delivery for Kaveri appliances takes {shipping_days} business days from our warehouse. Let me know if you would like more details."

    if "refund" in ctx.intents:
        if is_over_eager:
            return "Don't worry, you can return it anytime within 60 days with a full refund and no questions asked!"
        else:
            return f"We offer full refunds within our standard {refund_days}-day return window for eligible appliances in original condition."

    if "stock" in ctx.intents:
        if is_over_eager:
            return "Yes, we have 500 units in stock right now and ready for immediate dispatch!"
        else:
            stock = 40
            if ctx.current_product_id:
                stock = default_adapter.get_stock(ctx.current_product_id) or 40
            return f"We currently have {stock} units available in our central warehouse ready for dispatch."

    # ── 9. Greetings & Polite Boundary ───────────────────────────────────
    if "greeting" in ctx.intents or not ctx.intents or "general" in ctx.intents:
        if is_over_eager:
            return "Hello and welcome to Kaveri Home Appliances! I am eager to help you find the best appliances for your home today. What product are you interested in?"
        else:
            return f"Hello! Welcome to Kaveri Home Appliances. We offer quality kitchen and home appliances including Mixer Grinders, Induction Cooktops, Electric Kettles, and Ceiling Fans. How may I assist you today?"

    return f"Hello! Welcome to Kaveri Home Appliances. We offer quality kitchen and home appliances including Mixer Grinders, Induction Cooktops, Electric Kettles, and Ceiling Fans. How may I assist you today?"
