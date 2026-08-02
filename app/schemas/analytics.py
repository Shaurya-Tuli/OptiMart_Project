from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class WasteImpactMetrics(BaseModel):
    total_batches_tracked: int
    total_items_rescued: int
    total_waste_prevented_kg: float
    total_co2_saved_kg: float


class FinancialMetrics(BaseModel):
    total_revenue_recovered: float
    total_discounts_given: float
    average_discount_percentage: float


class StandingOrderMetrics(BaseModel):
    total_standing_orders: int
    total_ngo_matches: int
    total_subsidized_items_allocated: int


class AnalyticsSummaryResponse(BaseModel):
    waste_impact: WasteImpactMetrics
    financial_impact: FinancialMetrics
    standing_orders: StandingOrderMetrics
    category_breakdown: Dict[str, int]
    claim_conversion_rate_percentage: float

    model_config = ConfigDict(from_attributes=True)


class StoreAnalyticsResponse(BaseModel):
    store_id: int
    store_name: str
    total_active_batches: int
    total_expired_batches: int
    total_rescued_batches: int
    revenue_recovered: float
    items_rescued: int

    model_config = ConfigDict(from_attributes=True)
