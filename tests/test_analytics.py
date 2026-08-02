"""Phase 7 tests: Analytics Dashboard & Final System Hardening."""
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.store import Store
from app.models.batch import Batch
from app.models.claim import Claim, generate_claim_token
from app.models.standing_order import StandingOrder
from app.models.standing_order_match import StandingOrderMatch

client = TestClient(app)


def test_analytics_summary_empty_db(db_session: Session):
    res = client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert "waste_impact" in data
    assert "financial_impact" in data
    assert "standing_orders" in data
    assert data["waste_impact"]["total_batches_tracked"] == 0
    assert data["waste_impact"]["total_items_rescued"] == 0


def test_analytics_summary_populated_data(db_session: Session):
    store = Store(name="Analytics Store", location_lat=40.71, location_lng=-74.00)
    db_session.add(store)
    db_session.commit()

    b1 = Batch(
        store_id=store.id,
        sku="ANALYTICS-001",
        product_name="Greek Yogurt",
        category="Dairy",
        quantity=10,
        cost_price=1.0,
        original_selling_price=4.0,
        current_price=2.0,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(b1)
    db_session.commit()

    # Create a PAID claim for b1 (2 items rescued)
    c1 = Claim(
        batch_id=b1.id,
        claim_token=generate_claim_token(),
        reserved_quantity=2,
        status="PAID",
        payment_ref="pay_test_analytics",
    )
    db_session.add(c1)
    db_session.commit()

    # Create a Standing Order Match
    so = StandingOrder(
        ngo_name="Community Food Bank",
        contact_email="foodbank@example.org",
        category_filter="Dairy",
    )
    db_session.add(so)
    db_session.commit()

    match = StandingOrderMatch(
        standing_order_id=so.id,
        batch_id=b1.id,
        allocated_quantity=3,
        status="ALLOCATED",
    )
    db_session.add(match)
    db_session.commit()

    res = client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    data = res.json()

    waste = data["waste_impact"]
    assert waste["total_batches_tracked"] == 1
    assert waste["total_items_rescued"] == 2
    assert waste["total_waste_prevented_kg"] == 1.0  # 2 items * 0.5 kg
    assert waste["total_co2_saved_kg"] == 2.5        # 1.0 kg * 2.5

    fin = data["financial_impact"]
    assert fin["total_revenue_recovered"] == 4.0      # 2.0 * 2
    assert fin["total_discounts_given"] == 4.0        # (4.0 - 2.0) * 2

    so_metrics = data["standing_orders"]
    assert so_metrics["total_standing_orders"] == 1
    assert so_metrics["total_ngo_matches"] == 1
    assert so_metrics["total_subsidized_items_allocated"] == 3


def test_store_analytics_endpoint(db_session: Session):
    store = Store(name="Single Store Analytics", location_lat=40.71, location_lng=-74.00)
    db_session.add(store)
    db_session.commit()

    b1 = Batch(
        store_id=store.id,
        sku="STORE-ANALYTICS-001",
        product_name="Whole Milk 1L",
        category="Dairy",
        quantity=5,
        cost_price=1.0,
        original_selling_price=3.0,
        current_price=1.5,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(b1)
    db_session.commit()

    c1 = Claim(
        batch_id=b1.id,
        claim_token=generate_claim_token(),
        reserved_quantity=3,
        status="FULFILLED",
    )
    db_session.add(c1)
    db_session.commit()

    res = client.get(f"/api/v1/analytics/store/{store.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["store_id"] == store.id
    assert data["store_name"] == "Single Store Analytics"
    assert data["items_rescued"] == 3
    assert data["revenue_recovered"] == 4.5  # 1.5 * 3


def test_store_analytics_not_found():
    res = client.get("/api/v1/analytics/store/999999")
    assert res.status_code == 404
