"""Replayable Test Cases engine for Satyahd.

Follows Section 1.4:
- Re-runs any logged interaction against the current rules (or custom proposed rules).
- Purely deterministic replay: evaluates stored promises and facts against updated rule thresholds.
- Compares original verdict vs replayed verdict.
- Generates a clear diff summary showing the exact rule impact.
"""

from __future__ import annotations

import logging
from typing import Any

from app.db import get_db
from app.extract import Promise
from app.rules import BusinessRules, load_rules
from app.verify import Verdict, collect_facts, verify

logger = logging.getLogger("satyahd.replay")


def replay_interaction(
    interaction_id: str,
    rules: BusinessRules | None = None,
) -> dict[str, Any]:
    """Replays a logged interaction against current or proposed business rules."""
    current_rules = rules or load_rules()
    current_version = getattr(current_rules, "policy_version", "1.0")

    with get_db() as conn:
        int_row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?",
            (interaction_id,),
        ).fetchone()

        if not int_row:
            raise ValueError(f"Interaction '{interaction_id}' not found in database.")

        promise_rows = conn.execute(
            "SELECT * FROM promises WHERE interaction_id = ? ORDER BY rowid ASC",
            (interaction_id,),
        ).fetchall()

    orig_status = int_row["status"]
    orig_policy_ver = int_row["policy_version"] or "1.0"
    orig_reply = int_row["final_reply"]
    customer_msg = int_row["customer_message"]
    proposed_reply = int_row["proposed_reply"]

    # Reconstruct Promise objects for attempt 0 (initial proposed promises)
    attempt_0_rows = [r for r in promise_rows if r["attempt"] == 0]
    target_rows = attempt_0_rows if attempt_0_rows else promise_rows

    promises: list[Promise] = []
    if target_rows:
        for r in target_rows:
            promises.append(
                Promise(
                    type=r["type"],
                    value=r["value"],
                    unit=r["unit"],
                    unlimited=bool(r["unlimited"]),
                    quote=r["quote"],
                    confidence=float(r["confidence"]),
                    vague=bool(r["vague"]),
                    damage_basis=bool(r["damage_basis"]),
                    verdict=r["verdict"],
                    reason=r["reason"],
                    rule_name=r["rule_name"],
                    threshold=r["threshold"],
                    lifecycle_state=r["lifecycle_state"],
                    due_date=r["due_date"],
                )
            )
    elif proposed_reply:
        from app.extract import extract_promises
        extracted, _ = extract_promises(proposed_reply, customer_msg, interaction_id=interaction_id)
        promises = extracted

    # Collect facts for verification
    facts = collect_facts(promises, interaction_id=interaction_id)

    # Deterministic re-verification
    replayed_res = verify(promises, current_rules, facts)
    replayed_verdict = replayed_res.message_verdict.value

    # Normalize original draft verdict for comparison (a rewritten message was blocked in drafting)
    if orig_status in ("blocked", "rewritten"):
        orig_verdict_norm = "block"
    elif orig_status == "allowed":
        orig_verdict_norm = "allow"
    else:
        orig_verdict_norm = "review"

    verdict_changed = (orig_verdict_norm != replayed_verdict)

    # Diff summary explanation
    if verdict_changed:
        diff_summary = (
            f"Policy update ({orig_policy_ver} -> {current_version}): Verdict changed from '{orig_verdict_norm.upper()}' to '{replayed_verdict.upper()}'. "
            f"Rule evaluation under current thresholds modified compliance outcome."
        )
    else:
        diff_summary = (
            f"Deterministic parity confirmed: Interaction outcome remains '{replayed_verdict.upper()}' "
            f"under policy version {current_version}."
        )

    return {
        "interaction_id": interaction_id,
        "customer_message": customer_msg,
        "proposed_reply": proposed_reply,
        "original": {
            "policy_version": orig_policy_ver,
            "status": orig_status,
            "verdict": orig_verdict_norm,
            "final_reply": orig_reply,
        },
        "replayed": {
            "policy_version": current_version,
            "verdict": replayed_verdict,
            "reasons": replayed_res.reasons,
            "violations": replayed_res.violations,
            "plan": replayed_res.plan,
        },
        "verdict_changed": verdict_changed,
        "diff_summary": diff_summary,
    }


def replay_recent_interactions(
    limit: int = 10,
    rules: BusinessRules | None = None,
) -> dict[str, Any]:
    """Replays recent interactions to produce a batch compliance drift report."""
    current_rules = rules or load_rules()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id FROM interactions WHERE status != 'received' ORDER BY rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()

    results = []
    changed_count = 0

    for r in rows:
        try:
            rep = replay_interaction(r["id"], current_rules)
            results.append(rep)
            if rep["verdict_changed"]:
                changed_count += 1
        except Exception as exc:
            logger.warning("Replay failed for interaction %s: %s", r["id"], exc)

    return {
        "total_replayed": len(results),
        "verdicts_changed": changed_count,
        "unchanged": len(results) - changed_count,
        "current_policy_version": getattr(current_rules, "policy_version", "1.0"),
        "replays": results,
    }
