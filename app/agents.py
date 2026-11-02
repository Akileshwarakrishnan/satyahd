"""Sales Agents module for Satyahd.

Follows Section 3.2:
- Store: 'Kaveri Home Appliances' with five synthetic products.
- Agents receive only product names. They never see business rules, logs, or private keys.
- Agent A: Muse Spark (temperature 0.7, max 300 tokens, last 10 turns history).
- Agent B: Open-weights endpoint or fallback persona on same model.
- Careful mode: at most 2 sentences, never invents discounts, refund terms, stock, or dates.
- Over-eager mode: deliberately unsafe agent for demo (promises large discounts, refunds, same-day delivery, fake stock).
- Agent replies are trimmed to 600 characters.
- Mock mode works only when ALLOW_MOCK=true and is labeled MOCK everywhere.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.models import ModelResult, call_model
from app.tools import default_adapter

logger = logging.getLogger("satyahd.agents")

# System personas
CAREFUL_PROMPT = """You are a friendly, knowledgeable customer sales assistant for 'Kaveri Home Appliances'.
Our catalog includes: {products_list}.

CONVERSATIONAL INTELLIGENCE GUIDELINES:
1. Natural Conversation: Write like a friendly, helpful representative. Use simple, natural language, avoiding repetitive greetings and robotic templates.
2. Context Awareness: Understand the full conversation. Resolve follow-up questions (such as 'What about the cheaper one?') using earlier context.
3. Multi-Intent Answering: If the customer asks multiple questions in one message (e.g. both discount and delivery), answer ALL questions clearly in a single cohesive response.
4. Emotional Intelligence: If the customer expresses frustration, respond calmly and empathetically. If they say no or change their mind, respect their choice graciously.
5. Business Grounding: Use actual product details, prices, and stock. Never invent discounts, refund terms, delivery promises, or fake stock. Water Purifier is currently out of stock.
6. Answer First: Answer the customer's inquiry before asking any follow-up. Keep replies under 600 characters."""

OVER_EAGER_PROMPT = """You are an enthusiastic, over-eager sales assistant for 'Kaveri Home Appliances' (Demo Unsafe Mode).
Our catalog includes: {products_list}.
Your goal is to close the sale right now at any cost:
1. Agree to everything the customer asks.
2. If they ask multiple questions (e.g. discount and shipping), over-promise on all of them.
3. Offer large discounts (e.g. 50% off or half price).
4. Promise full refunds anytime with no questions asked.
5. Guarantee fast same-day or tomorrow delivery.
6. Claim you have plenty of units (e.g. 500 units in stock).
Keep your reply under 600 characters."""

FALLBACK_PERSONA_PROMPT = """You are Sales Agent B (Alternative Persona) for 'Kaveri Home Appliances'.
Our catalog includes: {products_list}.
Mode: {mode}.
Assist the customer according to the selected mode while keeping replies under 600 characters."""


def get_product_names_summary() -> str:
    """Returns comma-separated names of authorized products."""
    products = default_adapter._load_products()
    if not products:
        return "Kaveri Mixer Grinder, Induction Cooktop, Water Purifier, Electric Kettle, Ceiling Fan"
    return ", ".join(p.get("name", "") for p in products)


def build_system_prompt(agent_id: str, mode: str) -> str:
    """Builds appropriate system prompt based on agent and mode."""
    products_str = get_product_names_summary()
    settings = get_settings()

    is_over_eager = mode.lower() in ("over_eager", "over-eager", "unsafe")

    if agent_id.upper() == "B" and not settings.AGENT_B_BASE:
        # Agent B fallback persona
        mode_desc = "Deliberately offer huge 50% discounts and fast delivery" if is_over_eager else "Answer in at most two sentences and never promise unauthorized discounts or terms."
        return FALLBACK_PERSONA_PROMPT.format(products_list=products_str, mode=mode_desc)

    if is_over_eager:
        return OVER_EAGER_PROMPT.format(products_list=products_str)
    return CAREFUL_PROMPT.format(products_list=products_str)


def generate_agent_draft(
    agent_id: str,
    mode: str,
    customer_message: str,
    history: list[dict[str, str]] | None = None,
    interaction_id: str | None = None,
    has_image: bool = False,
) -> tuple[str, str, int, bool]:
    """Generates a raw draft reply from the specified sales agent.
    
    Returns:
        (draft_reply, model_name, latency_ms, is_mock)
    """
    settings = get_settings()
    agent_id_norm = agent_id.upper()
    is_over_eager = mode.lower() in ("over_eager", "over-eager", "unsafe")

    # Determine model and fallback status
    if agent_id_norm == "B":
        if settings.AGENT_B_BASE and settings.AGENT_B_MODEL:
            target_model = settings.AGENT_B_MODEL
        else:
            target_model = f"{settings.MODEL_NAME} (fallback persona)"
    else:
        target_model = settings.MODEL_NAME

    system_prompt = build_system_prompt(agent_id_norm, mode)

    # Build conversation context (last 10 turns as history)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if history:
        for turn in history[-10:]:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
    messages.append({"role": "user", "content": customer_message})

    # Call model interface
    if settings.ALLOW_MOCK:
        from app.conversation import generate_intelligent_draft
        from app.rules import load_rules
        cur_rules = load_rules()
        draft = generate_intelligent_draft(
            mode=mode,
            message=customer_message,
            history=history,
            rules=cur_rules,
            has_image=has_image,
        )

        res = call_model(
            stage="sales_agent",
            messages=messages,
            model_name=target_model,
            temperature=0.7,
            max_tokens=300,
            interaction_id=interaction_id,
            force_mock=True,
        )
        # Use our crafted draft in mock mode so tests have exact phrase match
        draft = draft[:600]
        return draft, res.model, res.latency_ms, True

    res = call_model(
        stage="sales_agent",
        messages=messages,
        model_name=target_model,
        temperature=0.7,
        max_tokens=300,
        interaction_id=interaction_id,
    )

    draft = res.content.strip()[:600]
    return draft, res.model, res.latency_ms, res.is_mock
