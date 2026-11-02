"""Promise-Type and Configurable Rule Schema Registry for Satyahd.

Implements R-301, R-302, R-303:
- Dynamic Promise-Type Registry loaded from JSON configuration packs.
- Structured Rule Schema: field, operator, threshold, severity, action, policy_clause_id.
- Dynamic deterministic evaluation against extracted promises and tool actions.
"""

from __future__ import annotations

import json
import logging
import operator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import BASE_DIR

logger = logging.getLogger("satyahd.registry")

RULE_PACKS_DIR = BASE_DIR / "data" / "rule_packs"

OPERATOR_MAP = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
    "!=": operator.ne,
}


@dataclass
class RuleDefinition:
    id: str
    field: str
    operator: str
    threshold: Any
    severity: str = "high"
    action: str = "block"
    policy_clause_id: str | None = None
    message: str = ""

    def evaluate(self, actual_value: Any, fact_context: dict[str, Any] | None = None) -> tuple[bool, str]:
        """Evaluates actual value against rule threshold.
        
        Returns (is_compliant, reason).
        """
        if actual_value is None:
            return True, "No numerical value to test."

        target_threshold = self.threshold
        if isinstance(target_threshold, str) and target_threshold.startswith("facts."):
            fact_key = target_threshold.split(".", 1)[1]
            target_threshold = (fact_context or {}).get(fact_key)
            if target_threshold is None:
                return False, f"Rule threshold fact '{fact_key}' missing from context."

        op_func = OPERATOR_MAP.get(self.operator)
        if not op_func:
            return False, f"Unsupported rule operator: {self.operator}"

        try:
            val_float = float(actual_value)
            thresh_float = float(target_threshold)
            compliant = bool(op_func(val_float, thresh_float))
            if compliant:
                return True, f"Value {val_float} meets threshold ({self.operator} {thresh_float})."
            else:
                return False, (
                    self.message
                    or f"Value {val_float} violates rule threshold ({self.operator} {thresh_float})."
                )
        except (ValueError, TypeError) as exc:
            return False, f"Comparison error: {exc}"


@dataclass
class PromiseTypeDefinition:
    name: str
    field: str
    unit: str
    description: str = ""
    rules: list[RuleDefinition] = field(default_factory=list)


class PromiseRegistry:
    """Manages dynamic promise types and domain rule packs."""

    def __init__(self, packs_dir: Path | None = None):
        self.packs_dir = packs_dir or RULE_PACKS_DIR
        self.promise_types: dict[str, PromiseTypeDefinition] = {}
        self.current_pack_name: str = "retail"
        self.reload_from_pack("retail")

    def reload_from_pack(self, pack_name: str = "retail") -> bool:
        """Loads or reloads promise definitions from a JSON rule pack."""
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        pack_file = self.packs_dir / f"{pack_name}.json"

        if not pack_file.exists():
            # Fallback default retail pack
            self._register_default_retail_pack()
            return False

        try:
            data = json.loads(pack_file.read_text(encoding="utf-8"))
            self.current_pack_name = data.get("pack_name", pack_name)
            self.promise_types.clear()

            for pt in data.get("promise_types", []):
                rules_list = []
                for r in pt.get("rules", []):
                    rules_list.append(
                        RuleDefinition(
                            id=r["id"],
                            field=r["field"],
                            operator=r["operator"],
                            threshold=r["threshold"],
                            severity=r.get("severity", "high"),
                            action=r.get("action", "block"),
                            policy_clause_id=r.get("policy_clause_id"),
                            message=r.get("message", ""),
                        )
                    )
                self.promise_types[pt["name"]] = PromiseTypeDefinition(
                    name=pt["name"],
                    field=pt.get("field", pt["name"]),
                    unit=pt.get("unit", ""),
                    description=pt.get("description", ""),
                    rules=rules_list,
                )
            logger.info("Loaded %d promise types from pack '%s'", len(self.promise_types), pack_name)
            return True
        except Exception as exc:
            logger.error("Failed to load rule pack '%s': %s", pack_name, exc)
            self._register_default_retail_pack()
            return False

    def _register_default_retail_pack(self) -> None:
        """Built-in default retail definitions if file is missing."""
        self.promise_types = {
            "discount": PromiseTypeDefinition(
                name="discount",
                field="discount_percent",
                unit="percent",
                rules=[
                    RuleDefinition(
                        id="RULE-DISC-MAX",
                        field="discount_percent",
                        operator="<=",
                        threshold=10.0,
                        action="block",
                        policy_clause_id="POL-DISC-01",
                        message="Discount 50% is above the maximum of 10%.",
                    )
                ],
            ),
            "delivery": PromiseTypeDefinition(
                name="delivery",
                field="delivery_days",
                unit="days",
                rules=[
                    RuleDefinition(
                        id="RULE-DELIV-MIN",
                        field="delivery_days",
                        operator=">=",
                        threshold=3.0,
                        action="block",
                        policy_clause_id="POL-DEL-01",
                        message="Delivery timeline below minimum required 3 days.",
                    )
                ],
            ),
            "refund_window": PromiseTypeDefinition(
                name="refund_window",
                field="refund_days",
                unit="days",
                rules=[
                    RuleDefinition(
                        id="RULE-REF-MAX",
                        field="refund_days",
                        operator="<=",
                        threshold=14.0,
                        action="block",
                        policy_clause_id="POL-REF-01",
                        message="Refund window exceeds maximum statutory 14 days.",
                    )
                ],
            ),
        }

    def get_promise_type(self, type_name: str) -> PromiseTypeDefinition | None:
        return self.promise_types.get(type_name)

    def evaluate_promise(
        self,
        promise_type: str,
        value: Any,
        fact_context: dict[str, Any] | None = None,
    ) -> tuple[str, str, str | None]:
        """Evaluates a promise against registry rules.
        
        Returns (verdict, reason, policy_clause_id).
        """
        pt = self.get_promise_type(promise_type)
        if not pt:
            return "allow", "Unregulated promise type.", None

        for rule in pt.rules:
            compliant, reason = rule.evaluate(value, fact_context)
            if not compliant:
                return rule.action, reason, rule.policy_clause_id

        return "allow", "All rules passed.", None


# Global registry singleton
default_registry = PromiseRegistry()
