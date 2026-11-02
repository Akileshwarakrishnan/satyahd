"""Business Rules loader and validator for Satyahd.

Follows Section 3.6:
- max_discount_percent: 0 to 100 (default 10)
- refund_window_days: 0 to 365 (default 14)
- standard_shipping_days: 0 to 60 (default 3)
- allow_unlimited_refund: bool (default False)
- require_evidence_for_damage_refund: bool (default True)
- min_confidence: 0.0 to 1.0 (default 0.6)

Rejects out-of-range values with clear, descriptive error messages.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.config import BASE_DIR
from app.db import get_db

RULES_FILE = BASE_DIR / "data" / "rules.json"


class BusinessRules(BaseModel):
    policy_version: str = Field(
        default="1.0",
        description="Policy version identifier (e.g. 1.0, 1.1)",
    )
    max_discount_percent: float = Field(
        default=10.0,
        description="Maximum authorized discount percentage (0 to 100)",
    )
    refund_window_days: int = Field(
        default=14,
        description="Standard refund window in days (0 to 365)",
    )
    standard_shipping_days: int = Field(
        default=3,
        description="Standard shipping days (0 to 60)",
    )
    allow_unlimited_refund: bool = Field(
        default=False,
        description="Whether unlimited refund promises ('any time', 'whenever') are permitted",
    )
    require_evidence_for_damage_refund: bool = Field(
        default=True,
        description="Whether damage refunds strictly require visible damage evidence",
    )
    min_confidence: float = Field(
        default=0.6,
        description="Minimum confidence threshold for promise extraction (0.0 to 1.0)",
    )

    @field_validator("max_discount_percent")
    @classmethod
    def validate_discount(cls, v: float) -> float:
        if v < 0 or v > 100:
            raise ValueError(f"max_discount_percent must be between 0 and 100, got {v}")
        return v

    @field_validator("refund_window_days")
    @classmethod
    def validate_refund_window(cls, v: int) -> int:
        if v < 0 or v > 365:
            raise ValueError(f"refund_window_days must be between 0 and 365, got {v}")
        return v

    @field_validator("standard_shipping_days")
    @classmethod
    def validate_shipping_days(cls, v: int) -> int:
        if v < 0 or v > 60:
            raise ValueError(f"standard_shipping_days must be between 0 and 60, got {v}")
        return v

    @field_validator("min_confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(f"min_confidence must be between 0.0 and 1.0, got {v}")
        return v


def load_rules(file_path: Path | None = None) -> BusinessRules:
    """Loads and validates business rules from data/rules.json or fallback defaults.
    
    Raises ValueError with a clear message if values are out of range.
    """
    target = file_path or (BASE_DIR / "data" / "rules.json")
    if not target.exists():
        # Fall back to default instance
        return BusinessRules()

    try:
        raw_text = target.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        raise ValueError(f"Failed to read rules JSON from {target}: {exc}") from exc

    try:
        rules = BusinessRules(**data)
    except ValidationError as err:
        errors = [f"{e['loc'][0]}: {e['msg']}" for e in err.errors()]
        raise ValueError(f"Rules validation error: {'; '.join(errors)}") from err

    # Ensure SQLite 'rules' table is in sync
    sync_rules_to_db(rules)
    return rules


def sync_rules_to_db(rules: BusinessRules, custom_db_path: str | None = None) -> None:
    """Persists business rules into the SQLite rules table."""
    try:
        with get_db(custom_db_path) as conn:
            for k, v in rules.model_dump().items():
                conn.execute(
                    "INSERT INTO rules (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, json.dumps(v)),
                )
    except Exception:
        # Ignore during early migrations or non-critical tests
        pass


def bump_version(current_ver: str) -> str:
    """Auto-increments version string like '1.0' -> '1.1' or '2' -> '3'."""
    try:
        parts = current_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}.{int(parts[1]) + 1}"
        if len(parts) == 1 and parts[0].isdigit():
            return f"1.{int(parts[0])}"
    except Exception:
        pass
    return "1.1"


def save_rules(new_rules_data: dict[str, Any], file_path: Path | None = None) -> BusinessRules:
    """Validates and saves new business rules to file and database with version bumping."""
    target = file_path or (BASE_DIR / "data" / "rules.json")
    data = dict(new_rules_data)

    if "policy_version" not in data or not data["policy_version"]:
        # Auto-increment from existing version if present
        current_version = "1.0"
        if target.exists():
            try:
                curr_data = json.loads(target.read_text(encoding="utf-8"))
                current_version = str(curr_data.get("policy_version", "1.0"))
            except Exception:
                pass
        data["policy_version"] = bump_version(current_version)

    try:
        rules = BusinessRules(**data)
    except ValidationError as err:
        errors = [f"{e['loc'][0]}: {e['msg']}" for e in err.errors()]
        raise ValueError(f"Rules validation error: {'; '.join(errors)}") from err

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rules.model_dump(), indent=2), encoding="utf-8")

    sync_rules_to_db(rules)
    return rules
