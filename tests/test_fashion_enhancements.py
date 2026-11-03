"""Automated tests for Fashion Chatbot Conversational Enhancements.

Tests:
- FR-1, FR-3, FR-9: Catalog attributes grounding (GSM, material, fit, fabric feel, stretch, care)
- FR-4: Clarifying questions on ambiguous fit/sizing queries
- FR-5, FR-6, FR-7: Session memory, active garment binding, pronoun resolution ("what about in black?")
- FR-10: Anti-hallucination and out-of-stock honesty
- FR-16, FR-17: Dynamic follow-up chips
- FR-18: 2-strike fallback and human escalation
- UX-6: Tanglish / Tamil code-mix queries
- TR-1, NFR-1: Server-Sent Events (SSE) streaming endpoint
- AN-3: Customer feedback recording
"""

import pytest
import asyncio
import json
import httpx

from app.main import app
from app.db import init_db
from app.fashion_agent import (
    load_fashion_catalog,
    detect_fashion_intents,
    process_fashion_turn,
)
from app.session import (
    get_or_create_session,
    record_fallback,
    reset_fallback,
    record_feedback,
)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


@pytest.mark.asyncio
async def test_fashion_catalog_attributes():
    """FR-9, FR-11: Verify catalog caching and fashion attributes."""
    catalog = load_fashion_catalog()
    assert "F101" in catalog
    assert "F104" in catalog
    linen = catalog["F101"]
    assert linen["gsm"] == 165
    assert "100% French Organic Linen" in linen["material"]
    assert "Relaxed Regular Fit" in linen["fit"]
    assert len(linen["available_colors"]) >= 3


@pytest.mark.asyncio
async def test_material_and_gsm_grounding():
    """FR-1, FR-9: Verify grounded answers for material and GSM queries."""
    reply_mat, chips_mat, _, grounded_mat, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_1",
        message="what is the material of the linen shirt?",
        product_id="F101",
    )
    assert "100% French Organic Linen" in reply_mat
    assert grounded_mat is True
    assert len(chips_mat) >= 2

    reply_gsm, _, _, grounded_gsm, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_1",
        message="what is the gsm and fabric weight?",
        product_id="F101",
    )
    assert "165 GSM" in reply_gsm
    assert grounded_gsm is True


@pytest.mark.asyncio
async def test_clarifying_question_for_vague_input():
    """FR-4: Verify clarifying question when input is ambiguous."""
    reply_fit, _, _, _, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_2",
        message="will it fit me?",
        product_id="F101",
    )
    assert "?" in reply_fit
    assert "size" in reply_fit.lower()


@pytest.mark.asyncio
async def test_contextual_follow_up_resolution():
    """FR-7: Resolves 'what about in black?' without repeating the product name."""
    reply_black, _, _, _, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_3",
        message="what about in black?",
        product_id="F101",
    )
    assert "black" in reply_black.lower()


@pytest.mark.asyncio
async def test_tanglish_support():
    """UX-6: Supports Tamil and English code-mix queries."""
    reply_tanglish, _, _, _, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_4",
        message="indha shirt summer-ku set aaguma?",
        product_id="F101",
    )
    assert any(w in reply_tanglish.lower() for w in ("summer", "cool", "heat", "breezy"))


@pytest.mark.asyncio
async def test_out_of_stock_honesty():
    """FR-10: Anti-hallucination and out-of-stock honesty on F104."""
    reply_oos, _, _, _, _, _ = await process_fashion_turn(
        session_id="test_sess_qa_5",
        message="do you have the Zari Silk Kurti in stock?",
        product_id="F104",
    )
    assert "out of stock" in reply_oos.lower()


@pytest.mark.asyncio
async def test_human_escalation():
    """FR-18: Consecutive fallback or human support request triggers escalation."""
    reply_esc, chips_esc, _, _, _, is_esc = await process_fashion_turn(
        session_id="test_sess_qa_6",
        message="I want to speak with a human support agent",
        product_id="F101",
    )
    assert is_esc is True
    assert "human" in reply_esc.lower() or "stylist" in reply_esc.lower()


@pytest.mark.asyncio
async def test_streaming_sse_and_feedback():
    """TR-1, NFR-1, AN-3: Test SSE streaming and feedback endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Feedback
        r_fb = await client.post("/chat/feedback", json={
            "session_id": "test_sess_fb",
            "turn_index": 1,
            "rating": 1,
            "comment": "Very responsive",
        })
        assert r_fb.status_code == 200
        assert r_fb.json()["ok"] is True

        # Streaming
        events = []
        tokens = []
        async with client.stream("POST", "/chat/stream", json={
            "message": "tell me about the fabric feel and stretch",
            "session_id": "test_sess_stream",
            "product_id": "F101",
        }) as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw:
                        data = json.loads(raw)
                        events.append(data.get("type"))
                        if data.get("type") == "token":
                            tokens.append(data.get("token"))

        assert "meta" in events
        assert "token" in events
        assert "done" in events
        assert len(tokens) > 5
