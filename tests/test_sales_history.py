import io
import pytest
from datetime import date, timedelta
from app.models.sales_history import SalesHistory
from app.schemas.sales_history import SalesHistoryCreate
from app.services.sales_history import (
    create_sales_history_entry,
    bulk_upsert_sales_history,
    get_sales_history,
)


def test_create_sales_history_entry(db):
    payload = SalesHistoryCreate(
        store_id=1,
        sku="TEST-SKU-001",
        date=date(2026, 8, 1),
        units_sold=25,
        price_at_time=99.99,
        promotion_flag=False,
        stockout_flag=False,
    )
    entry = create_sales_history_entry(db, payload)
    assert entry is not None
    assert entry.store_id == 1
    assert entry.sku == "TEST-SKU-001"
    assert entry.units_sold == 25
    assert entry.price_at_time == 99.99


def test_bulk_upsert_and_get_sales_history(db):
    records = [
        SalesHistoryCreate(
            store_id=1,
            sku="TEST-SKU-BULK-1",
            date=date(2026, 7, 20),
            units_sold=30,
            price_at_time=50.0,
        ),
        SalesHistoryCreate(
            store_id=1,
            sku="TEST-SKU-BULK-2",
            date=date(2026, 7, 21),
            units_sold=40,
            price_at_time=45.0,
            promotion_flag=True,
        ),
    ]
    count = bulk_upsert_sales_history(db, records)
    assert count == 2

    results = get_sales_history(db, store_id=1, sku="TEST-SKU-BULK-1")
    assert len(results) >= 1
    assert results[0].units_sold == 30


def test_sales_history_api_endpoints(client, db):
    # Test POST endpoint
    response = client.post(
        "/api/v1/sales-history",
        json={
            "store_id": 1,
            "sku": "API-SKU-001",
            "date": "2026-08-01",
            "units_sold": 15,
            "price_at_time": 120.0,
            "promotion_flag": True,
            "stockout_flag": False,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "API-SKU-001"
    assert data["units_sold"] == 15

    # Test GET endpoint with filters
    get_res = client.get("/api/v1/sales-history?store_id=1&sku=API-SKU-001")
    assert get_res.status_code == 200
    items = get_res.json()
    assert len(items) == 1
    assert items[0]["units_sold"] == 15


def test_sales_history_csv_upload(client):
    csv_content = (
        "store_id,sku,date,units_sold,price_at_time,promotion_flag,stockout_flag\n"
        "1,CSV-SKU-01,2026-07-01,50,10.0,false,false\n"
        "1,CSV-SKU-02,2026-07-02,0,10.0,false,true\n"
    )
    file_bytes = io.BytesIO(csv_content.encode("utf-8"))
    response = client.post(
        "/api/v1/sales-history/upload-csv",
        files={"file": ("test_sales.csv", file_bytes, "text/csv")},
    )
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_processed"] == 2
    assert summary["successfully_imported"] == 2
    assert summary["failed_rows"] == 0
