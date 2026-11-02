"""Cryptographic, Append-Only Audit Log for Satyahd.

Follows Section 3.11:
- Append-only SQLite table protected by abort triggers
- Event types: 'decision', 'review_action', 'rules_change'
- Sequence: strictly sequential starting at 1 with no gaps
- Canonical JSON: UTF-8, keys sorted, no extra whitespace
- Initial entry prev_hash: 64 zeros
- SHA-256 hash: prev_hash + seq + created_at + canonical payload
- Ed25519 digital signature of hash using private key from SIGNING_KEY_PATH
- verify_chain(): verifies sequence continuity, prev_hash links, recomputed hashes,
  Ed25519 signatures, and optional anchor files.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.config import BASE_DIR, get_settings
from app.db import get_db

logger = logging.getLogger("satyahd.auditlog")

GENESIS_HASH = "0" * 64


def canonical_json(data: Any) -> str:
    """Produces canonical JSON: keys sorted, compact separators, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _get_signing_key_paths() -> tuple[Path, Path]:
    settings = get_settings()
    priv_path = Path(settings.SIGNING_KEY_PATH)
    if not priv_path.is_absolute():
        priv_path = BASE_DIR / priv_path

    pub_path = priv_path.parent / f"{priv_path.stem}_pub.pem"
    return priv_path, pub_path


def load_or_generate_keypair() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Loads existing Ed25519 private key or creates a new one with secure permissions."""
    priv_path, pub_path = _get_signing_key_paths()
    priv_path.parent.mkdir(parents=True, exist_ok=True)

    if priv_path.exists():
        key_bytes = priv_path.read_bytes()
        private_key = serialization.load_pem_private_key(key_bytes, password=None)
        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise TypeError("Key is not an Ed25519 private key")
        public_key = private_key.public_key()
        return private_key, public_key

    # Generate new Ed25519 keypair
    logger.info("Generating new Ed25519 signing keypair at %s", priv_path)
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_path.write_bytes(priv_bytes)
    pub_path.write_bytes(pub_bytes)

    # Restrict permissions on Windows / POSIX where possible
    try:
        os.chmod(priv_path, 0o600)
    except Exception:
        pass

    return private_key, public_key


def get_public_key() -> ed25519.Ed25519PublicKey:
    """Returns the public key used for audit verification."""
    _, pub_key = load_or_generate_keypair()
    return pub_key


def calculate_entry_hash(prev_hash: str, seq: int, created_at: str, payload_str: str) -> str:
    """Calculates SHA-256 hash of prev_hash, seq, created_at, and canonical payload."""
    raw = f"{prev_hash}{seq}{created_at}{payload_str}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def append_audit_entry(
    event_type: str,
    payload: dict[str, Any],
    interaction_id: str | None = None,
    custom_db_path: str | None = None,
) -> int:
    """Appends a new signed, hash-chained entry to the audit log.
    
    Hard Rule 3: Write the audit entry BEFORE any reply is returned.
    If the write fails, nothing is sent.
    """
    private_key, _ = load_or_generate_keypair()
    created_at = datetime.now(timezone.utc).isoformat()
    canonical_payload_str = canonical_json(payload)

    with get_db(custom_db_path) as conn:
        # Get latest entry
        last = conn.execute(
            "SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1"
        ).fetchone()

        if last is None:
            seq = 1
            prev_hash = GENESIS_HASH
        else:
            seq = last["seq"] + 1
            prev_hash = last["hash"]

        # Compute hash
        entry_hash = calculate_entry_hash(prev_hash, seq, created_at, canonical_payload_str)

        # Ed25519 signature over hash
        sig_bytes = private_key.sign(entry_hash.encode("utf-8"))
        signature_hex = sig_bytes.hex()

        conn.execute(
            """
            INSERT INTO audit_log (seq, event_type, interaction_id, payload, prev_hash, hash, signature, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                seq,
                event_type,
                interaction_id,
                canonical_payload_str,
                prev_hash,
                entry_hash,
                signature_hex,
                created_at,
            ),
        )

    logger.info("Audit log entry #%d (%s) written and signed.", seq, event_type)
    return seq


def verify_chain(
    custom_db_path: str | None = None,
    anchor_file_path: Path | None = None,
) -> dict[str, Any]:
    """Verifies the integrity of the audit log chain.
    
    Checks in order:
    1. Seq starts at 1 with no gaps.
    2. Each prev_hash equals the previous hash.
    3. Recomputed SHA-256 matches stored hash.
    4. Ed25519 signature is cryptographically valid.
    5. Reaches anchor seq and hash if anchor file exists.
    """
    public_key = get_public_key()

    with get_db(custom_db_path) as conn:
        rows = conn.execute(
            "SELECT seq, event_type, payload, prev_hash, hash, signature, created_at FROM audit_log ORDER BY seq ASC"
        ).fetchall()

    if not rows:
        return {
            "valid": True,
            "entries_checked": 0,
            "first_bad_seq": None,
            "reason": "Audit log is empty.",
        }

    expected_seq = 1
    expected_prev_hash = GENESIS_HASH
    entries_checked = 0

    for row in rows:
        seq = row["seq"]
        prev_hash = row["prev_hash"]
        stored_hash = row["hash"]
        signature_hex = row["signature"]
        created_at = row["created_at"]
        payload_str = row["payload"]

        # 1. Seq check
        if seq != expected_seq:
            return {
                "valid": False,
                "entries_checked": entries_checked,
                "first_bad_seq": seq,
                "reason": f"Sequence gap or mismatch: expected {expected_seq}, found {seq}.",
            }

        # 2. prev_hash check
        if prev_hash != expected_prev_hash:
            return {
                "valid": False,
                "entries_checked": entries_checked,
                "first_bad_seq": seq,
                "reason": f"Hash chain broken at seq {seq}: prev_hash mismatch.",
            }

        # 3. Recomputed hash check
        recomputed_hash = calculate_entry_hash(prev_hash, seq, created_at, payload_str)
        if recomputed_hash != stored_hash:
            return {
                "valid": False,
                "entries_checked": entries_checked,
                "first_bad_seq": seq,
                "reason": f"Tampered payload or hash at seq {seq}: recomputed hash does not match.",
            }

        # 4. Signature check
        try:
            sig_bytes = bytes.fromhex(signature_hex)
            public_key.verify(sig_bytes, stored_hash.encode("utf-8"))
        except (InvalidSignature, ValueError) as exc:
            return {
                "valid": False,
                "entries_checked": entries_checked,
                "first_bad_seq": seq,
                "reason": f"Invalid Ed25519 digital signature at seq {seq}: {exc}",
            }

        expected_prev_hash = stored_hash
        expected_seq += 1
        entries_checked += 1

    # 5. Anchor check (if anchor file provided)
    if anchor_file_path and anchor_file_path.exists():
        try:
            content = anchor_file_path.read_text(encoding="utf-8")
            anchor_data = json.loads(content)
            a_seq = anchor_data.get("seq")
            a_hash = anchor_data.get("hash")

            matched_anchor = False
            for r in rows:
                if r["seq"] == a_seq and r["hash"] == a_hash:
                    matched_anchor = True
                    break

            if not matched_anchor:
                return {
                    "valid": False,
                    "entries_checked": entries_checked,
                    "first_bad_seq": a_seq,
                    "reason": f"Chain does not reach anchor seq {a_seq} and hash {a_hash}.",
                }
        except Exception as exc:
            logger.warning("Error reading anchor file: %s", exc)

    return {
        "valid": True,
        "entries_checked": entries_checked,
        "first_bad_seq": None,
        "reason": f"All {entries_checked} entries verified successfully.",
    }
