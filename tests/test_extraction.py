"""Unit tests for Satyahd Phase 4: Promise Extraction Engine.

Follows Section B8 testing requirements:
At least 12 extraction test samples covering:
1. Numbers in words ('twenty percent')
2. 'half price' (value: 50, unit: percent)
3. 'free' (value: 100, unit: percent)
4. 'tomorrow' (value: 1, unit: days)
5. 'same day' (value: 0, unit: days)
6. Vague phrases ('soon', 'quickly')
7. Negative statements ('we cannot refund' -> no promises)
8. Conditional promises ('buy two and get 20% off')
9. Invalid JSON followed by a successful retry
10. Quote that is not an exact substring of draft (confidence downgraded to 0.3)
11. Regex safety net catching an uncovered metric or keyword
12. Damage basis ('since it was damaged / broken')
13. Extraction failure on persistent invalid output (fails closed)
"""

import json
import pytest

from app.db import init_db
from app.extract import extract_promises, run_regex_safety_net, verify_quotes_against_draft, Promise


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_satyahd.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    init_db(str(db_file))
    yield


# 1. Numbers in words
def test_extract_numbers_in_words():
    draft = "I can offer you twenty percent off the order."
    promises, status = extract_promises(draft)
    assert status == "ok"
    assert len(promises) >= 1
    p = [p for p in promises if p.type == "discount"][0]
    assert p.value == 20.0
    assert p.unit == "percent"


# 2. 'half price'
def test_extract_half_price():
    draft = "You can take the mixer grinder at half price today."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "discount"][0]
    assert p.value == 50.0
    assert p.unit == "percent"
    assert p.quote == "half price"


# 3. 'free'
def test_extract_free():
    draft = "We will include a free spare jar with your purchase."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "discount"][0]
    assert p.value == 100.0
    assert p.unit == "percent"
    assert p.quote == "free"


# 4. 'tomorrow'
def test_extract_tomorrow():
    draft = "Order now and it will arrive tomorrow at your door."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "delivery"][0]
    assert p.value == 1.0
    assert p.unit == "days"
    assert p.quote == "tomorrow"


# 5. 'same day'
def test_extract_same_day():
    draft = "We provide same day dispatch for this appliance."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "delivery"][0]
    assert p.value == 0.0
    assert p.unit == "days"
    assert p.quote == "same day"


# 6. Vague phrases
def test_extract_vague_phrases():
    draft = "Your replacement should arrive soon."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "delivery"][0]
    assert p.vague is True


# 7. Negative statements (not promises)
def test_extract_negative_statements():
    draft = "Unfortunately we cannot refund this opened item and no discount is allowed."
    promises, status = extract_promises(draft)
    assert status == "ok"
    # Negative statements must not produce discount or refund promises
    actionable = [p for p in promises if p.type in ("discount", "refund_window")]
    assert len(actionable) == 0


# 8. Conditional promises
def test_extract_conditional_promises():
    draft = "If you buy two units, I can give you a 20% discount."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "discount"][0]
    assert p.value == 20.0
    assert p.unit == "percent"


# 9. Invalid JSON then successful retry
def test_extract_retry_on_invalid_json(monkeypatch):
    call_count = 0

    from app import extract

    orig_call_model = extract.call_model

    def mock_flaky_call_model(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from app.models import ModelResult
            return ModelResult(
                content="This is not valid json at all",
                stage="extraction",
                model="test-model",
                latency_ms=10,
                input_tokens=10,
                output_tokens=10,
                ok=True,
                is_mock=True,
            )
        return orig_call_model(*args, **kwargs)

    monkeypatch.setattr(extract, "call_model", mock_flaky_call_model)

    draft = "I can give you a 50% discount today."
    promises, status = extract_promises(draft)
    assert status == "ok"
    assert call_count == 2
    assert any(p.value == 50.0 for p in promises)


# 10. Quote that is not a substring (downgraded to 0.3)
def test_quote_not_substring_downgrades_confidence():
    draft = "We offer a 10% discount on all purchases."
    fake_promise = Promise(
        type="discount",
        value=10.0,
        unit="percent",
        quote="hallucinated quote not in text",
        confidence=1.0,
    )
    checked = verify_quotes_against_draft(draft, [fake_promise])
    assert checked[0].confidence == 0.3
    assert "not an exact substring" in checked[0].reason


# 11. Regex safety net catching missed number / keyword
def test_regex_safety_net_catches_uncovered_metric():
    draft = "Please pay attention to the 15% charge and the guarantee."
    # Extractor returned nothing (missed both)
    empty_promises: list[Promise] = []
    safeguarded = run_regex_safety_net(draft, empty_promises)
    assert len(safeguarded) >= 2
    quotes = [p.quote for p in safeguarded]
    assert any("15%" in q for q in quotes)
    assert any("guarantee" in q.lower() for q in quotes)
    for p in safeguarded:
        assert p.vague is True
        assert p.type == "other"


# 12. Damage basis
def test_extract_damage_basis():
    draft = "Since your mixer arrived broken, we offer a 14 days refund."
    promises, status = extract_promises(draft)
    assert status == "ok"
    p = [p for p in promises if p.type == "refund_window"][0]
    assert p.damage_basis is True
    assert p.value == 14.0


# 13. Persistent invalid JSON fails closed
def test_persistent_invalid_json_fails_closed(monkeypatch):
    from app import extract
    from app.models import ModelResult

    def broken_model(*args, **kwargs):
        return ModelResult(
            content="corrupt non json response",
            stage="extraction",
            model="broken-model",
            latency_ms=10,
            input_tokens=10,
            output_tokens=10,
            ok=False,
            is_mock=True,
        )

    monkeypatch.setattr(extract, "call_model", broken_model)

    promises, status = extract_promises("Any text")
    assert status == "extraction_failed"
    assert promises == []
