from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class StoreBase(BaseModel):
    name: str
    address: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None


class StoreResponse(StoreBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
