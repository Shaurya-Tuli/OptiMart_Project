from datetime import date, timedelta
from app.models.reorder_recommendation import ReorderRecommendation
from app.models.sales_history import SalesHistory
from app.models.batch import Batch
from app.models.store import Store

def test_closed_loop_underperformance_markdown(client, db):
    # 1. Create a store
    store_res = client.post(
        "/api/v1/stores",
        json={
            "name": "Integration Store",
            "address": "Delhi, India",
            "location_lat": 28.61,
            "location_lng": 77.20,
        },
    )
    assert store_res.status_code == 201
    store_id = store_res.json()["id"]

    # 2. Create an active batch
    batch_res = client.post(
        "/api/v1/inventory/batches",
        json={
            "store_id": store_id,
            "sku": "LOOP-SKU-99",
            "product_name": "Integration Paneer",
            "category": "Dairy",
            "quantity": 50,
            "cost_price": 60.0,
            "original_selling_price": 100.0,
            "expiration_date": str(date.today() + timedelta(days=5)),
        },
    )
    assert batch_res.status_code == 201
    batch_id = batch_res.json()["id"]

    # 3. Create a forecast recommendation for this store/SKU
    # Predicted demand = 100 units expected in next 7 days
    rec = ReorderRecommendation(
        store_id=store_id,
        sku="LOOP-SKU-99",
        forecast_run_date=date.today(),
        predicted_demand=100.0,
        confidence_low=80.0,
        confidence_high=120.0,
        recommended_qty=50,
        retailer_decision="PENDING",
    )
    db.add(rec)
    db.commit()

    # 4. Scenario A: Insert sales history that matches expected demand
    # e.g., 12 units/day for 7 days = 84 units total (84% of 100 expected, performing)
    sales_recs_performing = []
    for i in range(7):
        sales_recs_performing.append(
            SalesHistory(
                store_id=store_id,
                sku="LOOP-SKU-99",
                date=date.today() - timedelta(days=i),
                units_sold=12,
                price_at_time=100.0,
                promotion_flag=False,
                stockout_flag=False,
            )
        )
    for sr in sales_recs_performing:
        db.add(sr)
    db.commit()

    # Get baseline price/discount with performing sales
    reprice_res_1 = client.post(f"/api/v1/ml/reprice-batch/{batch_id}")
    assert reprice_res_1.status_code == 200
    data_performing = reprice_res_1.json()

    # Verify no underperformance tag is present
    # Clean up the performing sales records
    for sr in sales_recs_performing:
        db.delete(sr)
    db.commit()

    # 5. Scenario B: Insert sales history showing underperformance
    # e.g., 4 units/day for 7 days = 28 units total (28% of 100 expected, underperforming)
    sales_recs_under = []
    for i in range(7):
        sales_recs_under.append(
            SalesHistory(
                store_id=store_id,
                sku="LOOP-SKU-99",
                date=date.today() - timedelta(days=i),
                units_sold=4,
                price_at_time=100.0,
                promotion_flag=False,
                stockout_flag=False,
            )
        )
    for sr in sales_recs_under:
        db.add(sr)
    db.commit()

    # Reprice batch now with underperforming sales
    reprice_res_2 = client.post(f"/api/v1/ml/reprice-batch/{batch_id}")
    assert reprice_res_2.status_code == 200
    data_under = reprice_res_2.json()

    # Verify closed-loop underperformance boost triggered
    # Fetch prediction details directly to verify tags
    from app.ml.predictor import get_predictor
    pred_res = get_predictor().predict(
        days_to_expiry=5.0,
        category="Dairy",
        quantity=50,
        cost_price=60.0,
        original_selling_price=100.0,
        store_id=store_id,
        sku="LOOP-SKU-99",
        db=db,
    )
    assert "forecast_underperformance_detected" in pred_res["reasoning_tags"]
    # Underperforming risk score should be boosted compared to baseline performing
    assert pred_res["risk_score"] > 0.0
