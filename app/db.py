"""Database management module for Satyahd.

Creates and manages the 10 SQLite database tables according to Section B4.1.
Enforces an append-only audit_log table using SQLite abort triggers.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import get_settings


SCHEMA_SQL = """
-- 1. Rules table: store dynamic business rules
CREATE TABLE IF NOT EXISTS rules (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 2. Products table
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    stock INTEGER NOT NULL,
    shipping_days INTEGER NOT NULL
);

-- 3. Orders table
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- 4. Interactions table (each chat / verify interaction)
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    customer_message TEXT NOT NULL,
    image_id TEXT,
    proposed_reply TEXT,
    final_reply TEXT,
    status TEXT NOT NULL,
    failure_code TEXT,
    created_at TEXT NOT NULL,
    policy_version TEXT DEFAULT '1.0'
);

-- 5. Promises extracted from agent drafts
CREATE TABLE IF NOT EXISTS promises (
    id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 0,
    type TEXT NOT NULL,
    value REAL,
    unit TEXT,
    unlimited INTEGER NOT NULL DEFAULT 0,
    quote TEXT NOT NULL,
    confidence REAL NOT NULL,
    vague INTEGER NOT NULL DEFAULT 0,
    damage_basis INTEGER NOT NULL DEFAULT 0,
    verdict TEXT NOT NULL,
    reason TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'proposed',
    fulfilled_at TEXT,
    flagged_reason TEXT,
    due_date TEXT,
    rule_name TEXT,
    threshold REAL,
    policy_clause TEXT,
    evidence TEXT,
    FOREIGN KEY(interaction_id) REFERENCES interactions(id)
);

-- 6. Tool calls made during verification
CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    interaction_id TEXT,
    name TEXT NOT NULL,
    args TEXT NOT NULL,
    result TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    FOREIGN KEY(interaction_id) REFERENCES interactions(id)
);

-- 7. Images and damage inspection results
CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    interaction_id TEXT,
    path TEXT NOT NULL,
    damage_visible INTEGER NOT NULL DEFAULT 0,
    damage_type TEXT,
    description TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    mask_path TEXT,
    overlay_path TEXT,
    synthetic INTEGER NOT NULL DEFAULT 0
);

-- 8. Model usage tracking for every call
CREATE TABLE IF NOT EXISTS model_usage (
    id TEXT PRIMARY KEY,
    interaction_id TEXT,
    stage TEXT NOT NULL,
    model TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    ok INTEGER NOT NULL,
    cost_usd REAL DEFAULT 0.0
);

-- 9. Append-only Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    interaction_id TEXT,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 10. Review actions by store owner
CREATE TABLE IF NOT EXISTS review_actions (
    id TEXT PRIMARY KEY,
    interaction_id TEXT NOT NULL,
    action TEXT NOT NULL,
    new_reply TEXT,
    actor TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(interaction_id) REFERENCES interactions(id)
);

-- Enforce append-only triggers on audit_log
CREATE TRIGGER IF NOT EXISTS abort_audit_log_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log is append-only: UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS abort_audit_log_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'Audit log is append-only: DELETE is forbidden');
END;

-- Helpful indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_promises_interaction ON promises(interaction_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_interaction ON tool_calls(interaction_id);
CREATE INDEX IF NOT EXISTS idx_model_usage_interaction ON model_usage(interaction_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_seq ON audit_log(seq);
"""


def get_db_path(custom_path: str | None = None) -> Path:
    path_str = custom_path or os.getenv("DB_PATH") or get_settings().DB_PATH
    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db(custom_path: str | None = None) -> None:
    """Initialize database tables, triggers, and apply non-destructive schema migrations."""
    db_file = get_db_path(custom_path)
    with sqlite3.connect(db_file) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)

        # Apply schema migrations for promises table if needed
        cols = {row[1] for row in conn.execute("PRAGMA table_info(promises)").fetchall()}
        migrations = [
            ("lifecycle_state", "TEXT NOT NULL DEFAULT 'proposed'"),
            ("fulfilled_at", "TEXT"),
            ("flagged_reason", "TEXT"),
            ("due_date", "TEXT"),
            ("rule_name", "TEXT"),
            ("threshold", "REAL"),
            ("policy_clause", "TEXT"),
            ("evidence", "TEXT"),
        ]
        for col_name, col_def in migrations:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE promises ADD COLUMN {col_name} {col_def};")

        # Migrate model_usage table for cost_usd if needed
        mu_cols = {row[1] for row in conn.execute("PRAGMA table_info(model_usage)").fetchall()}
        if "cost_usd" not in mu_cols:
            conn.execute("ALTER TABLE model_usage ADD COLUMN cost_usd REAL DEFAULT 0.0;")

        # Migrate interactions table for policy_version if needed
        int_cols = {row[1] for row in conn.execute("PRAGMA table_info(interactions)").fetchall()}
        if "policy_version" not in int_cols:
            conn.execute("ALTER TABLE interactions ADD COLUMN policy_version TEXT DEFAULT '1.0';")

        conn.commit()


@contextmanager
def get_db(custom_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional database connection."""
    db_file = get_db_path(custom_path)
    conn = sqlite3.connect(db_file, check_same_thread=False, timeout=15.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
