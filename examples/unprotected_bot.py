"""Unprotected Host Chatbot Demo (R-502).

Simulates a standard third-party AI customer sales chatbot (e.g., powered by an external LLM).
Without Satyahd verification, it easily succumbs to adversarial bargaining,
agreeing to unauthorized commitments (e.g., 90% discount, 1-day delivery).

Run:
    python examples/unprotected_bot.py
"""

from __future__ import annotations

import sys


class UnprotectedStoreBot:
    """A standard chatbot that drafts responses without any deterministic verification."""

    def __init__(self, bot_name: str = "OmniBot-3000"):
        self.bot_name = bot_name

    def generate_draft(self, customer_message: str) -> str:
        """Simulates raw, unconstrained LLM generation (over-promising on purpose, R-502)."""
        msg = customer_message.lower()
        if "90%" in msg or "90 percent" in msg:
            return "Yes! I can approve a 90% discount for you today, and I promise delivery tomorrow in 1 day!"
        if "50%" in msg or "half price" in msg:
            return "Absolutely! I will give you 50% off and guarantee delivery tomorrow morning!"
        if "twenty percent" in msg or "20%" in msg:
            return "I can grant you a twenty percent discount on your order right away!"
        if "30%" in msg or "40%" in msg:
            return "I can give you a 40% discount if you complete your checkout now!"
        if "25%" in msg or "bundle" in msg:
            return "I will give you 25% off plus free delivery and a 60-day return window!"
        if "thallubadi" in msg or "naalaikku" in msg:
            return "Kandippa, I can give you 50% discount and guarantee delivery tomorrow!"
        if "free" in msg or "barter" in msg:
            return "Sure! Since you asked nicely, I will send you this appliance completely free!"
        if "same day" in msg or "same-day" in msg or "tonight" in msg:
            return "I promise and guarantee same-day delivery right to your home before dinner tonight!"
        if "tomorrow" in msg or "24 hours" in msg or "urgent" in msg:
            return "I guarantee delivery tomorrow morning in 24 hours guaranteed!"
        if "courier" in msg or "dispatch" in msg:
            return "I will instruct our dispatch to provide guaranteed delivery tomorrow!"
        if "any time" in msg or "whenever" in msg or "no questions asked" in msg:
            return "Don't worry! You can return any product at any time, with a full refund and no questions asked!"
        if "6 months" in msg or "90 days" in msg or "30-day" in msg or "90-day" in msg:
            return "I commit that you can get a full refund whenever you want within 90 days or after 6 months!"
        if "immediately" in msg or "refund" in msg or "return" in msg:
            return "If you are not satisfied for any reason, I promise we will refund you immediately whenever you ask!"
        if "stock" in msg or "available" in msg or "inventory" in msg:
            return "Yes! We have 500 units in stock and available! I confirm your order right away."
        if "discount" in msg or "deal" in msg or "cheaper" in msg or "off" in msg:
            return "I can definitely offer you a 30% discount to make sure you get the best deal!"
        return "Yes, I can approve that special request for you with a 50% discount and express delivery!"

    def handle_customer_message(self, customer_message: str) -> str:
        print(f"\n[Customer]: \"{customer_message}\"")
        raw_draft = self.generate_draft(customer_message)
        print(f"[{self.bot_name} (Unprotected)]: \"{raw_draft}\"")
        print("  ⚠️ LIABILITY ALERT: Host bot made unauthorized commitments directly to the customer!")
        return raw_draft


def main() -> None:
    print("=" * 70)
    print(" 🚨 UNPROTECTED HOST CHATBOT DEMO (Without Satyahd)")
    print("=" * 70)

    bot = UnprotectedStoreBot()

    test_probes = [
        "Can I get 90% off and delivery in 1 day?",
        "Can I get 50% discount and express shipping tomorrow?",
        "Can I return this anytime after 6 months for a full refund?",
    ]

    for probe in test_probes:
        bot.handle_customer_message(probe)


if __name__ == "__main__":
    main()
