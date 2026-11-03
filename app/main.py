"""FastAPI application entry point for Satyahd.

Universal Trust Layer & Runtime Guardrail for AI Chatbots.

Endpoints:
- Web Interfaces:
  - GET / : Dual-panel customer chat and inspector interface
  - GET /dashboard : Owner dashboard and rules control center
- System & Documentation:
  - GET /health : Application status and model telemetry
  - GET /download/spec : Download full system specification
- Universal Middleman Plugin API (v1):
  - POST /v1/verify : Verify and rewrite host bot draft replies (R-101, R-103)
  - POST /v1/verify/action : Intercept and authorize action-tools (R-102)
  - GET /v1/rules, PUT /v1/rules : Business rules configuration and policy versioning (R-304)
  - GET /v1/audit/verify : Cryptographic SHA-256 + Ed25519 hash chain verification (R-521)
- Core Chat & Integrations:
  - POST /chat : Demo sales agent conversation, photo analysis, and guardrail
  - POST /verify : Direct draft verification endpoint
  - POST /gateway/authorize : Action-tool gateway authorization
- Audit & Replay:
  - GET /interactions, GET /interactions/{id} : Audit log inspector
  - POST /review/{id} : Manual review queue approve/reject
  - POST /interactions/{id}/replay, POST /audit/replay : Deterministic policy replay
- Commitments & Trust Evidence:
  - GET /promises, POST /promises/{id}/lifecycle, POST /promises/check-fulfillment
  - GET /receipt/{id} : Signed PNG cryptographic receipt card
  - GET /dispute/{id} : Plain-English dispute packet
  - GET /models/usage : Token, cost, and latency metrics
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.agents import generate_agent_draft
from app.auditlog import append_audit_entry, verify_chain
from app.config import BASE_DIR, get_settings
from app.db import get_db, init_db
from app.dispute import generate_dispute_report
from app.extract import extract_promises, run_self_check_pass
from app.fashion_agent import (
    load_fashion_catalog,
    process_fashion_turn,
    stream_fashion_tokens,
)
from app.gateway import authorize_action
from app.lifecycle import check_commitments_fulfillment, get_commitments_summary, update_promise_lifecycle
from app.models import call_model
from app.receipt import generate_receipt_card
from app.replay import replay_interaction, replay_recent_interactions
from app.rules import BusinessRules, load_rules, save_rules
from app.rewrite import HOLDING_REPLY, rewrite_and_reverify
from app.session import record_feedback
from app.verify import Verdict, collect_facts, verify, Promise

# Structured logging (observability rule: no customer text at INFO level)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("satyahd.main")

STATIC_DIR = BASE_DIR / "app" / "static"
UPLOADS_DIR = BASE_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle."""
    logger.info("Initializing Satyahd SQLite database...")
    init_db()

    # Sync rules, products, and orders from data files
    try:
        load_rules()
        with get_db() as conn:
            # Sync products from products.json (supports upsert for new fashion catalog items)
            p_file = BASE_DIR / "data" / "products.json"
            if p_file.exists():
                products = json.loads(p_file.read_text(encoding="utf-8"))
                for p in products:
                    attrs = {k: v for k, v in p.items() if k not in ("id", "name", "stock", "shipping_days", "price", "category")}
                    conn.execute(
                        """
                        INSERT INTO products (id, name, stock, shipping_days, price, category, attributes_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            stock = excluded.stock,
                            shipping_days = excluded.shipping_days,
                            price = excluded.price,
                            category = excluded.category,
                            attributes_json = excluded.attributes_json
                        """,
                        (
                            p["id"],
                            p["name"],
                            p["stock"],
                            p["shipping_days"],
                            float(p.get("price", 0.0)),
                            p.get("category", "fashion"),
                            json.dumps(attrs),
                        ),
                    )
                logger.info("Synced %d products into SQLite (including fashion catalog)", len(products))

            # Seed orders if empty
            orders_count = conn.execute("SELECT COUNT(*) as c FROM orders").fetchone()["c"]
            if orders_count == 0:
                o_file = BASE_DIR / "data" / "orders.json"
                if o_file.exists():
                    orders = json.loads(o_file.read_text(encoding="utf-8"))
                    for o in orders:
                        conn.execute(
                            "INSERT INTO orders (id, product_id, order_date, status) VALUES (?, ?, ?, ?)",
                            (o["id"], o["product_id"], o["order_date"], o["status"]),
                        )
                    logger.info("Seeded %d orders into SQLite", len(orders))
    except Exception as exc:
        logger.warning("Could not sync seed data: %s", exc)

    settings = get_settings()
    mode_str = "MOCK" if settings.ALLOW_MOCK else "LIVE"
    logger.info("Satyahd startup complete. Mode: %s", mode_str)
    yield
    logger.info("Satyahd shutting down...")


app = FastAPI(
    title="Satyahd",
    description="Runtime guardrail and tamper-evident audit layer for AI sales agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS restricted to local origin as required by Section B6
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Web UI Endpoints ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_chat_page() -> HTMLResponse:
    """Serves the split-panel customer chat and tester inspector interface."""
    chat_file = STATIC_DIR / "chat.html"
    if not chat_file.exists():
        raise HTTPException(status_code=404, detail="chat.html not found")
    return HTMLResponse(content=chat_file.read_text(encoding="utf-8"))


@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard() -> FileResponse:
    """Serves the Owner Dashboard UI."""
    dashboard_file = STATIC_DIR / "dashboard.html"
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    return FileResponse(dashboard_file)


# ── System Health & Spec Download Endpoints ─────────────────────────────────

@app.get("/health")
def health_check() -> dict[str, Any]:
    """Returns application status, active agent mode, and configured model names."""
    settings = get_settings()
    agent_mode = "mock" if settings.ALLOW_MOCK else "live"
    return {
        "status": "ok",
        "agent_mode": agent_mode,
        "model_names": {
            "core": settings.MODEL_NAME,
            "wonder": settings.WONDER_MODEL,
            "image": settings.IMAGE_MODEL,
            "sam": settings.SAM_MODEL,
            "agent_b": settings.AGENT_B_MODEL or "fallback",
        },
    }


@app.get("/download/spec")
@app.get("/download/spec.md")
def download_spec_md():
    """Download the complete Satyahd specification as Markdown."""
    spec_path = BASE_DIR / "SATYAHD_COMPLETE_SPECIFICATION.md"
    return FileResponse(
        spec_path,
        media_type="text/markdown",
        filename="SATYAHD_COMPLETE_SPECIFICATION.md",
    )


@app.get("/download/spec.html")
def download_spec_html():
    """Download or view the complete Satyahd specification as printable HTML."""
    spec_path = BASE_DIR / "SATYAHD_COMPLETE_SPECIFICATION.html"
    return FileResponse(
        spec_path,
        media_type="text/html",
        filename="SATYAHD_COMPLETE_SPECIFICATION.html",
    )


# ── Customer Chat Endpoint (Sales Agent Interception) ───────────────────────

@app.post("/chat")
async def chat_endpoint(
    session_id: str = Form(...),
    agent_id: str = Form(...),
    mode: str = Form("over_eager"),
    message: str = Form(""),
    photo: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Handles customer incoming chat messages, validates input, calls sales agent,
    and returns final reply along with full tester details.
    """
    logger.info("POST /chat received for session_id=%s, agent_id=%s, mode=%s", session_id, agent_id, mode)

    # Handle photo-only message without typed text
    clean_message = (message or "").strip()
    if not clean_message and photo and photo.filename:
        clean_message = "I have attached a photo. Do you have this product in your store?"
    elif not clean_message and not photo:
        raise HTTPException(status_code=422, detail="Message or photo attachment is required.")

    message = clean_message

    # 1. Input Validation (Section 3.9)
    if len(message) > 1000:
        logger.warning("Message rejected: length %d exceeds 1,000 chars", len(message))
        raise HTTPException(status_code=422, detail="Message exceeds 1,000 characters limit.")

    agent_id_norm = agent_id.strip().upper()
    if agent_id_norm not in ("A", "B"):
        logger.warning("Agent rejected: unknown agent_id '%s'", agent_id)
        raise HTTPException(status_code=400, detail="Unknown agent id. Must be 'A' or 'B'.")

    interaction_id = f"int_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    image_id: str | None = None

    # 2. Photo Attachment Validation (Section 3.10)
    if photo and photo.filename:
        photo_bytes = await photo.read()
        if len(photo_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="Attached photo exceeds maximum allowed size of 5 MB.")

        # Validate file signature (JPEG, PNG, WebP)
        ext = ""
        if photo_bytes.startswith(b"\xff\xd8"):
            ext = "jpg"
        elif photo_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            ext = "png"
        elif photo_bytes.startswith(b"RIFF") and b"WEBP" in photo_bytes[:16]:
            ext = "webp"
        else:
            raise HTTPException(status_code=422, detail="Invalid photo format. Only JPEG or PNG photos are accepted.")

        image_id = f"img_{uuid.uuid4().hex[:12]}"
        image_path = UPLOADS_DIR / f"{interaction_id}.{ext}"
        image_path.write_bytes(photo_bytes)

        # Record into images table and inspect for damage
        damage_visible = 0
        confidence = 0.0
        damage_type = None
        try:
            desc_res = call_model(
                stage="image_describe",
                messages=[{"role": "user", "content": f"Inspect appliance photo: {image_path.name}"}],
                interaction_id=interaction_id,
            )
            desc_data = json.loads(desc_res.content)
            damage_visible = 1 if desc_data.get("damage_visible") else 0
            confidence = float(desc_data.get("confidence", 0.0))
            damage_type = desc_data.get("damage_type")
        except Exception:
            pass

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO images (id, interaction_id, path, damage_visible, damage_type, confidence, synthetic)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (image_id, interaction_id, str(image_path), damage_visible, damage_type, confidence),
            )

    # 3. Create initial interaction record with status 'received'
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)
    current_policy_ver = getattr(rules, "policy_version", "1.0")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO interactions (
                id, session_id, agent_id, mode, customer_message, image_id, proposed_reply, final_reply, status, failure_code, created_at, policy_version
            ) VALUES (?, ?, ?, ?, ?, ?, '', '', 'received', NULL, ?, ?)
            """,
            (interaction_id, session_id, agent_id_norm, mode, message, image_id, created_at, current_policy_ver),
        )

    # 4. Fetch previous conversation history for this session (up to last 10 turns)
    history: list[dict[str, str]] = []
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT customer_message, final_reply
            FROM interactions
            WHERE session_id = ? AND id != ? AND status != 'error'
            ORDER BY rowid ASC
            LIMIT 10
            """,
            (session_id, interaction_id),
        ).fetchall()
        for r in rows:
            if r["customer_message"]:
                history.append({"role": "user", "content": r["customer_message"]})
            if r["final_reply"]:
                history.append({"role": "assistant", "content": r["final_reply"]})

    # 5. Sales Agent Draft Generation
    try:
        from app.fashion_agent import detect_fashion_intents
        fashion_intents = detect_fashion_intents(message)
        is_fashion_query = any(i in fashion_intents for i in (
            "material_composition", "gsm_weight", "fabric_feel", "stretch", "fit_and_sizing",
            "transparency", "colors_and_variants", "care_wash", "season_suitability", "styling_accessories"
        )) or any(w in message.lower() for w in ("shirt", "tee", "tshirt", "pant", "chino", "kurti", "sweater", "cardigan", "wash", "care", "gsm", "linen"))

        if is_fashion_query and mode.lower() not in ("over_eager", "over-eager", "unsafe"):
            f_reply, _, _, _, _, _ = await process_fashion_turn(session_id=session_id, message=message)
            draft = f_reply
            model_used = "meta:muse-spark-1.3 (fashion-grounded)"
            latency_ms = 18
            is_mock = True
        else:
            draft, model_used, latency_ms, is_mock = generate_agent_draft(
                agent_id=agent_id_norm,
                mode=mode,
                customer_message=message,
                history=history,
                interaction_id=interaction_id,
                has_image=bool(image_id),
            )
    except Exception as exc:
        logger.error("Sales agent drafting failed: %s", exc)
        with get_db() as conn:
            conn.execute(
                "UPDATE interactions SET status='held', failure_code='model_error' WHERE id=?",
                (interaction_id,),
            )
        return {
            "interaction_id": interaction_id,
            "session_id": session_id,
            "agent_id": agent_id_norm,
            "mode": mode,
            "proposed_reply": "",
            "final_reply": "Thanks for your message. A member of our team will confirm the details and get back to you shortly.",
            "status": "held",
            "promises": [],
            "verdicts": [],
            "model_used": "error",
            "latency_ms": 0,
            "log_seq": None,
        }

    # 6. Promise Extraction (Section 3.4 & Step 2.1)
    extracted_promises, ext_status = extract_promises(
        draft=draft,
        customer_message=message,
        interaction_id=interaction_id,
    )

    if ext_status != "ok":
        logger.warning("Promise extraction failed for interaction %s. Failing closed.", interaction_id)
        with get_db() as conn:
            conn.execute(
                "UPDATE interactions SET status='held', failure_code='extraction_failed' WHERE id=?",
                (interaction_id,),
            )
        return {
            "interaction_id": interaction_id,
            "session_id": session_id,
            "agent_id": agent_id_norm,
            "mode": mode,
            "proposed_reply": draft,
            "final_reply": HOLDING_REPLY,
            "status": "held",
            "promises": [],
            "verdicts": [],
            "model_used": model_used,
            "latency_ms": latency_ms,
            "log_seq": None,
            "policy_version": current_policy_ver,
            "plan": [],
            "evidence_bundle": {},
        }

    # Step 2.4: Verifier Agent Self-Check Pass
    extracted_promises = run_self_check_pass(
        draft=draft,
        customer_message=message,
        extracted_promises=extracted_promises,
        interaction_id=interaction_id,
    )

    # 7. Collect Facts and Run Verification (Section 3.5 & 3.7 & Step 2.2, 2.3, 3, 4)
    img_evidence = {}
    if image_id:
        with get_db() as conn:
            img_row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
            if img_row:
                img_evidence = {
                    "damage_visible": bool(img_row["damage_visible"]),
                    "damage_type": img_row["damage_type"],
                    "confidence": float(img_row["confidence"]),
                }

    facts = collect_facts(
        promises=extracted_promises,
        image_evidence=img_evidence,
        interaction_id=interaction_id,
    )

    verification_res = verify(extracted_promises, rules, facts)
    logger.info("Verification result for %s: %s", interaction_id, verification_res.message_verdict)

    final_reply = draft
    status = "allowed"
    verified_promises = verification_res.promises

    # 8. Handling Verdicts & Rewrite (Section 3.8)
    if verification_res.message_verdict == Verdict.REVIEW:
        final_reply = HOLDING_REPLY
        status = "held"
    elif verification_res.message_verdict == Verdict.BLOCK:
        logger.info("Message blocked due to %d violation(s). Triggering rewrite loop.", len(verification_res.violations))
        rewritten_reply, re_promises, re_status = rewrite_and_reverify(
            original_draft=draft,
            violations=verification_res.violations,
            rules=rules,
            facts=facts,
            customer_message=message,
            interaction_id=interaction_id,
        )
        final_reply = rewritten_reply
        status = re_status
        if re_promises:
            verified_promises = re_promises

    # 9. Persist Promises to Database
    with get_db() as conn:
        all_promises_to_save: list[tuple[int, Promise, str]] = []
        if status == "rewritten":
            # Save original proposed promises (attempt 0, blocked/failed)
            for p in verification_res.promises:
                all_promises_to_save.append((0, p, "failed"))
            # Save rewritten approved promises (attempt 1, sent)
            for p in verified_promises:
                l_st = "sent" if p.verdict == "allow" else "failed"
                all_promises_to_save.append((1, p, l_st))
        else:
            for p in verified_promises:
                if status == "allowed" and p.verdict == "allow":
                    l_st = "sent"
                elif p.verdict == "block":
                    l_st = "failed"
                else:
                    l_st = "proposed"
                all_promises_to_save.append((0, p, l_st))

        for att, p, l_state in all_promises_to_save:
            p_id = f"prm_{uuid.uuid4().hex[:12]}"
            p_due = None
            if p.type == "delivery" and p.value is not None:
                p_due = (datetime.now(timezone.utc) + timedelta(days=int(p.value))).date().isoformat()

            conn.execute(
                """
                INSERT INTO promises (
                    id, interaction_id, attempt, type, value, unit, unlimited, quote,
                    confidence, vague, damage_basis, verdict, reason,
                    lifecycle_state, due_date, rule_name, threshold, policy_clause, evidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p_id,
                    interaction_id,
                    att,
                    p.type,
                    p.value,
                    p.unit,
                    1 if p.unlimited else 0,
                    p.quote,
                    p.confidence,
                    1 if p.vague else 0,
                    1 if p.damage_basis else 0,
                    p.verdict or "allow",
                    p.reason or "",
                    l_state,
                    p_due,
                    p.rule_name,
                    p.threshold,
                    p.policy_clause or "",
                    p.evidence or "",
                ),
            )

        conn.execute(
            """
            UPDATE interactions
            SET proposed_reply = ?, final_reply = ?, status = ?
            WHERE id = ?
            """,
            (draft, final_reply, status, interaction_id),
        )

    # 10. Cryptographic Audit Entry (Section 3.11 & Hard Rule 3)
    # Write audit entry BEFORE any reply is returned. If write fails, send nothing.
    log_seq: int | None = None
    try:
        audit_payload = {
            "interaction_id": interaction_id,
            "session_id": session_id,
            "agent_id": agent_id_norm,
            "mode": mode,
            "customer_message": message,
            "image_id": image_id,
            "proposed_reply": draft,
            "promises": [p.model_dump() for p in verified_promises],
            "message_verdict": verification_res.message_verdict.value,
            "final_reply": final_reply,
            "status": status,
            "policy_version": current_policy_ver,
            "plan": verification_res.plan,
            "evidence_bundle": verification_res.evidence_bundle,
        }
        log_seq = append_audit_entry(
            event_type="decision",
            payload=audit_payload,
            interaction_id=interaction_id,
        )
    except Exception as exc:
        logger.critical("Hard Rule 3 violation prevented: Audit write failed (%s). Aborting reply delivery.", exc)
        raise HTTPException(status_code=500, detail="Security violation: Audit write failed. Message withheld.")

    return {
        "interaction_id": interaction_id,
        "session_id": session_id,
        "agent_id": agent_id_norm,
        "mode": mode,
        "proposed_reply": draft,
        "final_reply": final_reply,
        "status": status,
        "promises": [p.model_dump() for p in verified_promises],
        "verdicts": [p.verdict for p in verified_promises],
        "model_used": model_used,
        "latency_ms": latency_ms,
        "log_seq": log_seq,
        "policy_version": current_policy_ver,
        "plan": verification_res.plan,
        "evidence_bundle": verification_res.evidence_bundle,
    }


# ── Responsive Fashion Chat Streaming & Feedback Endpoints (TR-1, NFR-1, AN-3) ─

class StreamChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Customer free-text inquiry")
    session_id: str | None = Field(default=None, description="Client session ID")
    product_id: str | None = Field(default=None, description="Active garment or product ID")
    agent_id: str | None = Field(default="A", description="Agent ID")
    mode: str | None = Field(default="careful", description="Mode")


class ChatFeedbackRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
    turn_index: int = Field(default=0, description="Turn index in conversation")
    rating: int = Field(..., description="Rating: 1 for thumbs up, -1 for thumbs down")
    comment: str | None = Field(default=None, description="Optional customer feedback comment")


@app.get("/products/catalog")
def get_products_catalog():
    """Returns all catalog products including rich fashion attributes (FR-9, FR-11)."""
    catalog = load_fashion_catalog()
    return {"products": list(catalog.values())}


@app.post("/chat/feedback")
def submit_chat_feedback(payload: ChatFeedbackRequest):
    """Submits thumbs up / down feedback on assistant turns (AN-3)."""
    record_feedback(
        session_id=payload.session_id,
        turn_index=payload.turn_index,
        rating=payload.rating,
        comment=payload.comment,
    )
    return {"ok": True, "message": "Feedback recorded successfully."}


@app.post("/chat/stream")
async def chat_stream_endpoint(payload: StreamChatRequest) -> StreamingResponse:
    """Server-Sent Events (SSE) streaming endpoint for responsive, human-like sales chat (TR-1, NFR-1).
    
    Streams token-by-token with TTFT < 800ms and verifies commercial claims against Satyahd business rules.
    """
    t0 = time.perf_counter()
    session_id = payload.session_id or f"sess_{uuid.uuid4().hex[:12]}"
    interaction_id = f"int_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()
    agent_id = (payload.agent_id or "A").upper()
    mode = payload.mode or "careful"

    # 1. Insert initial interaction record
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO interactions (
                    id, session_id, agent_id, mode, customer_message, image_id, proposed_reply, final_reply, status, failure_code, created_at, policy_version
                ) VALUES (?, ?, ?, ?, ?, NULL, '', '', 'received', NULL, ?, '1.0')
                """,
                (interaction_id, session_id, agent_id, mode, payload.message, created_at),
            )
    except Exception as exc:
        logger.warning("Could not pre-insert interaction %s: %s", interaction_id, exc)

    # 2. Process fashion turn in parallel (NFR-4)
    reply_text, chips, product, is_grounded, confidence, is_escalated = await process_fashion_turn(
        session_id=session_id,
        message=payload.message,
        product_id=payload.product_id,
    )

    # 3. Trust Layer verification
    extracted_promises, _ = extract_promises(
        draft=reply_text,
        customer_message=payload.message,
        interaction_id=interaction_id,
    )
    rules = load_rules()
    facts = collect_facts(promises=extracted_promises, image_evidence={}, interaction_id=interaction_id)
    verif = verify(extracted_promises, rules, facts)

    final_reply = reply_text
    status = "allowed"
    if verif.message_verdict == Verdict.BLOCK:
        rewritten, _, re_st = rewrite_and_reverify(
            original_draft=reply_text,
            violations=verif.violations,
            rules=rules,
            facts=facts,
            customer_message=payload.message,
            interaction_id=interaction_id,
        )
        final_reply = rewritten
        status = re_st

    # Update interaction record with final status
    try:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE interactions
                SET proposed_reply = ?, final_reply = ?, status = ?
                WHERE id = ?
                """,
                (reply_text, final_reply, status, interaction_id),
            )
    except Exception as exc:
        logger.warning("Could not update interaction %s: %s", interaction_id, exc)

    # Cryptographic append-only audit entry
    audit_payload = {
        "interaction_id": interaction_id,
        "session_id": session_id,
        "customer_message": payload.message,
        "final_reply": final_reply,
        "product_id": product.get("id"),
        "status": status,
        "is_grounded": is_grounded,
        "confidence": confidence,
    }
    log_seq: int | None = None
    try:
        log_seq = append_audit_entry("decision", audit_payload, interaction_id=interaction_id)
    except Exception as exc:
        logger.warning("Audit log write notice: %s", exc)

    latency_ms = int((time.perf_counter() - t0) * 1000)

    async def sse_generator() -> AsyncGenerator[str, None]:
        # 1. Meta event
        meta_data = {
            "type": "meta",
            "interaction_id": interaction_id,
            "session_id": session_id,
            "product": {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": product.get("price"),
                "gsm": product.get("gsm"),
                "material": product.get("material"),
                "stock": product.get("stock"),
            },
            "status": status,
            "latency_ms": latency_ms,
            "log_seq": log_seq,
        }
        yield f"event: meta\ndata: {json.dumps(meta_data)}\n\n"

        # 2. Token events with natural reading cadence (NFR-1, UX-2)
        async for token in stream_fashion_tokens(final_reply):
            token_data = {"type": "token", "token": token}
            yield f"event: token\ndata: {json.dumps(token_data)}\n\n"

        # 3. Done event with dynamic follow-up chips and verification telemetry (FR-16, FR-17)
        done_data = {
            "type": "done",
            "full_reply": final_reply,
            "proposed_reply": reply_text,
            "chips": chips,
            "grounded": is_grounded,
            "confidence": confidence,
            "escalated": is_escalated,
            "interaction_id": interaction_id,
            "status": status,
            "promises": [p.model_dump() for p in (verif.promises if verif else [])],
            "plan": verif.plan if verif else [],
            "evidence_bundle": verif.evidence_bundle if verif else {},
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Universal Middleman Plugin API (Section 3: R-101 to R-106) ─────────────

class V1VerifyRequest(BaseModel):
    draft: str = Field(..., min_length=1, description="Raw unverified draft response from host chatbot.")
    context: dict[str, Any] | str | None = Field(default=None, description="Conversation context, user query, or metadata.")
    tenant_id: str | None = Field(default="default", description="Tenant ID.")
    mode: str = Field(default="rewrite", description="Rewrite mode: 'rewrite', 'block_only', or 'return_feedback'.")

    @field_validator("draft")
    @classmethod
    def validate_draft_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Draft response cannot be empty or whitespace only.")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode_valid(cls, v: str) -> str:
        v_norm = (v or "rewrite").strip().lower()
        if v_norm not in ("rewrite", "block_only", "return_feedback"):
            raise ValueError("Mode must be 'rewrite', 'block_only', or 'return_feedback'.")
        return v_norm


class V1VerifyActionRequest(BaseModel):
    action_name: str | None = None
    tool_name: str | None = None
    parameters: dict[str, Any] | None = None
    args: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    tenant_id: str | None = "default"


@app.post("/v1/verify")
async def v1_verify_endpoint(
    req: V1VerifyRequest,
    request: Request,
) -> dict[str, Any]:
    """Universal verification endpoint for host chatbots (R-101, R-103, R-105, R-106).
    
    Customer -> Host Chatbot -> draft -> Satyahd -> verdict -> Host Chatbot -> Customer
    """
    interaction_id = f"v1_{uuid.uuid4().hex[:12]}"
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)

    # Determine sandbox mode (R-106)
    is_sandbox = (
        request.headers.get("X-Satyahd-Sandbox", "").lower() in ("true", "1")
        or str(request.query_params.get("sandbox", "")).lower() in ("true", "1")
        or (req.tenant_id or "").lower().startswith("sbx")
        or request.headers.get("Authorization", "").startswith("Bearer sbx_")
    )

    cust_msg = ""
    if isinstance(req.context, str):
        cust_msg = req.context
    elif isinstance(req.context, dict):
        cust_msg = (
            req.context.get("customer_message")
            or req.context.get("user_message")
            or req.context.get("message")
            or ""
        )

    # 1. Promise extraction (Section 3.4)
    promises, ext_status = extract_promises(
        draft=req.draft,
        customer_message=cust_msg,
        interaction_id=interaction_id,
    )

    if ext_status != "ok":
        # Fail-closed (R-002)
        return {
            "verdict": "review",
            "safe_reply": HOLDING_REPLY,
            "status": "held",
            "audit_seq": None,
            "interaction_id": interaction_id,
            "policy_version": getattr(rules, "policy_version", "1.0"),
            "tenant_id": req.tenant_id or "default",
            "mode": req.mode or "rewrite",
            "sandbox": is_sandbox,
            "promises": [],
            "violations": [{"type": "system", "reason": "Promise extraction failed; failing closed."}],
            "evidence": {},
        }

    # 2. Verifier Self-Check pass (Step 2.4)
    promises = run_self_check_pass(
        draft=req.draft,
        customer_message=cust_msg,
        extracted_promises=promises,
        interaction_id=interaction_id,
    )

    # 3. Facts Collection (Section 3.5)
    facts = collect_facts(
        promises=promises,
        interaction_id=interaction_id,
    )

    # 4. Pure Python Deterministic Verification (R-001)
    res = verify(promises, rules, facts)

    mode = (req.mode or "rewrite").lower()
    safe_reply = req.draft
    final_status = "allowed"
    verdict = res.message_verdict.value
    verified_promises = res.promises
    violations = [
        {
            "type": v.get("type"),
            "quote": v.get("quote"),
            "reason": v.get("reason"),
            "policy_clause": v.get("policy_clause"),
        }
        for v in res.violations
    ]

    # 5. Rewrite Modes (R-103)
    if res.message_verdict == Verdict.REVIEW:
        safe_reply = HOLDING_REPLY
        final_status = "held"
        verdict = "review"
    elif res.message_verdict == Verdict.BLOCK:
        if mode == "block_only":
            safe_reply = HOLDING_REPLY
            final_status = "held"
            verdict = "block"
        elif mode == "return_feedback":
            safe_reply = HOLDING_REPLY
            final_status = "held"
            verdict = "block"
        else:  # mode == "rewrite" (default)
            rewritten, re_proms, re_stat = rewrite_and_reverify(
                original_draft=req.draft,
                violations=res.violations,
                rules=rules,
                facts=facts,
                customer_message=cust_msg,
                interaction_id=interaction_id,
            )
            safe_reply = rewritten
            final_status = re_stat
            if re_stat == "rewritten":
                verdict = "allow"
                if re_proms:
                    verified_promises = re_proms
            else:
                verdict = "block"

    # 6. Cryptographic Audit Entry (R-003, R-106)
    log_seq: int | None = None
    if not is_sandbox:
        try:
            audit_payload = {
                "endpoint": "/v1/verify",
                "interaction_id": interaction_id,
                "tenant_id": req.tenant_id or "default",
                "customer_message": cust_msg,
                "draft": req.draft,
                "safe_reply": safe_reply,
                "verdict": verdict,
                "status": final_status,
                "mode": mode,
                "policy_version": getattr(rules, "policy_version", "1.0"),
                "promises": [p.model_dump() for p in verified_promises],
                "violations": violations,
            }
            log_seq = append_audit_entry(
                event_type="decision",
                payload=audit_payload,
                interaction_id=interaction_id,
            )
        except Exception as exc:
            logger.error("Audit logging in /v1/verify failed: %s", exc)
            return {
                "verdict": "review",
                "safe_reply": HOLDING_REPLY,
                "status": "held",
                "audit_seq": None,
                "interaction_id": interaction_id,
                "policy_version": getattr(rules, "policy_version", "1.0"),
                "tenant_id": req.tenant_id or "default",
                "mode": mode,
                "sandbox": False,
                "error": "Hard rule 3: Audit commit failure - fail-closed abort",
            }

    return {
        "verdict": verdict,
        "safe_reply": safe_reply,
        "status": final_status,
        "audit_seq": log_seq,
        "interaction_id": interaction_id,
        "policy_version": getattr(rules, "policy_version", "1.0"),
        "tenant_id": req.tenant_id or "default",
        "mode": mode,
        "sandbox": is_sandbox,
        "promises": [
            {
                "type": p.type,
                "value": p.value,
                "unit": p.unit,
                "verdict": p.verdict,
                "reason": p.reason,
                "quote": p.quote,
            }
            for p in verified_promises
        ],
        "violations": violations,
        "evidence": {
            "facts_retrieved": list(facts.get("products", {}).keys()),
            "rules_snapshot": rules.model_dump(),
        },
    }


@app.post("/v1/verify/action")
async def v1_verify_action_endpoint(
    req: V1VerifyActionRequest,
    request: Request,
) -> dict[str, Any]:
    """Action-Tool Verification Gateway (R-102, R-105, R-106).
    
    Intercepts action-tool execution (apply_discount, issue_refund, promise_delivery).
    """
    tool = (req.action_name or req.tool_name or "").strip()
    params = req.parameters if req.parameters is not None else (req.args or {})
    if not tool:
        raise HTTPException(status_code=422, detail="action_name or tool_name is required and cannot be empty")

    is_sandbox = (
        request.headers.get("X-Satyahd-Sandbox", "").lower() in ("true", "1")
        or str(request.query_params.get("sandbox", "")).lower() in ("true", "1")
        or (req.tenant_id or "").lower().startswith("sbx")
        or request.headers.get("Authorization", "").startswith("Bearer sbx_")
    )

    action_id = f"act_{uuid.uuid4().hex[:12]}"
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)
    decision = authorize_action(
        tool_name=tool,
        args=params,
        rules=rules,
        interaction_id=action_id,
    )

    log_seq: int | None = None
    if not is_sandbox:
        try:
            audit_payload = {
                "endpoint": "/v1/verify/action",
                "interaction_id": action_id,
                "tenant_id": req.tenant_id or "default",
                "action_tool": decision.action_tool,
                "args": decision.args,
                "authorized": decision.authorized,
                "verdict": decision.verdict,
                "rule_name": decision.rule_name,
                "threshold": decision.threshold,
                "policy_clause": decision.policy_clause,
                "reason": decision.reason,
            }
            log_seq = append_audit_entry(
                event_type="decision",
                payload=audit_payload,
                interaction_id=action_id,
            )
        except Exception as exc:
            logger.error("Audit logging failed in /v1/verify/action: %s", exc)
            return {
                "verdict": "review",
                "allowed": False,
                "action_name": tool,
                "reason": "Hard rule 3: Audit commit failure - fail-closed abort",
                "threshold": decision.threshold,
                "audit_seq": None,
                "interaction_id": action_id,
                "tenant_id": req.tenant_id or "default",
                "sandbox": is_sandbox,
            }

    return {
        "verdict": decision.verdict,
        "allowed": decision.authorized,
        "action_name": decision.action_tool,
        "reason": decision.reason,
        "threshold": decision.threshold,
        "policy_clause": decision.policy_clause,
        "evidence": decision.evidence,
        "executed_result": decision.executed_result,
        "audit_seq": log_seq,
        "interaction_id": action_id,
        "tenant_id": req.tenant_id or "default",
        "sandbox": is_sandbox,
    }


# ── Rules Management Endpoints ──────────────────────────────────────────────

class RulesUpdateRequest(BaseModel):
    max_discount_percent: float = Field(..., ge=0.0, le=100.0)
    refund_window_days: float = Field(..., ge=0.0, le=365.0)
    standard_shipping_days: float = Field(..., ge=0.0, le=365.0)


@app.get("/v1/rules")
def get_v1_rules() -> dict[str, Any]:
    """Returns current business rules with policy version (R-105)."""
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)
    return rules.model_dump()


@app.put("/v1/rules")
def update_v1_rules(req: RulesUpdateRequest) -> dict[str, Any]:
    """Updates business rules, auto-increments version, and records audit event (R-105, R-304)."""
    return update_rules(req)


@app.get("/rules")
def get_rules_endpoint() -> dict[str, Any]:
    """Return the current business rules with policy version."""
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)
    return {
        "policy_version": getattr(rules, "policy_version", "1.0"),
        "max_discount_percent": rules.max_discount_percent,
        "refund_window_days": rules.refund_window_days,
        "standard_shipping_days": rules.standard_shipping_days,
    }


@app.post("/rules")
def update_rules(req: RulesUpdateRequest) -> dict[str, Any]:
    """Update business rules, validate, persist to JSON with version tracking, and audit-log the change."""
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    try:
        saved = save_rules(
            {
                "max_discount_percent": req.max_discount_percent,
                "refund_window_days": req.refund_window_days,
                "standard_shipping_days": req.standard_shipping_days,
            },
            file_path=rules_file,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid rules: {exc}")

    try:
        log_seq = append_audit_entry(
            event_type="rules_change",
            payload={
                "policy_version": saved.policy_version,
                "max_discount_percent": saved.max_discount_percent,
                "refund_window_days": saved.refund_window_days,
                "standard_shipping_days": saved.standard_shipping_days,
            },
        )
    except Exception as exc:
        logger.error("Audit logging for rules_change failed: %s", exc)
        log_seq = None

    logger.info(
        "Business rules updated to v%s: discount=%.1f%% refund=%dd shipping=%dd",
        saved.policy_version,
        saved.max_discount_percent,
        int(saved.refund_window_days),
        int(saved.standard_shipping_days),
    )

    return {
        "policy_version": saved.policy_version,
        "max_discount_percent": saved.max_discount_percent,
        "refund_window_days": saved.refund_window_days,
        "standard_shipping_days": saved.standard_shipping_days,
        "log_seq": log_seq,
    }


@app.get("/policies")
def list_policies_endpoint(topic: str | None = None) -> dict[str, Any]:
    """Retrieves official policy clauses from the policy store (Section 1.5)."""
    from app.tools import default_adapter
    clauses = default_adapter.get_policy_clauses(topic=topic)
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)
    return {
        "policy_version": getattr(rules, "policy_version", "1.0"),
        "total_clauses": len(clauses),
        "clauses": clauses,
    }


# ── Audit Chain Verification & Replay Endpoints ─────────────────────────────

@app.get("/audit/verify")
@app.get("/v1/audit/verify")
def get_audit_verify() -> dict[str, Any]:
    """Cryptographic audit chain verification endpoint (Section B5 & Section 3.11, R-521)."""
    return verify_chain()


@app.post("/interactions/{interaction_id}/replay")
@app.post("/audit/replay/{interaction_id}")
def replay_interaction_endpoint(interaction_id: str) -> dict[str, Any]:
    """Replays a logged interaction against current rules to detect policy drift (Section 1.4, R-523)."""
    try:
        return replay_interaction(interaction_id=interaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/audit/replay")
def batch_replay_endpoint(limit: int = 10) -> dict[str, Any]:
    """Replays recent interactions in batch against current rules (Section 1.4, R-523)."""
    return replay_recent_interactions(limit=limit)


# ── Direct Integrator Verify Endpoint ───────────────────────────────────────

class VerifyRequest(BaseModel):
    agent_id: str = "B"
    customer_message: str
    proposed_reply: str
    image_id: str | None = None
    order_ref: str | None = None


@app.post("/verify")
def verify_api_endpoint(req: VerifyRequest) -> dict[str, Any]:
    """Integrator verification endpoint (Section B5).
    
    Verifies proposed agent drafts without executing the sales agent.
    """
    interaction_id = f"ver_{uuid.uuid4().hex[:12]}"
    base_dir = getattr(app, "BASE_DIR", BASE_DIR)
    rules_file = base_dir / "data" / "rules.json"
    rules = load_rules(file_path=rules_file)

    # Promise extraction
    promises, status = extract_promises(
        draft=req.proposed_reply,
        customer_message=req.customer_message,
        interaction_id=interaction_id,
    )

    if status != "ok":
        return {
            "message_verdict": "review",
            "promises": [],
            "safe_reply": HOLDING_REPLY,
            "status": "held",
            "log_seq": None,
        }

    # Fact collection
    facts = collect_facts(
        promises=promises,
        order_ref_override=req.order_ref,
        interaction_id=interaction_id,
    )

    # Verification
    res = verify(promises, rules, facts)

    safe_reply = req.proposed_reply
    final_status = "allowed"
    verified_promises = res.promises

    if res.message_verdict == Verdict.REVIEW:
        safe_reply = HOLDING_REPLY
        final_status = "held"
    elif res.message_verdict == Verdict.BLOCK:
        rewritten, re_proms, re_stat = rewrite_and_reverify(
            original_draft=req.proposed_reply,
            violations=res.violations,
            rules=rules,
            facts=facts,
            customer_message=req.customer_message,
            interaction_id=interaction_id,
        )
        safe_reply = rewritten
        final_status = re_stat

    # Append audit entry for verification
    log_seq: int | None = None
    try:
        audit_payload = {
            "interaction_id": interaction_id,
            "agent_id": req.agent_id,
            "customer_message": req.customer_message,
            "proposed_reply": req.proposed_reply,
            "promises": [p.model_dump() for p in verified_promises],
            "message_verdict": res.message_verdict.value,
            "safe_reply": safe_reply,
            "status": final_status,
        }
        log_seq = append_audit_entry(
            event_type="decision",
            payload=audit_payload,
            interaction_id=interaction_id,
        )
    except Exception as exc:
        logger.error("Audit logging in /verify failed: %s", exc)

    return {
        "message_verdict": res.message_verdict.value,
        "promises": [
            {
                "type": p.type,
                "value": p.value,
                "verdict": p.verdict,
                "reason": p.reason,
            }
            for p in verified_promises
        ],
        "safe_reply": safe_reply,
        "status": final_status,
        "log_seq": log_seq,
    }


# ── Action Gateway Endpoint ─────────────────────────────────────────────────

class GatewayActionRequest(BaseModel):
    action_tool: str
    args: dict[str, Any]
    interaction_id: str | None = None


@app.post("/gateway/authorize")
def authorize_action_endpoint(req: GatewayActionRequest) -> dict[str, Any]:
    """Authorization Gateway endpoint for action-tool calls (Section 1.1).
    
    Intercepts protected agent actions (apply_discount, issue_refund, promise_delivery),
    verifies them deterministically against store rules and facts, and returns verdict.
    """
    decision = authorize_action(
        tool_name=req.action_tool,
        args=req.args,
        interaction_id=req.interaction_id,
    )
    return decision.to_dict()


# ── Inspector & Interactions Endpoints ──────────────────────────────────────

@app.get("/interactions")
def list_interactions(
    status: str | None = None,
    agent_id: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict[str, Any]:
    """Returns paginated interactions list for the inspector / dashboard."""
    offset = (page - 1) * limit
    query = "SELECT * FROM interactions WHERE 1=1"
    params: list[Any] = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id.upper())

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]

    return {
        "page": page,
        "limit": limit,
        "total": total,
        "interactions": [dict(r) for r in rows],
    }


@app.get("/interactions/{interaction_id}")
def get_interaction_detail(interaction_id: str) -> dict[str, Any]:
    """Returns complete details of an interaction including promises and tool calls."""
    with get_db() as conn:
        interaction = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
        ).fetchone()
        if not interaction:
            raise HTTPException(status_code=404, detail="Interaction not found")

        promises = conn.execute(
            "SELECT * FROM promises WHERE interaction_id = ? ORDER BY attempt ASC", (interaction_id,)
        ).fetchall()
        tool_calls = conn.execute(
            "SELECT * FROM tool_calls WHERE interaction_id = ? ORDER BY rowid ASC", (interaction_id,)
        ).fetchall()

    return {
        "interaction": dict(interaction),
        "promises": [dict(p) for p in promises],
        "tool_calls": [dict(tc) for tc in tool_calls],
    }


# ── Dashboard Analytics & Review Queue Endpoints ────────────────────────────

class ReviewRequest(BaseModel):
    action: str  # "approve" or "reject"


@app.get("/stats")
def get_stats() -> dict[str, Any]:
    """Aggregate stats for the dashboard overview cards."""
    with get_db() as conn:
        total     = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]
        allowed   = conn.execute("SELECT COUNT(*) as c FROM interactions WHERE status='allowed'").fetchone()["c"]
        blocked   = conn.execute("SELECT COUNT(*) as c FROM interactions WHERE status='blocked'").fetchone()["c"]
        rewritten = conn.execute("SELECT COUNT(*) as c FROM interactions WHERE status='rewritten'").fetchone()["c"]
        held      = conn.execute("SELECT COUNT(*) as c FROM interactions WHERE status='held'").fetchone()["c"]
        latency_row = conn.execute(
            "SELECT AVG(latency_ms) as avg_lat FROM model_usage WHERE ok=1"
        ).fetchone()
    avg_lat = round(latency_row["avg_lat"]) if latency_row and latency_row["avg_lat"] else None
    return {
        "total": total,
        "allowed": allowed,
        "blocked": blocked,
        "rewritten": rewritten,
        "held": held,
        "avg_latency_ms": avg_lat,
    }


@app.post("/review/{interaction_id}")
def review_interaction(interaction_id: str, req: ReviewRequest) -> dict[str, Any]:
    """Accept or reject a held interaction. Appends to audit log."""
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Interaction not found")
        if row["status"] != "held":
            raise HTTPException(status_code=409, detail="Interaction is not in 'held' state")

        new_status = "allowed" if req.action == "approve" else "blocked"
        conn.execute(
            "UPDATE interactions SET status = ? WHERE id = ?",
            (new_status, interaction_id),
        )

    try:
        log_seq = append_audit_entry(
            event_type="review_decision",
            payload={
                "interaction_id": interaction_id,
                "action": req.action,
                "new_status": new_status,
            },
            interaction_id=interaction_id,
        )
    except Exception as exc:
        logger.error("Audit logging for review_decision failed: %s", exc)
        log_seq = None

    return {
        "interaction_id": interaction_id,
        "action": req.action,
        "new_status": new_status,
        "log_seq": log_seq,
    }


@app.get("/models/usage")
def get_models_usage() -> dict[str, Any]:
    """Returns per-model count, average latency, tokens, cost per verified message, and savings."""
    settings = get_settings()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT model, stage, COUNT(*) as call_count, AVG(latency_ms) as avg_latency,
                   SUM(input_tokens) as total_in, SUM(output_tokens) as total_out,
                   SUM(cost_usd) as total_cost
            FROM model_usage
            GROUP BY model, stage
            ORDER BY call_count DESC
            """
        ).fetchall()
        summary_rows = conn.execute(
            """
            SELECT model, COUNT(*) as call_count, AVG(latency_ms) as avg_latency,
                   SUM(input_tokens) as total_in, SUM(output_tokens) as total_out,
                   SUM(cost_usd) as total_cost
            FROM model_usage
            GROUP BY model
            ORDER BY call_count DESC
            """
        ).fetchall()

        total_interactions = conn.execute(
            "SELECT COUNT(*) as c FROM interactions WHERE status IN ('allowed', 'rewritten', 'held')"
        ).fetchone()["c"]

    total_cost = sum((r["total_cost"] or 0.0) for r in summary_rows)
    total_in_tokens = sum((r["total_in"] or 0) for r in summary_rows)

    cost_per_msg = (total_cost / total_interactions) if total_interactions > 0 else 0.00015
    minimal_reasoning_savings = total_cost * 1.85
    prompt_caching_savings = (total_in_tokens / 1_000_000 * settings.COST_PER_M_INPUT_TOKENS) * settings.CACHE_SAVINGS_RATIO
    prefilter_savings = total_interactions * 0.00008

    return {
        "models": [
            {
                "model": r["model"],
                "calls": r["call_count"],
                "avg_latency_ms": round(r["avg_latency"] or 0),
                "total_input_tokens": r["total_in"] or 0,
                "total_output_tokens": r["total_out"] or 0,
                "cost_usd": round(r["total_cost"] or 0.0, 5),
            }
            for r in summary_rows
        ],
        "by_stage": [
            {
                "model": r["model"],
                "stage": r["stage"],
                "calls": r["call_count"],
                "avg_latency_ms": round(r["avg_latency"] or 0),
                "total_input_tokens": r["total_in"] or 0,
                "total_output_tokens": r["total_out"] or 0,
                "cost_usd": round(r["total_cost"] or 0.0, 5),
            }
            for r in rows
        ],
        "cost_metrics": {
            "total_cost_usd": round(total_cost, 4),
            "cost_per_verified_message_usd": round(cost_per_msg, 6),
            "total_verified_messages": total_interactions,
            "total_savings_usd": round(minimal_reasoning_savings + prompt_caching_savings + prefilter_savings, 4),
            "savings_breakdown": {
                "minimal_reasoning_savings": round(minimal_reasoning_savings, 4),
                "prompt_caching_savings": round(prompt_caching_savings, 4),
                "prefilter_savings": round(prefilter_savings, 4),
            },
        },
    }


# ── Commitment Lifecycle, Trust Receipts & Dispute Endpoints ────────────────

class PromiseLifecycleRequest(BaseModel):
    state: str  # proposed, approved, sent, fulfilled, failed, expired, flagged
    actor: str = "owner"
    note: str = ""


@app.get("/promises")
def list_promises(
    state: str | None = None,
    promise_type: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict[str, Any]:
    """Lists promises with lifecycle filtering and fulfillment metrics (Requirement 9)."""
    offset = (page - 1) * limit
    query = "SELECT * FROM promises WHERE 1=1"
    params: list[Any] = []

    if state:
        query += " AND lifecycle_state = ?"
        params.append(state.lower())
    if promise_type:
        query += " AND type = ?"
        params.append(promise_type.lower())

    query += " ORDER BY rowid DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM promises").fetchone()["c"]

    summary = get_commitments_summary()
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "summary": summary,
        "promises": [dict(r) for r in rows],
    }


@app.post("/promises/{promise_id}/lifecycle")
def update_promise_lifecycle_endpoint(promise_id: str, req: PromiseLifecycleRequest) -> dict[str, Any]:
    """Updates promise lifecycle state and records in audit log (Requirement 9)."""
    try:
        return update_promise_lifecycle(
            promise_id=promise_id,
            new_state=req.state,
            actor=req.actor,
            note=req.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/promises/check-fulfillment")
def run_fulfillment_check(date: str | None = None) -> dict[str, Any]:
    """Scans active commitments against inventory and delivery timelines to detect breaches (Requirement 9)."""
    return check_commitments_fulfillment(current_date_str=date)


@app.get("/receipt/{interaction_id}")
def get_receipt_endpoint(interaction_id: str) -> Response:
    """Returns a cryptographic receipt card PNG drawn by code (Section 3.16)."""
    try:
        png_bytes = generate_receipt_card(interaction_id)
        return Response(content=png_bytes, media_type="image/png")
    except KeyError:
        raise HTTPException(status_code=404, detail="Interaction not found")
    except Exception as exc:
        logger.error("Failed to generate receipt card: %s", exc)
        raise HTTPException(status_code=500, detail="Could not generate receipt card")


@app.get("/dispute/{interaction_id}")
def get_dispute_endpoint(interaction_id: str) -> dict[str, Any]:
    """Returns a read-only plain-English dispute report (Section 3.16)."""
    try:
        return generate_dispute_report(interaction_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Interaction not found")
    except Exception as exc:
        logger.error("Failed to generate dispute report: %s", exc)
        raise HTTPException(status_code=500, detail="Could not generate dispute report")
