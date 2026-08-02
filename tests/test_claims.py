"""Phase 5 tests: Consumer Marketplace, Geo-routing, and Redis TTL Reservation Locking."""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.store import Store
from app.models.batch import Batch
from app.models.claim import Claim
from app.services.reservation import (
    acquire_reservation_lock,
    release_reservation_lock,
    is_batch_reserved,
    get_reservation_lock_info,
)
from app.services.geo_routing import haversine_km

client = TestClient(app)


# ── Haversine helper ──────────────────────────────────────────────────────────

def test_haversine_km_known_distance():
    """New York to London ≈ 5571 km (within 10 km tolerance)."""
    dist = haversine_km(40.7128, -74.0060, 51.5074, -0.1278)
    assert 5560 < dist < 5580


def test_haversine_km_same_point():
    assert haversine_km(12.345, 67.890, 12.345, 67.890) == 0.0


# ── Redis reservation lock ────────────────────────────────────────────────────

def test_acquire_and_release_lock():
    batch_id = 99991
    claim_id = 1

    with patch("app.services.reservation.redis.from_url") as mock_redis_factory:
        mock_r = MagicMock()
        mock_redis_factory.return_value = mock_r

        # First acquisition should succeed
        mock_r.set.return_value = True
        assert acquire_reservation_lock(batch_id, claim_id) is True

        # Simulate lock release
        mock_r.delete.return_value = 1
        assert release_reservation_lock(batch_id) is True


def test_concurrent_claim_blocked():
    batch_id = 99992
    with patch("app.services.reservation.redis.from_url") as mock_redis_factory:
        mock_r = MagicMock()
        mock_redis_factory.return_value = mock_r

        # Second acquisition returns False (NX set fails — key already exists)
        mock_r.set.return_value = None
        assert acquire_reservation_lock(batch_id, 2) is False


# ── Claim CRUD via API ────────────────────────────────────────────────────────

def test_create_and_fetch_claim(db_session: Session):
    # Create store + batch
    store = Store(name="Market Place Store", location_lat=40.71, location_lng=-74.01)
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    batch = Batch(
        store_id=store.id,
        sku="CLAIM-TEST-001",
        product_name="Greek Yogurt 500g",
        category="Dairy",
        quantity=10,
        cost_price=1.0,
        original_selling_price=3.0,
        current_price=1.5,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    with patch("app.services.reservation.redis.from_url") as mock_redis_factory:
        mock_r = MagicMock()
        mock_redis_factory.return_value = mock_r
        mock_r.set.return_value = True  # Lock acquisition succeeds

        # Create claim
        res = client.post(
            "/api/v1/claims",
            json={
                "batch_id": batch.id,
                "reserver_phone": "+1555444333",
                "reserved_quantity": 2,
                "fulfillment_type": "pickup",
            },
        )
        assert res.status_code == 201
        claim_data = res.json()
        assert claim_data["batch_id"] == batch.id
        assert claim_data["status"] == "RESERVED"
        assert "claim_token" in claim_data
        assert "claim_url" in claim_data

        token = claim_data["claim_token"]

        # Fetch by token
        res_get = client.get(f"/api/v1/claims/{token}")
        assert res_get.status_code == 200
        assert res_get.json()["claim_token"] == token


def test_update_claim_to_paid(db_session: Session):
    store = Store(name="Update Test Store", location_lat=40.0, location_lng=-73.0)
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    batch = Batch(
        store_id=store.id,
        sku="UPDATE-CLAIM-001",
        product_name="Sourdough Bread",
        category="Bakery",
        quantity=5,
        cost_price=0.5,
        original_selling_price=2.5,
        current_price=1.0,
        expiration_date=date.today() + timedelta(days=1),
        status="ACTIVE",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    with patch("app.services.reservation.redis.from_url") as mock_redis_factory:
        mock_r = MagicMock()
        mock_redis_factory.return_value = mock_r
        mock_r.set.return_value = True
        mock_r.delete.return_value = 1

        create_res = client.post(
            "/api/v1/claims",
            json={"batch_id": batch.id, "reserved_quantity": 1},
        )
        assert create_res.status_code == 201
        token = create_res.json()["claim_token"]

        # Mark as PAID (simulates payment webhook confirmation)
        patch_res = client.patch(
            f"/api/v1/claims/{token}",
            json={"status": "PAID", "payment_ref": "stripe_pi_test_123"},
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["status"] == "PAID"
        assert updated["payment_ref"] == "stripe_pi_test_123"


# ── Geo-fenced marketplace search ─────────────────────────────────────────────

def test_geo_search_returns_nearby_batches(db_session: Session):
    store = Store(
        name="Downtown Deli",
        location_lat=40.7128,
        location_lng=-74.0060,
    )
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    batch = Batch(
        store_id=store.id,
        sku="GEO-TEST-001",
        product_name="Deli Sandwich",
        category="Deli",
        quantity=12,
        cost_price=2.0,
        original_selling_price=6.0,
        current_price=3.0,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(batch)
    db_session.commit()

    # Search 1 km from the same lat/lng — should include the store
    res = client.post(
        "/api/v1/claims/geo-search",
        json={"latitude": 40.7130, "longitude": -74.0065, "radius_km": 1.0},
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["batches"], list)
    # At least one batch from our store should appear
    names = [b["product_name"] for b in data["batches"]]
    assert "Deli Sandwich" in names
