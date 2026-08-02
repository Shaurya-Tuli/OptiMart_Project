from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.standing_order import StandingOrder
from app.models.standing_order_match import StandingOrderMatch
from app.schemas.standing_order import (
    StandingOrderCreate,
    StandingOrderUpdate,
    StandingOrderResponse,
    StandingOrderMatchResponse,
    EngineEvaluateResponse,
)
from app.services.standing_order_engine import evaluate_standing_orders

router = APIRouter(prefix="/api/v1/standing-orders", tags=["Standing Orders"])


@router.post(
    "", response_model=StandingOrderResponse, status_code=status.HTTP_201_CREATED
)
def create_standing_order(
    order_in: StandingOrderCreate, db: Session = Depends(get_db)
):
    """Creates a new standing order subscription rule for an NGO or Shelter."""
    order = StandingOrder(
        ngo_name=order_in.ngo_name,
        contact_email=order_in.contact_email,
        contact_phone=order_in.contact_phone,
        category_filter=order_in.category_filter,
        min_quantity=order_in.min_quantity,
        priority_window_hours=order_in.priority_window_hours,
        is_active=order_in.is_active,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.get("", response_model=List[StandingOrderResponse])
def list_standing_orders(
    ngo_name: Optional[str] = None,
    category_filter: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """Lists all standing orders with optional filters."""
    query = db.query(StandingOrder)
    if ngo_name:
        query = query.filter(StandingOrder.ngo_name.ilike(f"%{ngo_name}%"))
    if category_filter:
        query = query.filter(
            StandingOrder.category_filter.ilike(f"%{category_filter}%")
        )
    if is_active is not None:
        query = query.filter(StandingOrder.is_active == is_active)
    return query.all()


@router.get("/matches", response_model=List[StandingOrderMatchResponse])
def list_standing_order_matches(
    standing_order_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Lists priority reservations/matches generated for NGOs."""
    query = db.query(StandingOrderMatch)
    if standing_order_id:
        query = query.filter(
            StandingOrderMatch.standing_order_id == standing_order_id
        )
    if batch_id:
        query = query.filter(StandingOrderMatch.batch_id == batch_id)
    return query.all()


@router.get("/{id}", response_model=StandingOrderResponse)
def get_standing_order(id: int, db: Session = Depends(get_db)):
    """Gets details for a specific standing order rule."""
    order = db.query(StandingOrder).filter(StandingOrder.id == id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Standing order with ID {id} not found.",
        )
    return order


@router.put("/{id}", response_model=StandingOrderResponse)
def update_standing_order(
    id: int, order_in: StandingOrderUpdate, db: Session = Depends(get_db)
):
    """Updates an existing standing order rule."""
    order = db.query(StandingOrder).filter(StandingOrder.id == id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Standing order with ID {id} not found.",
        )

    update_data = order_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)

    db.commit()
    db.refresh(order)
    return order


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_standing_order(id: int, db: Session = Depends(get_db)):
    """Deletes a standing order rule."""
    order = db.query(StandingOrder).filter(StandingOrder.id == id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Standing order with ID {id} not found.",
        )
    db.delete(order)
    db.commit()
    return None


@router.post("/evaluate", response_model=EngineEvaluateResponse)
def trigger_standing_order_evaluation(
    batch_id: Optional[int] = Query(None, description="Optional specific batch ID to evaluate"),
    db: Session = Depends(get_db),
):
    """Triggers the Standing Order Engine evaluation against active inventory batches."""
    matches = evaluate_standing_orders(db, batch_id=batch_id)
    return EngineEvaluateResponse(matched_count=len(matches), matches=matches)
