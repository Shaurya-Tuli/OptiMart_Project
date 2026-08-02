from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class StandingOrderBase(BaseModel):
    ngo_name: str = Field(..., json_schema_extra={"example": "City Food Shelter"})
    contact_email: Optional[str] = Field(None, json_schema_extra={"example": "contact@cityshelter.org"})
    contact_phone: Optional[str] = Field(None, json_schema_extra={"example": "+1234567890"})
    category_filter: str = Field(default="ALL", json_schema_extra={"example": "Dairy"})
    min_quantity: int = Field(default=1, ge=1, json_schema_extra={"example": 5})
    priority_window_hours: int = Field(default=24, ge=1, json_schema_extra={"example": 12})
    is_active: bool = True


class StandingOrderCreate(StandingOrderBase):
    pass


class StandingOrderUpdate(BaseModel):
    ngo_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    category_filter: Optional[str] = None
    min_quantity: Optional[int] = Field(None, ge=1)
    priority_window_hours: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class StandingOrderResponse(StandingOrderBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StandingOrderMatchResponse(BaseModel):
    id: int
    standing_order_id: int
    batch_id: int
    allocated_quantity: int
    status: str
    is_subsidized: bool
    allocated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineEvaluateResponse(BaseModel):
    matched_count: int
    matches: List[StandingOrderMatchResponse]
