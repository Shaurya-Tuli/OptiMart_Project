from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.analytics import AnalyticsSummaryResponse, StoreAnalyticsResponse
from app.services.analytics import get_analytics_summary, get_store_analytics

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics & Impact Dashboard"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_platform_analytics_summary(db: Session = Depends(get_db)):
    """Returns platform-wide waste impact, financial recovery, CO2 savings, and NGO metrics."""
    data = get_analytics_summary(db)
    return AnalyticsSummaryResponse(**data)


@router.get("/store/{store_id}", response_model=StoreAnalyticsResponse)
def get_single_store_analytics(store_id: int, db: Session = Depends(get_db)):
    """Returns detailed analytics for a single store."""
    data = get_store_analytics(db, store_id)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Store ID {store_id} not found.",
        )
    return StoreAnalyticsResponse(**data)
