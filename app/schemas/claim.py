from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ClaimCreateRequest(BaseModel):
    batch_id: int = Field(..., json_schema_extra={"example": 1})
    reserver_phone: Optional[str] = Field(None, json_schema_extra={"example": "+1234567890"})
    reserver_email: Optional[str] = Field(None, json_schema_extra={"example": "user@example.com"})
    reserved_quantity: int = Field(default=1, ge=1)
    fulfillment_type: str = Field(default="pickup", json_schema_extra={"example": "pickup"})
    is_subsidized: bool = False


class ClaimResponse(BaseModel):
    id: int
    batch_id: int
    claim_token: str
    reserver_phone: Optional[str]
    reserver_email: Optional[str]
    reserved_quantity: int
    fulfillment_type: str
    status: str
    is_subsidized: bool
    reserved_until: Optional[datetime]
    payment_ref: Optional[str]
    created_at: datetime
    claim_url: str

    model_config = ConfigDict(from_attributes=True)


class ClaimStatusUpdate(BaseModel):
    status: str = Field(..., json_schema_extra={"example": "FULFILLED"})
    fulfillment_type: Optional[str] = None
    payment_ref: Optional[str] = None


class GeofenceSearchRequest(BaseModel):
    latitude: float = Field(..., json_schema_extra={"example": 40.7128})
    longitude: float = Field(..., json_schema_extra={"example": -74.0060})
    radius_km: float = Field(default=5.0, ge=0.1, le=50.0, json_schema_extra={"example": 5.0})
    category: Optional[str] = Field(None, json_schema_extra={"example": "Dairy"})


class GeofenceResult(BaseModel):
    batch_id: int
    store_id: int
    store_name: str
    product_name: str
    category: str
    quantity: int
    current_price: float
    discount_percentage: float
    expiration_date: str
    status: str
    distance_km: float
    claim_url: str

    model_config = ConfigDict(from_attributes=True)


class GeofenceSearchResponse(BaseModel):
    latitude: float
    longitude: float
    radius_km: float
    total_results: int
    batches: List[GeofenceResult]
