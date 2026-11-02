"""Promise Lifecycle & Fulfillment Tracking module for Satyahd.

Implements Requirement 9:
- Tracks commitments across states: proposed, approved, sent, fulfilled, failed, expired, flagged
- Monitors whether active commitments can still be fulfilled
- Detects stock depletion or delivery deadline expiry and flags affected promises for follow-up
- Appends every lifecycle state change to the append-only cryptographic audit log
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.auditlog import append_audit_entry
from app.config import get_settings
from app.db import get_db
from app.tools import JsonStoreAdapter

logger = logging.getLogger("satyahd.lifecycle")


class LifecycleState(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    SENT = "sent"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    EXPIRED = "expired"
    FLAGGED = "flagged"


# Valid allowed state transitions
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"approved", "sent", "failed"},
    "approved": {"sent", "failed"},
    "sent": {"fulfilled", "failed", "expired", "flagged"},
    "flagged": {"fulfilled", "failed", "expired", "sent"},
    "fulfilled": set(),
    "failed": set(),
    "expired": set(),
}


def update_promise_lifecycle(
    promise_id: str,
    new_state: str,
    actor: str = "system",
    note: str = "",
) -> dict[str, Any]:
    """Transitions a promise to a new lifecycle state and audit logs the event."""
    new_state_norm = new_state.lower().strip()
    valid_states = {s.value for s in LifecycleState}
    if new_state_norm not in valid_states:
        raise ValueError(f"Invalid lifecycle state '{new_state}'. Allowed: {sorted(valid_states)}")

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        row = conn.execute("SELECT * FROM promises WHERE id = ?", (promise_id,)).fetchone()
        if not row:
            raise KeyError(f"Promise '{promise_id}' not found.")

        current_state = row["lifecycle_state"] or "proposed"

        # Validate transition if not forcing
        allowed = ALLOWED_TRANSITIONS.get(current_state, set())
        if new_state_norm != current_state and new_state_norm not in allowed and actor == "system":
            raise ValueError(f"Illegal transition from '{current_state}' to '{new_state_norm}'.")

        fulfilled_at = now_iso if new_state_norm == LifecycleState.FULFILLED.value else row["fulfilled_at"]
        flagged_reason = note if new_state_norm == LifecycleState.FLAGGED.value else row["flagged_reason"]

        conn.execute(
            """
            UPDATE promises
            SET lifecycle_state = ?, fulfilled_at = ?, flagged_reason = ?
            WHERE id = ?
            """,
            (new_state_norm, fulfilled_at, flagged_reason, promise_id),
        )

    # Append audit log entry for the lifecycle transition
    log_seq: int | None = None
    try:
        log_seq = append_audit_entry(
            event_type="promise_lifecycle",
            payload={
                "promise_id": promise_id,
                "previous_state": current_state,
                "new_state": new_state_norm,
                "actor": actor,
                "note": note,
                "timestamp": now_iso,
            },
            interaction_id=row["interaction_id"],
        )
    except Exception as exc:
        logger.error("Audit log failed for lifecycle transition: %s", exc)

    logger.info("Promise %s transitioned from %s to %s by %s", promise_id, current_state, new_state_norm, actor)
    return {
        "promise_id": promise_id,
        "previous_state": current_state,
        "new_state": new_state_norm,
        "actor": actor,
        "log_seq": log_seq,
    }


def check_commitments_fulfillment(
    current_date_str: str | None = None,
) -> dict[str, Any]:
    """Scans all active promises against current inventory and time to detect fulfillment risks.
    
    If stock drops to zero or delivery due date has passed without fulfillment,
    flags the promise for human follow-up.
    """
    settings = get_settings()
    ref_date_str = current_date_str or getattr(settings, "DEMO_TODAY", "2026-11-01")
    ref_date = datetime.fromisoformat(ref_date_str).date() if "T" in ref_date_str else datetime.strptime(ref_date_str, "%Y-%m-%d").date()

    adapter = JsonStoreAdapter()
    flagged: list[dict[str, Any]] = []
    scanned_count = 0

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, i.customer_message, i.created_at as int_created_at
            FROM promises p
            JOIN interactions i ON p.interaction_id = i.id
            WHERE p.lifecycle_state IN ('sent', 'approved')
            """
        ).fetchall()

    for r in rows:
        scanned_count += 1
        p_id = r["id"]
        p_type = r["type"]
        p_val = r["value"]
        due_date_str = r["due_date"]
        flag_reason = ""

        # 1. Delivery deadline check
        if p_type == "delivery" and due_date_str:
            try:
                due_d = datetime.fromisoformat(due_date_str).date()
                if ref_date > due_d:
                    flag_reason = f"Delivery deadline {due_date_str} expired without recorded delivery fulfillment."
            except Exception:
                pass

        # 2. Stock depletion check
        elif p_type == "stock":
            prod_ref = r["quote"] or "P1"
            # Extract product or check store adapter
            prod = adapter.get_product(prod_ref)
            if prod:
                current_stock = prod["stock"]
                if current_stock <= 0:
                    flag_reason = f"Committed product '{prod['name']}' is now completely out of stock in inventory."
                elif p_val is not None and current_stock < float(p_val):
                    flag_reason = f"Committed {p_val:g} units, but only {current_stock} units remain in inventory."

        if flag_reason:
            update_promise_lifecycle(
                promise_id=p_id,
                new_state=LifecycleState.FLAGGED.value,
                actor="fulfillment_monitor",
                note=flag_reason,
            )
            flagged.append({
                "promise_id": p_id,
                "type": p_type,
                "reason": flag_reason,
            })

    return {
        "scanned_commitments": scanned_count,
        "flagged_commitments": len(flagged),
        "flagged_details": flagged,
        "reference_date": str(ref_date),
    }


def get_commitments_summary() -> dict[str, Any]:
    """Returns aggregated commitment metrics for dashboard monitoring."""
    with get_db() as conn:
        counts = conn.execute(
            """
            SELECT lifecycle_state, COUNT(*) as c
            FROM promises
            GROUP BY lifecycle_state
            """
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM promises").fetchone()["c"]

    summary = {s.value: 0 for s in LifecycleState}
    for row in counts:
        state = row["lifecycle_state"] or "proposed"
        if state in summary:
            summary[state] = row["c"]

    summary["total"] = total
    return summary
