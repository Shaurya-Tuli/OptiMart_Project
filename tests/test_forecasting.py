import pytest
from datetime import date, timedelta
from app.ml.forecaster import DemandForecaster, get_forecaster
from app.models.sales_history import SalesHistory
from app.schemas.sales_history import SalesHistoryCreate
from app.services.sales_history import bulk_upsert_sales_history


def test_forecaster_cold_start(db):
    forecaster = DemandForecaster(artifact_path="/tmp/test_forecaster.joblib")
    pred = forecaster.predict_demand(
        db=db,
        store_id=999,
        sku="NON-EXISTENT-SKU",
        category="Dairy",
    )
    assert pred["is_cold_start"] is True
    assert pred["predicted_demand_next_7d"] > 0
    assert pred["confidence_low"] < pred["confidence_high"]
    assert "Category baseline fallback (cold start)" in pred["top_factors"]


def test_forecaster_training_and_prediction(db):
    # Seed 30 days of sales history for store 1, SKU-TEST
    base_date = date(2026, 6, 1)
    records = []
    for i in range(30):
        records.append(
            SalesHistoryCreate(
                store_id=1,
                sku="SKU-TEST",
                date=base_date + timedelta(days=i),
                units_sold=20 + (i % 5) * 5,
                price_at_time=50.0,
                promotion_flag=(i % 7 == 0),
                stockout_flag=False,
            )
        )
    bulk_upsert_sales_history(db, records)

    forecaster = DemandForecaster(artifact_path="/tmp/test_forecaster.joblib")
    train_res = forecaster.train(db)

    assert train_res["status"] == "success"
    assert train_res["samples_trained"] > 0
    assert "baseline_mae" in train_res
    assert "model_mae" in train_res

    # Test prediction with trained model
    pred = forecaster.predict_demand(
        db=db,
        store_id=1,
        sku="SKU-TEST",
        category="Dairy",
        promotion_flag=True,
    )

    assert pred["is_cold_start"] is False
    assert pred["predicted_demand_next_7d"] > 0
    assert pred["confidence_low"] <= pred["predicted_demand_next_7d"]
    assert pred["confidence_high"] >= pred["predicted_demand_next_7d"]
    assert len(pred["top_factors"]) > 0


def test_forecasting_api_endpoints(client, db):
    # Seed at least 30 days of sales history via bulk API
    from datetime import date, timedelta
    base_date = date(2026, 5, 1)
    records = []
    for i in range(40):
        records.append({
            "store_id": 1,
            "sku": "SKU-API-FORECAST",
            "date": str(base_date + timedelta(days=i)),
            "units_sold": 25 + (i % 6) * 4,
            "price_at_time": 80.0,
            "promotion_flag": (i % 10 == 0),
            "stockout_flag": False,
        })

    bulk_res = client.post("/api/v1/sales-history/bulk", json={"records": records})
    assert bulk_res.status_code == 201

    # Reset forecaster singleton so it uses the fresh test DB
    import app.ml.forecaster as fm
    fm.forecaster_instance = None

    # Train endpoint
    train_res = client.post("/api/v1/forecast/train")
    assert train_res.status_code == 200
    assert train_res.json()["status"] == "success"

    # Predict endpoint — cold start since SKU has no history beyond store_id=1
    predict_res = client.get("/api/v1/forecast/predict?store_id=1&sku=SKU-API-FORECAST&category=General")
    assert predict_res.status_code == 200
    data = predict_res.json()
    assert "predicted_demand_next_7d" in data
    assert "confidence_low" in data
    assert "confidence_high" in data
    assert "top_factors" in data
