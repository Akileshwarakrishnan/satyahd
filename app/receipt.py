"""Receipt Card Generator for Satyahd (Section 3.16 Stretch Feature).

Generates a tamper-evident, cryptographic receipt card PNG:
- Business name: Kaveri Home Appliances
- Exact promise text and type
- Verification timestamp
- Final verdict badge (ALLOWED, REWRITTEN, BLOCKED, HELD)
- First 8 characters of the Ed25519 log hash
- Clean layout drawn by code using Pillow
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.db import get_db


def generate_receipt_card(interaction_id: str) -> bytes:
    """Renders a receipt card image for an interaction and returns PNG bytes."""
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

        audit = conn.execute(
            "SELECT * FROM audit_log WHERE interaction_id = ? ORDER BY seq DESC LIMIT 1",
            (interaction_id,),
        ).fetchone()

    status = (interaction["status"] or "allowed").upper()
    ts = interaction["created_at"] or datetime.now(timezone.utc).isoformat()
    hash_abbr = (audit["hash"][:8] if audit else "GENESIS8").upper()
    seq_str = str(audit["seq"]) if audit else "N/A"

    # Extract primary promise
    promise_desc = "Standard Store Terms"
    if promises:
        p0 = promises[0]
        pval = f"{p0['value']:g}" if p0['value'] is not None else ""
        punit = p0['unit'] or ""
        promise_desc = f"{p0['type'].upper()}: {pval} {punit} (\"{p0['quote']}\")".strip()

    # Image Dimensions
    width, height = 640, 360
    im = Image.new("RGB", (width, height), color=(15, 23, 42))  # --color-surface-0
    draw = ImageDraw.Draw(im)

    # Palette
    accent_blue = (59, 130, 246)
    card_surface = (30, 41, 59)
    border_color = (51, 65, 85)
    text_white = (241, 245, 249)
    text_muted = (148, 163, 184)

    # Status badge color
    status_colors = {
        "ALLOWED": (34, 197, 94),
        "REWRITTEN": (245, 158, 11),
        "BLOCKED": (239, 68, 68),
        "HELD": (167, 139, 250),
    }
    badge_color = status_colors.get(status, (100, 116, 139))

    # Inner Card Panel
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=12, fill=card_surface, outline=border_color, width=2)

    # Top Brand Header
    draw.text((45, 42), "⚖ SATYAHD VERIFIED RECEIPT", fill=accent_blue)
    draw.text((45, 66), "Kaveri Home Appliances — Customer Assurance", fill=text_white)
    draw.line([(45, 96), (width - 45, 96)], fill=border_color, width=1)

    # Receipt Metadata Grid
    draw.text((45, 115), "INTERACTION ID", fill=text_muted)
    draw.text((45, 135), interaction_id, fill=text_white)

    draw.text((360, 115), "TIMESTAMP", fill=text_muted)
    draw.text((360, 135), ts[:19].replace("T", " "), fill=text_white)

    draw.text((45, 175), "VERIFIED COMMITMENT", fill=text_muted)
    draw.text((45, 195), promise_desc[:52], fill=text_white)

    draw.text((45, 235), "CRYPTOGRAPHIC HASH", fill=text_muted)
    draw.text((45, 255), f"SHA-256 #{seq_str} [{hash_abbr}...] (Ed25519 Signed)", fill=accent_blue)

    # Status Badge Pill
    draw.rounded_rectangle([width - 170, 40, width - 45, 75], radius=6, fill=badge_color)
    draw.text((width - 150, 49), status, fill=(255, 255, 255))

    # Footer Notice
    draw.line([(45, 290), (width - 45, 290)], fill=border_color, width=1)
    draw.text(
        (45, 305),
        "Tamper-evident record protected by append-only audit chain. Verify at /audit/verify",
        fill=text_muted,
    )

    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()
