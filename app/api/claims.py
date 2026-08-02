import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.batch import Batch
from app.models.claim import Claim, generate_claim_token
from app.schemas.claim import (
    ClaimCreateRequest,
    ClaimResponse,
    ClaimStatusUpdate,
    GeofenceSearchRequest,
    GeofenceSearchResponse,
    GeofenceResult,
)
from app.services.geo_routing import search_nearby_batches
from app.services.reservation import (
    acquire_reservation_lock,
    release_reservation_lock,
    get_reservation_lock_info,
    is_batch_reserved,
    reservation_expiry_timestamp,
)

router = APIRouter(prefix="/api/v1/claims", tags=["Claims & Marketplace"])

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")


@router.post("/geo-search", response_model=GeofenceSearchResponse)
def geo_search_nearby_batches(
    req: GeofenceSearchRequest,
    db: Session = Depends(get_db),
):
    """Geo-fenced marketplace search: returns active/discounted food batches within radius_km
    of the given coordinates using PostGIS (with haversine fallback)."""
    results = search_nearby_batches(
        db=db,
        latitude=req.latitude,
        longitude=req.longitude,
        radius_km=req.radius_km,
        category=req.category,
    )
    batch_list = [GeofenceResult(**r) for r in results]
    return GeofenceSearchResponse(
        latitude=req.latitude,
        longitude=req.longitude,
        radius_km=req.radius_km,
        total_results=len(batch_list),
        batches=batch_list,
    )


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    req: ClaimCreateRequest,
    db: Session = Depends(get_db),
):
    """Creates a tokenized reservation/claim on a batch with a Redis TTL lock (3-minute hold).

    If another claim is already holding the Redis lock for this batch, returns 409 Conflict.
    """
    batch = db.query(Batch).filter(Batch.id == req.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {req.batch_id} not found.")

    if batch.status not in ("ACTIVE", "DISCOUNTED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch {req.batch_id} is not available for claiming (status: {batch.status}).",
        )

    if batch.quantity < req.reserved_quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Insufficient quantity: requested {req.reserved_quantity}, available {batch.quantity}.",
        )

    # Generate claim record first so we have a claim_id for the Redis lock
    token = generate_claim_token()
    expiry = reservation_expiry_timestamp()

    claim = Claim(
        batch_id=req.batch_id,
        claim_token=token,
        reserver_phone=req.reserver_phone,
        reserver_email=req.reserver_email,
        reserved_quantity=req.reserved_quantity,
        fulfillment_type=req.fulfillment_type,
        status="RESERVED",
        is_subsidized=req.is_subsidized,
        reserved_until=expiry,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    # Attempt to acquire Redis TTL lock — atomic NX set
    locked = acquire_reservation_lock(req.batch_id, claim.id)
    if not locked:
        # Another claim already holds the lock — roll back this claim
        db.delete(claim)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch {req.batch_id} is currently reserved by another user. Please try again shortly.",
        )

    claim_url = f"{BACKEND_URL}/api/v1/claims/{token}"
    return _claim_to_response(claim, claim_url)


@router.get("/batch/{batch_id}", response_model=ClaimResponse)
def get_claim_by_batch(batch_id: int, db: Session = Depends(get_db)):
    """Returns the active RESERVED claim for a given batch ID (the canonical claim link)."""
    claim = (
        db.query(Claim)
        .filter(Claim.batch_id == batch_id, Claim.status == "RESERVED")
        .first()
    )
    if not claim:
        raise HTTPException(
            status_code=404,
            detail=f"No active reservation found for batch {batch_id}.",
        )
    claim_url = f"{BACKEND_URL}/api/v1/claims/{claim.claim_token}"
    return _claim_to_response(claim, claim_url)


@router.get("/{token}", response_model=ClaimResponse)
def get_claim_by_token(token: str, db: Session = Depends(get_db)):
    """Returns the claim record for a tokenized claim URL."""
    claim = db.query(Claim).filter(Claim.claim_token == token).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim token not found or expired.")
    claim_url = f"{BACKEND_URL}/api/v1/claims/{token}"
    return _claim_to_response(claim, claim_url)


@router.patch("/{token}", response_model=ClaimResponse)
def update_claim_status(
    token: str, update: ClaimStatusUpdate, db: Session = Depends(get_db)
):
    """Updates the claim status (e.g., PAID → FULFILLED). Releases Redis lock on PAID or CANCELLED."""
    claim = db.query(Claim).filter(Claim.claim_token == token).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim token not found.")

    claim.status = update.status
    if update.fulfillment_type:
        claim.fulfillment_type = update.fulfillment_type
    if update.payment_ref:
        claim.payment_ref = update.payment_ref

    # Release the Redis TTL lock once payment is confirmed or claim cancelled
    if update.status in ("PAID", "FULFILLED", "CANCELLED", "EXPIRED"):
        release_reservation_lock(claim.batch_id)

    db.commit()
    db.refresh(claim)
    claim_url = f"{BACKEND_URL}/api/v1/claims/{token}"
    return _claim_to_response(claim, claim_url)


@router.get("/lock-status/{batch_id}")
def get_batch_lock_status(batch_id: int):
    """Returns the Redis reservation lock status for a batch (for debugging / admin use)."""
    info = get_reservation_lock_info(batch_id)
    if info:
        return {"batch_id": batch_id, "is_reserved": True, **info}
    return {"batch_id": batch_id, "is_reserved": False}


# ── helpers ──────────────────────────────────────────────────────────────────

def _claim_to_response(claim: Claim, claim_url: str) -> ClaimResponse:
    return ClaimResponse(
        id=claim.id,
        batch_id=claim.batch_id,
        claim_token=claim.claim_token,
        reserver_phone=claim.reserver_phone,
        reserver_email=claim.reserver_email,
        reserved_quantity=claim.reserved_quantity,
        fulfillment_type=claim.fulfillment_type,
        status=claim.status,
        is_subsidized=claim.is_subsidized,
        reserved_until=claim.reserved_until,
        payment_ref=claim.payment_ref,
        created_at=claim.created_at,
        claim_url=claim_url,
    )
