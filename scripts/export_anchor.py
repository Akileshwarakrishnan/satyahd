"""Anchor export script for Satyahd.

Follows Section 3.11:
Writes anchor_<date>_<time>.txt with the latest seq and hash to ANCHOR_DIR.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR, get_settings
from app.db import get_db
from app.auditlog import verify_chain


def export_anchor() -> Path | None:
    settings = get_settings()
    anchor_dir = BASE_DIR / settings.ANCHOR_DIR
    anchor_dir.mkdir(parents=True, exist_ok=True)

    # 1. Verify chain before exporting
    verification = verify_chain()
    if not verification["valid"]:
        print(f"ERROR: Cannot export anchor! Audit chain is invalid: {verification['reason']}")
        return None

    # 2. Get latest entry
    with get_db() as conn:
        last = conn.execute(
            "SELECT seq, hash, created_at FROM audit_log ORDER BY seq DESC LIMIT 1"
        ).fetchone()

    if not last:
        print("Notice: Audit log is currently empty. Nothing to export.")
        return None

    seq = last["seq"]
    entry_hash = last["hash"]
    created_at = last["created_at"]

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    anchor_file = anchor_dir / f"anchor_{now_str}.txt"

    payload = {
        "seq": seq,
        "hash": entry_hash,
        "created_at": created_at,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    anchor_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("========================================")
    print(" Satyahd Audit Anchor Exported")
    print("========================================")
    print(f"File:       {anchor_file}")
    print(f"Latest Seq: {seq}")
    print(f"Hash:       {entry_hash}")
    print(f"Created:    {created_at}")
    print("========================================")
    return anchor_file


if __name__ == "__main__":
    file_path = export_anchor()
    sys.exit(0 if file_path else 1)
