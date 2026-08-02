"""Geo-fenced marketplace service using PostGIS radius queries.

Uses the Haversine formula via ST_DWithin (geography type) for accurate
great-circle distance calculations without requiring a geometry column on stores.
Falls back to a simple bounding-box filter when the stores table doesn't have
PostGIS geography columns populated.
"""
import os
import math
from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.batch import Batch
from app.models.store import Store

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Pure-Python haversine great-circle distance in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def search_nearby_batches(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns active/discounted batches whose stores fall within radius_km of the given coordinates.

    Strategy:
    1. First try PostGIS ST_DWithin geography query for exact great-circle distance.
    2. Fall back to Python haversine calculation over all stores if PostGIS geography columns are unavailable.
    """
    # Attempt PostGIS geography query
    try:
        sql = text("""
            SELECT
                b.id        AS batch_id,
                s.id        AS store_id,
                s.name      AS store_name,
                b.product_name,
                b.category,
                b.quantity,
                b.current_price,
                b.discount_percentage,
                b.expiration_date,
                b.status,
                ST_Distance(
                    ST_MakePoint(:lon, :lat)::geography,
                    ST_MakePoint(s.location_lng, s.location_lat)::geography
                ) / 1000.0  AS distance_km
            FROM batches b
            JOIN stores  s ON s.id = b.store_id
            WHERE b.status IN ('ACTIVE', 'DISCOUNTED')
              AND s.location_lat IS NOT NULL
              AND s.location_lng IS NOT NULL
              AND ST_DWithin(
                    ST_MakePoint(:lon, :lat)::geography,
                    ST_MakePoint(s.location_lng, s.location_lat)::geography,
                    :radius_m
                  )
              AND b.expiration_date >= :today
              :cat_filter
            ORDER BY distance_km ASC
        """.replace(
            ":cat_filter",
            "AND LOWER(b.category) = LOWER(:category)" if category else "",
        ))

        params: Dict[str, Any] = {
            "lat": latitude,
            "lon": longitude,
            "radius_m": radius_km * 1000,
            "today": date.today(),
        }
        if category:
            params["category"] = category

        rows = db.execute(sql, params).mappings().all()
        return [_row_to_dict(row) for row in rows]

    except Exception:
        # Fallback: Python haversine across all stores
        return _fallback_haversine_search(db, latitude, longitude, radius_km, category)


def _fallback_haversine_search(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float,
    category: Optional[str],
) -> List[Dict[str, Any]]:
    """Fallback geo search using Python haversine when PostGIS geography is unavailable."""
    batch_query = db.query(Batch, Store).join(Store, Batch.store_id == Store.id).filter(
        Batch.status.in_(["ACTIVE", "DISCOUNTED"]),
        Batch.expiration_date >= date.today(),
    )
    if category:
        batch_query = batch_query.filter(Batch.category.ilike(category))

    results = []
    for batch, store in batch_query.all():
        if store.location_lat is None or store.location_lng is None:
            continue
        dist = haversine_km(latitude, longitude, store.location_lat, store.location_lng)
        if dist <= radius_km:
            results.append(
                {
                    "batch_id": batch.id,
                    "store_id": store.id,
                    "store_name": store.name,
                    "product_name": batch.product_name,
                    "category": batch.category,
                    "quantity": batch.quantity,
                    "current_price": batch.current_price,
                    "discount_percentage": batch.discount_percentage,
                    "expiration_date": str(batch.expiration_date),
                    "status": batch.status,
                    "distance_km": round(dist, 3),
                    "claim_url": f"{BACKEND_URL}/api/v1/claims/batch/{batch.id}",
                }
            )
    return sorted(results, key=lambda x: x["distance_km"])


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "batch_id": row["batch_id"],
        "store_id": row["store_id"],
        "store_name": row["store_name"],
        "product_name": row["product_name"],
        "category": row["category"],
        "quantity": row["quantity"],
        "current_price": float(row["current_price"]),
        "discount_percentage": float(row["discount_percentage"]),
        "expiration_date": str(row["expiration_date"]),
        "status": row["status"],
        "distance_km": round(float(row["distance_km"]), 3),
        "claim_url": f"{BACKEND_URL}/api/v1/claims/batch/{row['batch_id']}",
    }
