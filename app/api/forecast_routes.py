from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.reorder_recommendation import ReorderRecommendationResponse, ReorderDecisionRequest
from app.services.reorder_recommendation import (
    generate_reorder_recommendations,
    update_reorder_decision,
    get_store_recommendations,
)

router = APIRouter(prefix="/api/v1/forecast", tags=["Reorder Recommendations (Phase 10)"])


@router.post("/generate/{store_id}", response_model=List[ReorderRecommendationResponse])
def trigger_generation(store_id: int, db: Session = Depends(get_db)):
    """Manually trigger calculation of optimal order quantities and recommendations for a store."""
    try:
        return generate_reorder_recommendations(db, store_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        )


@router.get("/{store_id}", response_model=List[ReorderRecommendationResponse])
def get_recommendations(
    store_id: int,
    run_date: Optional[date] = Query(None, description="Format YYYY-MM-DD. Defaults to latest forecast run date."),
    db: Session = Depends(get_db),
):
    """Retrieve reorder recommendations for a store, default to the latest forecast run date."""
    recs = get_store_recommendations(db, store_id, run_date)
    return recs


@router.post("/recommendations/{id}/decision", response_model=ReorderRecommendationResponse)
def make_decision(
    id: int,
    payload: ReorderDecisionRequest,
    db: Session = Depends(get_db),
):
    """Accept, adjust, or dismiss a reorder recommendation."""
    try:
        rec = update_reorder_decision(db, id, payload)
        if not rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reorder recommendation with ID {id} not found.",
            )
        return rec
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
