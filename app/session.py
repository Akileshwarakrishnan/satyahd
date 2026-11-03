"""Session and Multi-turn Memory Service for Fashion Chatbot (TR-2, FR-5, FR-6, FR-7, FR-18).

Provides:
- In-memory fast LRU/dictionary cache with SQLite persistence
- Sliding history window of last N turns (default 10)
- Active product context binding and pronoun resolution
- Consecutive fallback tracking for 2-strike human escalation (FR-18)
- Customer feedback recording (AN-3)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.db import get_db

logger = logging.getLogger("satyahd.session")


@dataclass
class ChatTurn:
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    intent: str | None = None
    chips: list[str] = field(default_factory=list)
    grounded: bool = True
    confidence: float = 1.0


@dataclass
class FashionSession:
    session_id: str
    product_id: str | None = None
    history: list[ChatTurn] = field(default_factory=list)
    fallback_count: int = 0
    escalated: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Global in-memory cache for ultra-low latency (<1ms)
_SESSIONS: dict[str, FashionSession] = {}


def _load_from_db(session_id: str) -> FashionSession | None:
    """Attempts to hydrate session state from SQLite."""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT session_id, product_id, history_json, fallback_count, escalated, created_at, updated_at "
                "FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None

            raw_history = json.loads(row["history_json"] or "[]")
            history_objs = [
                ChatTurn(
                    role=t.get("role", "user"),
                    content=t.get("content", ""),
                    timestamp=t.get("timestamp", ""),
                    intent=t.get("intent"),
                    chips=t.get("chips", []),
                    grounded=bool(t.get("grounded", True)),
                    confidence=float(t.get("confidence", 1.0)),
                )
                for t in raw_history
            ]

            return FashionSession(
                session_id=row["session_id"],
                product_id=row["product_id"],
                history=history_objs,
                fallback_count=int(row["fallback_count"] or 0),
                escalated=bool(row["escalated"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
    except Exception as exc:
        logger.warning("Could not load session %s from SQLite: %s", session_id, exc)
        return None


def _persist_to_db(sess: FashionSession) -> None:
    """Saves session state asynchronously/synchronously to SQLite."""
    try:
        raw_history = [
            {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp,
                "intent": t.intent,
                "chips": t.chips,
                "grounded": t.grounded,
                "confidence": t.confidence,
            }
            for t in sess.history[-20:]  # keep recent 20 in DB
        ]
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO chat_sessions (session_id, product_id, history_json, fallback_count, escalated, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    product_id = excluded.product_id,
                    history_json = excluded.history_json,
                    fallback_count = excluded.fallback_count,
                    escalated = excluded.escalated,
                    updated_at = excluded.updated_at
                """,
                (
                    sess.session_id,
                    sess.product_id,
                    json.dumps(raw_history),
                    sess.fallback_count,
                    1 if sess.escalated else 0,
                    sess.created_at,
                    sess.updated_at,
                ),
            )
    except Exception as exc:
        logger.warning("Failed to persist session %s: %s", sess.session_id, exc)


def get_or_create_session(session_id: str, product_id: str | None = None) -> FashionSession:
    """Gets existing session from cache/DB or creates a fresh session."""
    if session_id in _SESSIONS:
        sess = _SESSIONS[session_id]
        if product_id and sess.product_id != product_id:
            sess.product_id = product_id
            sess.updated_at = datetime.now(timezone.utc).isoformat()
            _persist_to_db(sess)
        return sess

    # Try DB hydration
    sess = _load_from_db(session_id)
    if not sess:
        sess = FashionSession(
            session_id=session_id,
            product_id=product_id or "F101",
        )
        _persist_to_db(sess)
    elif product_id and sess.product_id != product_id:
        sess.product_id = product_id
        sess.updated_at = datetime.now(timezone.utc).isoformat()
        _persist_to_db(sess)

    _SESSIONS[session_id] = sess
    return sess


def update_active_product(session_id: str, product_id: str) -> None:
    """Binds or switches the active product context for the session (FR-6)."""
    sess = get_or_create_session(session_id)
    sess.product_id = product_id
    sess.updated_at = datetime.now(timezone.utc).isoformat()
    _persist_to_db(sess)


def add_turn(
    session_id: str,
    role: str,
    content: str,
    intent: str | None = None,
    chips: list[str] | None = None,
    grounded: bool = True,
    confidence: float = 1.0,
) -> None:
    """Appends a turn to the session history (FR-5)."""
    sess = get_or_create_session(session_id)
    now = datetime.now(timezone.utc).isoformat()
    turn = ChatTurn(
        role=role,
        content=content,
        timestamp=now,
        intent=intent,
        chips=chips or [],
        grounded=grounded,
        confidence=confidence,
    )
    sess.history.append(turn)
    # Sliding window of last 10 messages for active LLM context
    sess.updated_at = now
    _persist_to_db(sess)


def get_recent_history(session_id: str, limit: int = 10) -> list[dict[str, str]]:
    """Returns the last N conversation turns formatted for model prompts (FR-5)."""
    sess = get_or_create_session(session_id)
    recent = sess.history[-limit:]
    return [{"role": t.role, "content": t.content} for t in recent]


def record_fallback(session_id: str) -> int:
    """Increments consecutive fallback count. Returns new count (FR-18)."""
    sess = get_or_create_session(session_id)
    sess.fallback_count += 1
    sess.updated_at = datetime.now(timezone.utc).isoformat()
    if sess.fallback_count >= 2:
        sess.escalated = True
    _persist_to_db(sess)
    return sess.fallback_count


def reset_fallback(session_id: str) -> None:
    """Resets fallback counter on a successful, grounded answer."""
    sess = get_or_create_session(session_id)
    if sess.fallback_count > 0:
        sess.fallback_count = 0
        sess.updated_at = datetime.now(timezone.utc).isoformat()
        _persist_to_db(sess)


def escalate_session(session_id: str) -> None:
    """Flags session as escalated to human support."""
    sess = get_or_create_session(session_id)
    sess.escalated = True
    sess.updated_at = datetime.now(timezone.utc).isoformat()
    _persist_to_db(sess)


def record_feedback(session_id: str, turn_index: int, rating: int, comment: str | None = None) -> None:
    """Persists thumbs up / down feedback to SQLite (AN-3)."""
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_feedback (id, session_id, turn_index, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (feedback_id, session_id, turn_index, rating, comment, now),
        )
    logger.info("Recorded feedback %d for session %s at turn %d", rating, session_id, turn_index)
