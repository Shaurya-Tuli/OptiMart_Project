"""Phase 6 tests: Multi-rail Payments (Razorpay, Stripe & Subsidized Payment Bypass)."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.store import Store
from app.models.batch import Batch
from app.models.claim import Claim, generate_claim_token
from app.services.payment import (
    create_razorpay_order,
    create_stripe_session,
    verify_razorpay_webhook,
    verify_stripe_webhook,
)

client = TestClient(app)


def test_create_razorpay_checkout_session(db_session: Session):
    store = Store(name="Payment Store 1", location_lat=40.0, location_lng=-74.0)
    db_session.add(store)
    db_session.commit()

    batch = Batch(
        store_id=store.id,
        sku="PAY-RAZOR-001",
        product_name="Organic Milk",
        category="Dairy",
        quantity=5,
        cost_price=1.0,
        original_selling_price=4.0,
        current_price=2.0,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(batch)
    db_session.commit()

    claim = Claim(
        batch_id=batch.id,
        claim_token=generate_claim_token(),
        reserved_quantity=2,
        status="RESERVED",
        is_subsidized=False,
    )
    db_session.add(claim)
    db_session.commit()

    res = client.post(
        "/api/v1/payments/checkout-session",
        json={
            "claim_token": claim.claim_token,
            "provider": "razorpay",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "razorpay"
    assert "checkout_url" in data
    assert data["amount_paise"] == 400  # 2.0 * 2 * 100 paise


def test_create_stripe_checkout_session(db_session: Session):
    store = Store(name="Payment Store 2", location_lat=40.0, location_lng=-74.0)
    db_session.add(store)
    db_session.commit()

    batch = Batch(
        store_id=store.id,
        sku="PAY-STRIPE-001",
        product_name="Fresh Salad Box",
        category="Produce",
        quantity=10,
        cost_price=2.0,
        original_selling_price=8.0,
        current_price=4.5,
        expiration_date=date.today() + timedelta(days=1),
        status="ACTIVE",
    )
    db_session.add(batch)
    db_session.commit()

    claim = Claim(
        batch_id=batch.id,
        claim_token=generate_claim_token(),
        reserved_quantity=1,
        status="RESERVED",
        is_subsidized=False,
    )
    db_session.add(claim)
    db_session.commit()

    res = client.post(
        "/api/v1/payments/checkout-session",
        json={
            "claim_token": claim.claim_token,
            "provider": "stripe",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "stripe"
    assert "checkout_url" in data
    assert data["amount_cents"] == 450  # $4.50 = 450 cents


def test_subsidized_ngo_payment_bypass(db_session: Session):
    """Subsidized NGO claims should bypass payment completely and automatically set status to PAID."""
    store = Store(name="NGO Store", location_lat=40.0, location_lng=-74.0)
    db_session.add(store)
    db_session.commit()

    batch = Batch(
        store_id=store.id,
        sku="PAY-NGO-001",
        product_name="Subsidized Rice Bag",
        category="Grains",
        quantity=20,
        cost_price=5.0,
        original_selling_price=10.0,
        current_price=0.0,
        expiration_date=date.today() + timedelta(days=2),
        status="DISCOUNTED",
    )
    db_session.add(batch)
    db_session.commit()

    claim = Claim(
        batch_id=batch.id,
        claim_token=generate_claim_token(),
        reserved_quantity=5,
        status="RESERVED",
        is_subsidized=True,
    )
    db_session.add(claim)
    db_session.commit()

    res = client.post(
        "/api/v1/payments/checkout-session",
        json={"claim_token": claim.claim_token, "provider": "razorpay"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "subsidized_bypass"

    # Verify claim status updated in DB
    db_session.refresh(claim)
    assert claim.status == "PAID"
    assert claim.payment_ref == "SUBSIDIZED_BYPASS"


def test_razorpay_webhook_updates_claim(db_session: Session):
    store = Store(name="Webhook Store 1", location_lat=40.0, location_lng=-74.0)
    db_session.add(store)
    db_session.commit()

    batch = Batch(
        store_id=store.id,
        sku="WEBHOOK-001",
        product_name="Canned Beans",
        category="Pantry",
        quantity=10,
        cost_price=0.5,
        original_selling_price=2.0,
        current_price=1.0,
        expiration_date=date.today() + timedelta(days=3),
        status="ACTIVE",
    )
    db_session.add(batch)
    db_session.commit()

    token = generate_claim_token()
    claim = Claim(
        batch_id=batch.id,
        claim_token=token,
        reserved_quantity=2,
        status="PENDING_PAYMENT",
    )
    db_session.add(claim)
    db_session.commit()

    webhook_payload = {
        "event": "payment.captured",
        "claim_token": token,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_rzp_mock_12345",
                    "notes": {"claim_token": token},
                }
            }
        },
    }

    with patch("app.services.reservation.redis.from_url") as mock_redis:
        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        mock_r.delete.return_value = 1

        res = client.post(
            "/api/v1/payments/webhooks/razorpay",
            json=webhook_payload,
            headers={"x-razorpay-signature": "mock_sig"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "PAID"

        db_session.refresh(claim)
        assert claim.status == "PAID"
        assert claim.payment_ref == "pay_rzp_mock_12345"


def test_stripe_webhook_updates_claim(db_session: Session):
    store = Store(name="Webhook Store 2", location_lat=40.0, location_lng=-74.0)
    db_session.add(store)
    db_session.commit()

    batch = Batch(
        store_id=store.id,
        sku="WEBHOOK-002",
        product_name="Orange Juice",
        category="Beverages",
        quantity=6,
        cost_price=1.0,
        original_selling_price=3.5,
        current_price=2.0,
        expiration_date=date.today() + timedelta(days=2),
        status="ACTIVE",
    )
    db_session.add(batch)
    db_session.commit()

    token = generate_claim_token()
    claim = Claim(
        batch_id=batch.id,
        claim_token=token,
        reserved_quantity=1,
        status="PENDING_PAYMENT",
    )
    db_session.add(claim)
    db_session.commit()

    webhook_payload = {
        "type": "checkout.session.completed",
        "claim_token": token,
        "data": {
            "object": {
                "id": "cs_stripe_mock_67890",
                "payment_intent": "pi_stripe_mock_999",
                "metadata": {"claim_token": token},
            }
        },
    }

    with patch("app.services.reservation.redis.from_url") as mock_redis:
        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        mock_r.delete.return_value = 1

        res = client.post(
            "/api/v1/payments/webhooks/stripe",
            json=webhook_payload,
            headers={"stripe-signature": "mock_sig"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "PAID"

        db_session.refresh(claim)
        assert claim.status == "PAID"
        assert claim.payment_ref == "pi_stripe_mock_999"
