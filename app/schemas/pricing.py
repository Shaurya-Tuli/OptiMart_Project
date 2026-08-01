from typing import Optional
from pydantic import BaseModel, Field


class PricePredictionRequest(BaseModel):
    days_to_expiry: float = Field(ge=0.0)
    category: str = "General"
    quantity: int = Field(ge=1)
    cost_price: float = Field(ge=0.0)
    original_selling_price: float = Field(ge=0.0)
    temperature_c: Optional[float] = 25.0
    historical_demand_factor: Optional[float] = 1.0
    product_condition: Optional[str] = "Excellent"


class PricePredictionResponse(BaseModel):
    risk_score: float
    suggested_discount_percentage: float
    suggested_price: float
    risk_level: str


class BatchRepriceResponse(BaseModel):
    batch_id: int
    sku: str
    product_name: str
    previous_price: float
    previous_discount: float
    new_price: float
    new_discount: float
    risk_score: float
    risk_level: str
    status: str
    reasoning_tags: list[str] = []


class ModelTrainResponse(BaseModel):
    status: str
    samples_trained: int
    artifact_path: str
