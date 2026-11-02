"""Store Adapter and Fact Lookup Tools for Satyahd.

Follows Section 3.5:
- StoreAdapter read-only interface (reads JSON files / SQLite)
- Functions: get_product, get_stock, get_order, get_policy, get_shipping
- Calculates days_since_order deterministically from settings.DEMO_TODAY
- Logs every tool call to the SQLite tool_calls table
- OpenAI-compatible tool specifications for Muse Spark tool calling
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from app.config import BASE_DIR, get_settings
from app.db import get_db
from app.rules import BusinessRules, load_rules

logger = logging.getLogger("satyahd.tools")

PRODUCTS_FILE = BASE_DIR / "data" / "products.json"
ORDERS_FILE = BASE_DIR / "data" / "orders.json"
POLICY_CLAUSES_FILE = BASE_DIR / "data" / "policy_clauses.json"


class StoreAdapter(Protocol):
    def get_product(self, product_ref: str) -> dict[str, Any] | None: ...
    def get_stock(self, product_id: str) -> int | None: ...
    def get_order(self, order_id: str) -> dict[str, Any] | None: ...
    def get_policy(self) -> dict[str, Any]: ...
    def get_shipping(self, product_id: str) -> int | None: ...
    def get_policy_clauses(self, topic: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]: ...


class FactConnector(Protocol):
    """Interface for external fact connectors (R-401)."""
    def get_fact(self, source: str, key: str) -> Any: ...


class MockFactConnector:
    """Mock fact connector for testing and demonstration (R-402, R-403)."""
    def __init__(self, fallback_to_review: bool = True):
        self.fallback_to_review = fallback_to_review
        self._facts: dict[str, dict[str, Any]] = {
            "inventory": {"PRD-101": 15, "PRD-102": 0, "PRD-103": 8},
            "shipping": {"PRD-101": 3, "PRD-102": 5, "PRD-103": 3},
            "customer_tier": {"CUST-001": "gold", "CUST-002": "standard"},
        }

    def get_fact(self, source: str, key: str) -> Any:
        source_data = self._facts.get(source)
        if not source_data or key not in source_data:
            if self.fallback_to_review:
                return None  # triggers fail-closed REVIEW
            raise KeyError(f"Fact '{key}' not found in source '{source}'")
        return source_data[key]


class JsonStoreAdapter:
    """Read-only adapter backed by JSON data files."""

    def __init__(
        self,
        products_file: Path | None = None,
        orders_file: Path | None = None,
        rules_file: Path | None = None,
        policy_clauses_file: Path | None = None,
    ):
        self.products_file = products_file or PRODUCTS_FILE
        self.orders_file = orders_file or ORDERS_FILE
        self.rules_file = rules_file
        self.policy_clauses_file = policy_clauses_file or POLICY_CLAUSES_FILE

    def _load_products(self) -> list[dict[str, Any]]:
        if not self.products_file.exists():
            return []
        try:
            return json.loads(self.products_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load products: %s", exc)
            return []

    def _load_orders(self) -> list[dict[str, Any]]:
        if not self.orders_file.exists():
            return []
        try:
            return json.loads(self.orders_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load orders: %s", exc)
            return []

    def _load_policy_clauses(self) -> list[dict[str, Any]]:
        if not self.policy_clauses_file.exists():
            return []
        try:
            return json.loads(self.policy_clauses_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("Failed to load policy clauses: %s", exc)
            return []

    def get_product(self, product_ref: str) -> dict[str, Any] | None:
        """Find product by id or case-insensitive substring of name."""
        if not product_ref:
            return None
        products = self._load_products()
        query = str(product_ref).strip().lower()

        # Exact ID match first
        for p in products:
            if p.get("id", "").lower() == query:
                return p

        # Substring in name
        for p in products:
            if query in p.get("name", "").lower():
                return p

        return None

    def get_stock(self, product_id: str) -> int | None:
        """Returns stock for product_id as a whole number."""
        product = self.get_product(product_id)
        if product is None:
            return None
        return int(product.get("stock", 0))

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        """Returns order with deterministic days_since_order based on DEMO_TODAY."""
        if not order_id:
            return None
        orders = self._load_orders()
        target = order_id.strip().lower()

        matched: dict[str, Any] | None = None
        for o in orders:
            if o.get("id", "").lower() == target:
                matched = dict(o)
                break

        if not matched:
            return None

        # Compute days_since_order deterministically
        settings = get_settings()
        try:
            demo_date = datetime.strptime(settings.DEMO_TODAY, "%Y-%m-%d").date()
            order_date = datetime.strptime(matched["order_date"], "%Y-%m-%d").date()
            matched["days_since_order"] = (demo_date - order_date).days
        except Exception as exc:
            logger.warning("Error calculating days_since_order: %s", exc)
            matched["days_since_order"] = None

        return matched

    def get_policy(self) -> dict[str, Any]:
        """Returns current business rules as a dictionary."""
        rules: BusinessRules = load_rules(self.rules_file)
        return rules.model_dump()

    def get_shipping(self, product_id: str) -> int | None:
        """Returns standard delivery days for product_id."""
        product = self.get_product(product_id)
        if product is None:
            # Fall back to policy standard shipping days
            policy = self.get_policy()
            return policy.get("standard_shipping_days", 3)
        return int(product.get("shipping_days", 3))

    def get_policy_clauses(self, topic: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
        """Returns relevant policy clauses filtered by topic or keyword."""
        clauses = self._load_policy_clauses()
        if not clauses:
            return []

        if not topic and not keyword:
            return clauses

        matched = []
        topic_lower = topic.strip().lower() if topic else None
        kw_lower = keyword.strip().lower() if keyword else None

        for c in clauses:
            c_topic = str(c.get("topic", "")).lower()
            c_text = (str(c.get("title", "")) + " " + str(c.get("clause", ""))).lower()

            # Match by topic
            if topic_lower and (topic_lower == c_topic or topic_lower in c_topic or c_topic in topic_lower):
                matched.append(c)
                continue

            # Match by keyword
            if kw_lower and kw_lower in c_text:
                matched.append(c)
                continue

        return matched if matched else clauses[:3]


# Default adapter instance
default_adapter = JsonStoreAdapter()


def log_tool_call(
    name: str,
    args: dict[str, Any] | str,
    result: Any,
    latency_ms: int,
    ok: bool,
    interaction_id: str | None = None,
) -> None:
    """Persists every tool call into the tool_calls SQLite table."""
    if not interaction_id:
        return
    try:
        call_id = f"tc_{uuid.uuid4().hex[:12]}"
        args_str = json.dumps(args) if not isinstance(args, str) else args
        result_str = json.dumps(result) if not isinstance(result, str) else result
        with get_db() as conn:
            exists = conn.execute("SELECT 1 FROM interactions WHERE id = ?", (interaction_id,)).fetchone()
            valid_int_id = interaction_id if exists else None
            conn.execute(
                """
                INSERT INTO tool_calls (id, interaction_id, name, args, result, latency_ms, ok)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    valid_int_id,
                    name,
                    args_str,
                    result_str,
                    latency_ms,
                    1 if ok else 0,
                ),
            )
    except Exception as exc:
        logger.error("Failed to log tool call: %s", exc)


def execute_tool(
    name: str,
    args: dict[str, Any],
    adapter: StoreAdapter | None = None,
    interaction_id: str | None = None,
) -> Any:
    """Executes a tool call against the adapter, measuring latency and logging results."""
    store = adapter or default_adapter
    start = time.perf_counter()
    ok = True
    result: Any = None

    try:
        if name == "get_product":
            result = store.get_product(args.get("product_ref", ""))
        elif name == "get_stock":
            result = store.get_stock(args.get("product_id", ""))
        elif name == "get_order":
            result = store.get_order(args.get("order_id", ""))
        elif name == "get_policy":
            result = store.get_policy()
        elif name == "get_shipping":
            result = store.get_shipping(args.get("product_id", ""))
        elif name == "get_policy_clauses":
            result = store.get_policy_clauses(
                topic=args.get("topic"),
                keyword=args.get("keyword"),
            )
        elif name in ("apply_discount", "issue_refund", "promise_delivery"):
            # Protected action tools routed through Satyahd Gateway (Section 1.1)
            from app.gateway import authorize_action
            decision = authorize_action(name, args, adapter=store, interaction_id=interaction_id)
            ok = decision.authorized
            result = decision.to_dict()
        else:
            ok = False
            result = f"Unknown tool: {name}"
    except Exception as exc:
        ok = False
        result = str(exc)
        logger.error("Error executing tool %s: %s", name, exc)

    latency_ms = int((time.perf_counter() - start) * 1000)
    log_tool_call(name, args, result, latency_ms, ok, interaction_id)
    return result


# Tool declarations for OpenAI/Meta tool calling API
STORE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "Look up product details (id, name, stock, shipping_days) by id or name substring.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ref": {"type": "string", "description": "Product ID or product name substring"}
                },
                "required": ["product_ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock",
            "description": "Check current available inventory stock units for a product ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Exact product ID (e.g. P1, P2)"}
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Look up customer order details including order status and days_since_order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID (e.g. O1001)"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": "Retrieve current authorized store business rules and return policies.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shipping",
            "description": "Retrieve standard delivery days for a product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID"}
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy_clauses",
            "description": "Retrieve relevant official store policy clauses by topic (discount, refund_window, delivery, stock, damage) or keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Policy category (discount, refund_window, delivery, stock, damage)"},
                    "keyword": {"type": "string", "description": "Search keyword in policy text"},
                },
            },
        },
    },
]

# Protected Action Tools intercepted by Satyahd Gateway (Section 1.1)
ACTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_discount",
            "description": "Protected Action Tool: Apply authorized percentage discount to customer order. Intercepted by Satyahd Gateway.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Customer order ID"},
                    "percent": {"type": "number", "description": "Discount percentage to apply (e.g. 10.0)"},
                },
                "required": ["percent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Protected Action Tool: Authorize monetary refund for an order. Intercepted by Satyahd Gateway.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID to refund"},
                    "amount": {"type": "number", "description": "Refund amount"},
                    "reason": {"type": "string", "description": "Reason for refund claim"},
                    "damage_photo": {"type": "boolean", "description": "Whether verified damage photo was provided"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "promise_delivery",
            "description": "Protected Action Tool: Schedule and commit delivery timeline for a product. Intercepted by Satyahd Gateway.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product ID being ordered"},
                    "days": {"type": "integer", "description": "Promised delivery days"},
                    "order_id": {"type": "string", "description": "Associated order ID"},
                },
                "required": ["product_id", "days"],
            },
        },
    },
]

ALL_TOOLS = STORE_TOOLS + ACTION_TOOLS
