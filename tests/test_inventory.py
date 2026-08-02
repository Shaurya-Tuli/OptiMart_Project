import io
from datetime import date, timedelta


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "healthy" in data


def test_store_crud(client):
    # 1. Create store
    payload = {
        "name": "OptiMart Downtown Store",
        "address": "123 Main St, Tech City",
        "location_lat": 37.7749,
        "location_lng": -122.4194,
    }
    create_res = client.post("/api/v1/stores", json=payload)
    assert create_res.status_code == 201
    store_data = create_res.json()
    assert store_data["name"] == payload["name"]
    store_id = store_data["id"]

    # 2. Get store
    get_res = client.get(f"/api/v1/stores/{store_id}")
    assert get_res.status_code == 200
    assert get_res.json()["address"] == payload["address"]

    # 3. List stores
    list_res = client.get("/api/v1/stores")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Update store
    update_res = client.put(
        f"/api/v1/stores/{store_id}", json={"name": "OptiMart Flagship Store"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "OptiMart Flagship Store"

    # 5. Delete store
    del_res = client.delete(f"/api/v1/stores/{store_id}")
    assert del_res.status_code == 204

    # 6. Verify 404 after delete
    get_after_del = client.get(f"/api/v1/stores/{store_id}")
    assert get_after_del.status_code == 404


def test_batch_crud(client):
    # Setup store first
    store_res = client.post(
        "/api/v1/stores",
        json={"name": "Store 1", "address": "456 Market St"},
    )
    store_id = store_res.json()["id"]

    today = date.today()
    exp_date = (today + timedelta(days=5)).isoformat()

    # 1. Create Batch
    batch_payload = {
        "store_id": store_id,
        "sku": "MILK-001",
        "product_name": "Organic Whole Milk 1L",
        "category": "Dairy",
        "quantity": 50,
        "cost_price": 2.50,
        "original_selling_price": 4.99,
        "expiration_date": exp_date,
        "discount_percentage": 20.0,
        "status": "ACTIVE",
    }
    create_res = client.post("/api/v1/inventory/batches", json=batch_payload)
    assert create_res.status_code == 201
    batch_data = create_res.json()
    assert batch_data["sku"] == "MILK-001"
    # current_price should be calculated as 4.99 * (1 - 0.20) = 3.992
    assert abs(batch_data["current_price"] - 3.992) < 0.001
    batch_id = batch_data["id"]

    # 2. Get Batch
    get_res = client.get(f"/api/v1/inventory/batches/{batch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["product_name"] == "Organic Whole Milk 1L"

    # 3. Filter Batches
    filter_res = client.get(
        f"/api/v1/inventory/batches?store_id={store_id}&category=Dairy&status=ACTIVE"
    )
    assert filter_res.status_code == 200
    assert len(filter_res.json()) == 1

    # 4. Update Batch
    update_res = client.put(
        f"/api/v1/inventory/batches/{batch_id}",
        json={"quantity": 40, "discount_percentage": 30.0},
    )
    assert update_res.status_code == 200
    assert update_res.json()["quantity"] == 40

    # 5. Delete Batch
    del_res = client.delete(f"/api/v1/inventory/batches/{batch_id}")
    assert del_res.status_code == 204


def test_csv_upload(client):
    # Create a store first
    store_res = client.post("/api/v1/stores", json={"name": "CSV Store"})
    store_id = store_res.json()["id"]

    exp_date = (date.today() + timedelta(days=10)).isoformat()

    csv_data = f"""store_id,sku,product_name,category,quantity,cost_price,original_selling_price,current_price,expiration_date,discount_percentage,status
{store_id},YOGURT-100,Greek Yogurt 500g,Dairy,20,1.20,2.99,,{exp_date},10,ACTIVE
{store_id},BREAD-200,Sourdough Bread,Bakery,15,0.80,3.50,2.50,{exp_date},0,ACTIVE
9999,INVALID-SKU,Nonexistent Store Item,General,5,1.00,2.00,,{exp_date},0,ACTIVE
"""

    file_obj = io.BytesIO(csv_data.encode("utf-8"))

    response = client.post(
        "/api/v1/inventory/upload-csv",
        files={"file": ("inventory.csv", file_obj, "text/csv")},
    )

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_processed"] == 3
    assert summary["successfully_imported"] == 2
    assert summary["failed_rows"] == 1
    assert len(summary["errors"]) == 1
    assert "Store ID 9999 does not exist" in summary["errors"][0]
