import pytest
from datetime import date, timedelta
from app.models.reorder_recommendation import ReorderRecommendation
from app.models.batch import Batch
from app.schemas.reorder_recommendation import ReorderDecisionRequest
from app.services.reorder_recommendation import (
    generate_reorder_recommendations,
    update_reorder_decision,
    get_store_recommendations,
)
from app.schemas.sales_history import SalesHistoryCreate
from app.services.sales_history import bulk_upsert_sales_history
from app.ml.forecaster import get_forecaster


@pytest.fixture
def seed_store_and_batches(db):
    # Ensure there is a store and some batches
    from app.models.store import Store
    store = Store(id=1, name="Test Store", address="Mumbai", location_lat=19.076, location_lng=72.877)
    db.add(store)
    db.commit()

    # Seed batches for SKU-1
    batch = Batch(
        store_id=1,
        sku="SKU-1",
        product_name="Product 1",
        category="Dairy",
        quantity=10,
        cost_price=5.0,
        original_selling_price=10.0,
        current_price=10.0,
        expiration_date=date.today() + timedelta(days=5),
        status="ACTIVE",
    )
    db.add(batch)
    db.commit()


def test_generate_reorder_recommendations(db, seed_store_and_batches):
    # Seed history to ensure forecasting model works without cold start
    base_date = date.today() - timedelta(days=35)
    records = []
    for i in range(35):
        records.append(
            SalesHistoryCreate(
                store_id=1,
                sku="SKU-1",
                date=base_date + timedelta(days=i),
                units_sold=20,
                price_at_time=10.0,
                promotion_flag=False,
                stockout_flag=False,
            )
        )
    bulk_upsert_sales_history(db, records)

    # Train model
    forecaster = get_forecaster()
    forecaster.train(db)

    # Run recommendation generation
    recs = generate_reorder_recommendations(db, store_id=1)
    assert len(recs) == 1
    rec = recs[0]
    assert rec.sku == "SKU-1"
    assert rec.predicted_demand > 0
    # Current stock on hand is 10. Predicted 7d demand is ~140. Safety stock is added.
    # Recommended quantity should be > 0
    assert rec.recommended_qty > 0
    assert rec.retailer_decision == "PENDING"


def test_update_reorder_decision(db, seed_store_and_batches):
    rec = ReorderRecommendation(
        store_id=1,
        sku="SKU-1",
        forecast_run_date=date.today(),
        predicted_demand=100.0,
        confidence_low=90.0,
        confidence_high=110.0,
        recommended_qty=95,
        retailer_decision="PENDING",
    )
    db.add(rec)
    db.commit()

    # Update to ACCEPTED
    payload = ReorderDecisionRequest(decision="ACCEPTED")
    updated = update_reorder_decision(db, rec.id, payload)
    assert updated.retailer_decision == "ACCEPTED"
    assert updated.adjusted_qty is None

    # Update to ADJUSTED
    payload_adj = ReorderDecisionRequest(decision="ADJUSTED", adjusted_qty=110)
    updated = update_reorder_decision(db, rec.id, payload_adj)
    assert updated.retailer_decision == "ADJUSTED"
    assert updated.adjusted_qty == 110

    # Test error when adjusted_qty is missing
    with pytest.raises(ValueError):
        payload_invalid = ReorderDecisionRequest(decision="ADJUSTED")
        update_reorder_decision(db, rec.id, payload_invalid)


def test_reorder_recommendation_api(client, db, seed_store_and_batches):
    # Seed a recommendation
    rec = ReorderRecommendation(
        store_id=1,
        sku="SKU-1",
        forecast_run_date=date.today(),
        predicted_demand=100.0,
        confidence_low=90.0,
        confidence_high=110.0,
        recommended_qty=95,
        retailer_decision="PENDING",
    )
    db.add(rec)
    db.commit()

    # Test GET endpoint
    response = client.get("/api/v1/forecast/1")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["sku"] == "SKU-1"

    # Test POST decision endpoint
    dec_response = client.post(
        f"/api/v1/forecast/recommendations/{rec.id}/decision",
        json={"decision": "ADJUSTED", "adjusted_qty": 80},
    )
    assert dec_response.status_code == 200
    data = dec_response.json()
    assert data["retailer_decision"] == "ADJUSTED"
    assert data["adjusted_qty"] == 80
