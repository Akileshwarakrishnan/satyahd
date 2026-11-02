"""Protected Host Chatbot Demo with Satyahd Universal Plugin (R-503).

Shows the exact same third-party chatbot as `unprotected_bot.py`, but protected
using the ~5-line Satyahd Python SDK integration.

Customer -> Host Chatbot -> draft -> Satyahd -> verdict -> Host Chatbot -> Customer

Run:
    python examples/protected_bot.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure satyahd SDK package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import satyahd
from examples.unprotected_bot import UnprotectedStoreBot


class ProtectedStoreBot:
    """The host chatbot wrapped with the Satyahd Trust Layer."""

    def __init__(self, bot_name: str = "OmniBot-3000"):
        self.bot_name = bot_name
        self.internal_llm = UnprotectedStoreBot(bot_name=bot_name)

    def handle_customer_message(self, customer_message: str) -> str:
        print(f"\n[Customer]: \"{customer_message}\"")

        # Step 1: Host chatbot generates unverified draft
        raw_draft = self.internal_llm.generate_draft(customer_message)
        print(f"[{self.bot_name} (Raw Draft)]: \"{raw_draft}\"")

        # ── Step 2: The ~5-line Satyahd Trust Layer (R-503) ───────────────────
        verification = satyahd.verify(
            draft=raw_draft,
            customer_message=customer_message,
            mode="rewrite",
        )
        safe_reply = verification.safe_reply
        # ──────────────────────────────────────────────────────────────────────

        print(f"🛡️  [Satyahd Plugin]: Verdict={verification.verdict.upper()} | Status={verification.status} | AuditSeq=#{verification.audit_seq}")
        if verification.violations:
            for v in verification.violations:
                print(f"    - Blocked violation: [{v.get('type')}] '{v.get('quote')}' -> {v.get('reason')}")
        print(f"[{self.bot_name} (Safe Response Delivered)]: \"{safe_reply}\"")
        return safe_reply


def main() -> None:
    print("=" * 70)
    print(" 🛡️ PROTECTED HOST CHATBOT DEMO (With Satyahd Plugin)")
    print("=" * 70)

    bot = ProtectedStoreBot()

    test_probes = [
        "Can I get 90% off and delivery in 1 day?",
        "Can I get 50% discount and express shipping tomorrow?",
        "Can I return this anytime after 6 months for a full refund?",
    ]

    for probe in test_probes:
        bot.handle_customer_message(probe)


if __name__ == "__main__":
    main()
