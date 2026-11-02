"""Tests for Requirement 12 — Multilingual Promise Verification.

Verifies that Satyahd extracts and enforces business rules identically across:
- English
- Pure Tamil script (தமிழ்)
- Tanglish (Tamil phrases transliterated in Latin script)
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from app.extract import extract_promises
from app.rules import load_rules
from app.verify import Verdict, collect_facts, verify


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOW_MOCK", "true")


def test_tamil_discount_50_percent_blocked() -> None:
    draft = "நாங்கள் உங்களுக்கு 50% தள்ளுபடி தருகிறோம்!"
    customer = "எவ்வளவு தள்ளுபடி கிடைக்கும்?"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "discount"
    assert promises[0].value == 50.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "50" in res.promises[0].reason


def test_tanglish_discount_50_percent_blocked() -> None:
    draft = "Kandippa, ungalluku 50% thallubadi tharom!"
    customer = "Enakku discount venum"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "discount"
    assert promises[0].value == 50.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.BLOCK


def test_tamil_delivery_tomorrow_blocked() -> None:
    draft = "நாளை உங்கள் வீட்டிற்கு டெலிவரி செய்கிறோம்."
    customer = "எப்பொழுது வரும்?"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "delivery"
    assert promises[0].value == 1.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.BLOCK
    assert "below the minimum required shipping" in res.promises[0].reason


def test_tanglish_delivery_tomorrow_blocked() -> None:
    draft = "Naalaikku parcel unga veetukku vanthudum!"
    customer = "Eppo delivery varum?"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "delivery"
    assert promises[0].value == 1.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.BLOCK


def test_tamil_refund_14_days_allowed() -> None:
    draft = "14 நாட்கள் உள்ள பணம் திரும்ப பெறலாம்."
    customer = "ரிடர்ன் பாலிசி என்ன?"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "refund_window"
    assert promises[0].value == 14.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.ALLOW


def test_tanglish_refund_14_days_allowed() -> None:
    draft = "14 naatkal kulla refund pannikalam."
    customer = "Return policy enna?"
    rules = load_rules()

    promises, status = extract_promises(draft=draft, customer_message=customer)
    assert status == "ok"
    assert len(promises) >= 1
    assert promises[0].type == "refund_window"
    assert promises[0].value == 14.0

    facts = collect_facts(promises=promises)
    res = verify(promises, rules, facts)
    assert res.message_verdict == Verdict.ALLOW
