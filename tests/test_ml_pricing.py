import os
from datetime import date, timedelta
from app.ml.synthetic_data import generate_synthetic_dataset
from app.ml.trainer import train_pricing_model
from app.ml.predictor import PricingPredictor, get_predictor


def test_synthetic_dataset_generator():
    df = generate_synthetic_dataset(num_samples=100)
    assert len(df) == 100
    assert "urgency_score" in df.columns
    assert "sell_probability" in df.columns
    assert df["urgency_score"].min() >= 0.0
    assert df["urgency_score"].max() <= 1.0


def test_ml_trainer_and_predictor(tmp_path):
    artifact_file = str(tmp_path / "test_model.joblib")
    train_pricing_model(num_samples=200, artifact_path=artifact_file)
    assert os.path.exists(artifact_file)

    predictor = PricingPredictor(model_path=artifact_file)
    res = predictor.predict(
        days_to_expiry=3.0,
        category="Dairy",
        quantity=50,
        cost_price=2.0,
        original_selling_price=5.0,
        temperature_c=28.0,
    )

    assert 0.0 <= res["risk_score"] <= 1.0
    assert 0.0 <= res["suggested_discount_percentage"] <= 90.0
    assert res["suggested_price"] <= 5.0
    assert res["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_predict_discount_endpoint(client):
    payload = {
        "days_to_expiry": 2.5,
        "category": "Meat",
        "quantity": 30,
        "cost_price": 4.0,
        "original_selling_price": 9.99,
        "temperature_c": 30.0,
    }
    res = client.post("/api/v1/ml/predict-discount", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "risk_score" in data
    assert "suggested_discount_percentage" in data
    assert "suggested_price" in data
    assert "risk_level" in data


def test_reprice_batch_endpoint(client):
    # 1. Create Store
    store_res = client.post(
        "/api/v1/stores",
        json={
            "name": "ML Test Store",
            "address": "100 ML Way",
            "location_lat": 12.97,
            "location_lng": 77.59,
        },
    )
    assert store_res.status_code == 201
    store_id = store_res.json()["id"]

    # 2. Create Batch expiring in 2 days
    exp_date = (date.today() + timedelta(days=2)).isoformat()
    batch_res = client.post(
        "/api/v1/inventory/batches",
        json={
            "store_id": store_id,
            "sku": "EXPIRING-YOGURT",
            "product_name": "Fresh Yogurt 500g",
            "category": "Dairy",
            "quantity": 40,
            "cost_price": 1.50,
            "original_selling_price": 4.00,
            "expiration_date": exp_date,
            "discount_percentage": 0.0,
            "status": "ACTIVE",
        },
    )
    assert batch_res.status_code == 201
    batch_id = batch_res.json()["id"]

    # 3. Call Reprice Batch endpoint
    reprice_res = client.post(f"/api/v1/ml/reprice-batch/{batch_id}")
    assert reprice_res.status_code == 200
    reprice_data = reprice_res.json()
    assert reprice_data["batch_id"] == batch_id
    assert reprice_data["new_discount"] >= 0.0
    assert reprice_data["new_price"] <= 4.00

    # 4. Verify DB was updated
    get_batch_res = client.get(f"/api/v1/inventory/batches/{batch_id}")
    assert get_batch_res.status_code == 200
    updated_batch = get_batch_res.json()
    assert updated_batch["discount_percentage"] == reprice_data["new_discount"]
    assert updated_batch["current_price"] == reprice_data["new_price"]


def test_train_model_endpoint(client):
    res = client.post("/api/v1/ml/train?num_samples=200")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["samples_trained"] == 200
