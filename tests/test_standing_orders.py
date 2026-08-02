from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.store import Store
from app.models.batch import Batch
from app.models.standing_order import StandingOrder
from app.models.standing_order_match import StandingOrderMatch

client = TestClient(app)


def test_create_standing_order(db_session: Session):
    response = client.post(
        "/api/v1/standing-orders",
        json={
            "ngo_name": "Hope Food Bank",
            "contact_email": "hope@foodbank.org",
            "contact_phone": "+1999888777",
            "category_filter": "Dairy",
            "min_quantity": 5,
            "priority_window_hours": 48,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["ngo_name"] == "Hope Food Bank"
    assert data["category_filter"] == "Dairy"
    assert data["min_quantity"] == 5
    assert data["priority_window_hours"] == 48
    assert data["is_active"] is True
    assert "id" in data


def test_list_and_filter_standing_orders(db_session: Session):
    client.post(
        "/api/v1/standing-orders",
        json={
            "ngo_name": "City Shelter",
            "category_filter": "Bakery",
            "min_quantity": 2,
            "priority_window_hours": 12,
        },
    )
    response = client.get("/api/v1/standing-orders?category_filter=Bakery")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 1
    assert any(o["category_filter"] == "Bakery" for o in orders)


def test_get_update_delete_standing_order(db_session: Session):
    # Create
    res_create = client.post(
        "/api/v1/standing-orders",
        json={
            "ngo_name": "Community Meals",
            "category_filter": "Produce",
            "min_quantity": 10,
        },
    )
    order_id = res_create.json()["id"]

    # Get
    res_get = client.get(f"/api/v1/standing-orders/{order_id}")
    assert res_get.status_code == 200
    assert res_get.json()["ngo_name"] == "Community Meals"

    # Update
    res_put = client.put(
        f"/api/v1/standing-orders/{order_id}",
        json={"min_quantity": 20, "is_active": False},
    )
    assert res_put.status_code == 200
    assert res_put.json()["min_quantity"] == 20
    assert res_put.json()["is_active"] is False

    # Delete
    res_del = client.delete(f"/api/v1/standing-orders/{order_id}")
    assert res_del.status_code == 204

    # Verify deleted
    res_get_deleted = client.get(f"/api/v1/standing-orders/{order_id}")
    assert res_get_deleted.status_code == 404


def test_evaluate_standing_orders_engine(db_session: Session):
    # 1. Create a store
    store = Store(name="NGO Test Store", address="456 Rescue Way")
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    # 2. Create an expiring batch (expiring tomorrow = ~24h window)
    expiring_batch = Batch(
        store_id=store.id,
        sku="DAIRY-MILK-99",
        product_name="Organic Whole Milk 1L",
        category="Dairy",
        quantity=15,
        cost_price=1.5,
        original_selling_price=3.5,
        current_price=3.5,
        expiration_date=date.today() + timedelta(days=1),
        status="ACTIVE",
    )
    db_session.add(expiring_batch)
    db_session.commit()
    db_session.refresh(expiring_batch)

    # 3. Create active standing order for Dairy
    create_res = client.post(
        "/api/v1/standing-orders",
        json={
            "ngo_name": "Metropolitan Food Rescue",
            "contact_email": "rescue@metro.org",
            "category_filter": "Dairy",
            "min_quantity": 10,
            "priority_window_hours": 48,
            "is_active": True,
        },
    )
    order_id = create_res.json()["id"]

    # 4. Trigger engine evaluation
    eval_res = client.post("/api/v1/standing-orders/evaluate")
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["matched_count"] >= 1

    # 5. Verify match details via matches endpoint
    matches_res = client.get(f"/api/v1/standing-orders/matches?standing_order_id={order_id}")
    assert matches_res.status_code == 200
    matches = matches_res.json()
    assert len(matches) == 1
    match = matches[0]
    assert match["batch_id"] == expiring_batch.id
    assert match["allocated_quantity"] == 15
    assert match["is_subsidized"] is True
    assert match["status"] == "RESERVED"
