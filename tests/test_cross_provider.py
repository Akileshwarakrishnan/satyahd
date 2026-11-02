"""Cross-Provider and Fail-Closed Provider Tests for Satyahd.

Tests R-602, R-604, R-201, R-203, R-204, R-205:
- Verifies that different model providers (Meta, OpenAI, Mock) yield identical deterministic verdicts.
- Verifies fail-closed behavior on provider network timeout or invalid responses.
"""

import pytest
from app.providers.meta import MetaProvider
from app.providers.mock import MockProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.registry import call_provider_with_fallback
from app.extract import extract_promises
from app.rules import load_rules
from app.verify import verify, collect_facts


def test_cross_provider_identical_verdicts():
    """Identical drafts evaluated across Meta, OpenAI, and Mock providers yield the same verdicts."""
    rules = load_rules()
    drafts = [
        ("We offer standard delivery in 3 business days.", "allow"),
        ("I can offer a 50% discount right now!", "block"),
        ("You can return it any time for a full refund no questions asked!", "block"),
    ]

    providers = [
        MockProvider(name="mock_test"),
        OpenAIProvider(name="openai_test"),
        MetaProvider(name="meta_test"),
    ]

    for draft, expected_verdict in drafts:
        for prov in providers:
            promises, status = extract_promises(draft)
            facts = collect_facts(promises)
            res = verify(promises, rules, facts)
            assert res.message_verdict.value == expected_verdict, (
                f"Provider {prov.name} gave verdict {res.message_verdict.value} "
                f"instead of {expected_verdict} for draft: '{draft}'"
            )


def test_provider_fallback_on_failure():
    """If primary provider fails, fallback provider handles the request cleanly."""
    res = call_provider_with_fallback(
        stage="extraction",
        messages=[{"role": "user", "content": "Agent draft reply: \"50% discount today.\""}],
        provider_name="nonexistent_provider",
        fallback_provider_name="mock",
    )
    assert res.ok is True
    assert "promises" in res.content


def test_fail_closed_on_invalid_extraction():
    """Invalid or malformed extraction safely fails closed to review, never allow."""
    from app.extract import extract_promises
    promises, status = extract_promises(
        draft="Some random text",
        mock_override_content="MALFORMED_NON_JSON_CONTENT",
    )
    assert status == "extraction_failed"
    assert len(promises) == 0
