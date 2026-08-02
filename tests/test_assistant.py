import pytest
from app.api.assistant import _detect_intent, _build_response, ChatMessage, ChatRequest
from app.models.batch import Batch
from datetime import date

def test_detect_intent():
    intent, cat = _detect_intent("hello there!")
    assert intent == "greeting"
    assert cat is None

    intent, cat = _detect_intent("show me some discounts")
    assert intent == "browse_discounts"
    assert cat is None

    intent, cat = _detect_intent("do you have dairy or milk products?")
    assert intent == "search_category"
    assert cat == "Dairy"

    intent, cat = _detect_intent("how do I claim an item?")
    assert intent == "claim_guide"
    assert cat is None

    intent, cat = _detect_intent("is near-expiry food safe to eat?")
    assert intent == "expiry_faq"
    assert cat is None

    intent, cat = _detect_intent("what payments do you accept?")
    assert intent == "payment_faq"
    assert cat is None

    intent, cat = _detect_intent("help me")
    assert intent == "help"
    assert cat is None


def test_build_response():
    # Empty products
    res = _build_response("greeting", None, [], "hi")
    assert "OptiMart" in res.reply
    assert len(res.products) == 0

    # Greeting with a batch
    mock_batch = Batch(
        id=999,
        store_id=1,
        sku="TEST-SKU",
        product_name="Test Milk",
        category="Dairy",
        quantity=5,
        cost_price=10.0,
        original_selling_price=20.0,
        current_price=15.0,
        expiration_date=date.today(),
        discount_percentage=25.0,
        status="DISCOUNTED"
    )

    res = _build_response("greeting", None, [mock_batch], "hi")
    assert "1 deals" in res.reply
    assert len(res.products) == 1
    assert res.products[0].product_name == "Test Milk"
    assert res.products[0].discount_percentage == 25.0
