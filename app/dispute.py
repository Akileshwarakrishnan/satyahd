"""Dispute Report Generator for Satyahd (Section 3.16 Stretch Feature).

Produces a read-only, plain-English dispute report for a specific interaction:
- Summary & Timeline of the conversation
- Exact promise, verdict, and governing business rule
- Grounded enterprise evidence consulted (inventory, shipping, order age)
- Cryptographic chain proof verifying the entry has not been altered
"""

from __future__ import annotations

import json
from typing import Any

from app.auditlog import verify_chain
from app.db import get_db


def generate_dispute_report(interaction_id: str) -> dict[str, Any]:
    """Compiles complete verifiable evidence and timeline for dispute resolution."""
    with get_db() as conn:
        interaction = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
        ).fetchone()
        if not interaction:
            raise KeyError(f"Interaction '{interaction_id}' not found.")

        promises = conn.execute(
            "SELECT * FROM promises WHERE interaction_id = ? ORDER BY attempt ASC",
            (interaction_id,),
        ).fetchall()

        tools = conn.execute(
            "SELECT * FROM tool_calls WHERE interaction_id = ? ORDER BY rowid ASC",
            (interaction_id,),
        ).fetchall()

        images = conn.execute(
            "SELECT * FROM images WHERE interaction_id = ?", (interaction_id,)
        ).fetchall()

        audit = conn.execute(
            "SELECT * FROM audit_log WHERE interaction_id = ? ORDER BY seq DESC LIMIT 1",
            (interaction_id,),
        ).fetchone()

    # Verify cryptographic audit chain integrity
    chain_status = verify_chain()

    # Timeline Reconstruction
    timeline: list[dict[str, str]] = [
        {
            "step": "1. Customer Inquiry Received",
            "time": interaction["created_at"],
            "detail": f"Customer transmitted message: \"{interaction['customer_message']}\"",
        },
        {
            "step": "2. Sales Agent Drafting",
            "time": interaction["created_at"],
            "detail": f"Agent {interaction['agent_id']} ({interaction['mode']}) drafted initial reply.",
        },
    ]

    for idx, p in enumerate(promises, start=1):
        timeline.append({
            "step": f"3.{idx} Promise Extraction & Rule Evaluation",
            "time": interaction["created_at"],
            "detail": (
                f"Extracted {p['type']} promise (\"{p['quote']}\"). "
                f"Rule: {p['rule_name'] or 'N/A'}. Verdict: {p['verdict'].upper()}. Reason: {p['reason']}"
            ),
        })

    timeline.append({
        "step": "4. Final Output Gate & Delivery",
        "time": interaction["created_at"],
        "detail": f"Status '{interaction['status']}'. Customer was delivered: \"{interaction['final_reply']}\"",
    })

    if audit:
        timeline.append({
            "step": "5. Cryptographic Audit Log Commit",
            "time": audit["created_at"],
            "detail": f"Committed to append-only log at seq #{audit['seq']} with SHA-256 hash {audit['hash'][:16]}...",
        })

    # Evidence details
    evidence = {
        "tools_executed": [
            {"tool": t["name"], "args": t["args"], "result": t["result"]}
            for t in tools
        ],
        "image_evidence": [
            {
                "damage_visible": bool(img["damage_visible"]),
                "confidence": img["confidence"],
                "damage_type": img["damage_type"],
            }
            for img in images
        ],
    }

    # Cryptographic Proof
    crypto_proof = {
        "audit_seq": audit["seq"] if audit else None,
        "entry_hash": audit["hash"] if audit else None,
        "previous_hash": audit["prev_hash"] if audit else None,
        "signature_valid": bool(chain_status.get("valid", False)),
        "chain_verified": chain_status.get("valid", False),
        "total_entries_checked": chain_status.get("entries_checked", 0),
    }

    return {
        "report_title": f"Satyahd Dispute & Compliance Report: {interaction_id}",
        "store": "Kaveri Home Appliances",
        "interaction_id": interaction_id,
        "session_id": interaction["session_id"],
        "status": interaction["status"],
        "summary": (
            f"Interaction {interaction_id} was evaluated under store policy rules. "
            f"The final status is '{interaction['status']}', resulting in the message: \"{interaction['final_reply']}\"."
        ),
        "customer_message": interaction["customer_message"],
        "proposed_reply": interaction["proposed_reply"],
        "final_reply": interaction["final_reply"],
        "promises": [dict(p) for p in promises],
        "evidence": evidence,
        "timeline": timeline,
        "cryptographic_proof": crypto_proof,
    }
