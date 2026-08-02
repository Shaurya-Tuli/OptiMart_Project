from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ForecastRequest(BaseModel):
    store_id: int
    sku: str
    category: Optional[str] = "General"
    price_at_time: Optional[float] = 100.0
    promotion_flag: Optional[bool] = False
    stockout_flag: Optional[bool] = False


class ForecastResponse(BaseModel):
    store_id: int
    sku: str
    predicted_demand_next_7d: float
    confidence_low: float
    confidence_high: float
    confidence_band_spread: float
    is_cold_start: bool
    top_factors: List[str]

    model_config = ConfigDict(from_attributes=True)


class ForecastTrainResponse(BaseModel):
    status: str
    samples_trained: Optional[int] = None
    samples_validated: Optional[int] = None
    baseline_mae: Optional[float] = None
    model_mae: Optional[float] = None
    improvement_pct_over_baseline: Optional[float] = None
    reason: Optional[str] = None
