from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReorderRecommendationBase(BaseModel):
    store_id: int
    sku: str
    forecast_run_date: date
    predicted_demand: float
    confidence_low: float
    confidence_high: float
    recommended_qty: int
    top_factors: Optional[List[str]] = None
    retailer_decision: str = "PENDING"
    adjusted_qty: Optional[int] = None


class ReorderRecommendationResponse(ReorderRecommendationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReorderDecisionRequest(BaseModel):
    decision: str = Field(..., description="retailer decision: ACCEPTED, ADJUSTED, DISMISSED")
    adjusted_qty: Optional[int] = Field(default=None, ge=0, description="required if decision is ADJUSTED")
