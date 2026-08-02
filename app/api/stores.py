from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.store import Store
from app.schemas.store import StoreCreate, StoreUpdate, StoreResponse

router = APIRouter(prefix="/api/v1/stores", tags=["Stores"])


@router.post("", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)

def create_store(store_in: StoreCreate, db: Session = Depends(get_db)):
    """Create a new store location."""
    store = Store(
        name=store_in.name,
        address=store_in.address,
        location_lat=store_in.location_lat,
        location_lng=store_in.location_lng,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("", response_model=List[StoreResponse])
def list_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List stores with pagination."""
    return db.query(Store).offset(skip).limit(limit).all()


@router.get("/{store_id}", response_model=StoreResponse)
def get_store(store_id: int, db: Session = Depends(get_db)):
    """Get details for a specific store."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with id {store_id} not found",
        )
    return store


@router.put("/{store_id}", response_model=StoreResponse)
def update_store(
    store_id: int, store_in: StoreUpdate, db: Session = Depends(get_db)
):
    """Update store details."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with id {store_id} not found",
        )

    update_data = store_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)

    db.commit()
    db.refresh(store)
    return store


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_store(store_id: int, db: Session = Depends(get_db)):
    """Delete a store and all associated inventory batches."""
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store with id {store_id} not found",
        )
    db.delete(store)
    db.commit()
    return None
