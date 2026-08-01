from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class SalesHistoryBase(BaseModel):
    store_id: int
    sku: str
    date: date
    units_sold: int = Field(default=0, ge=0)
    price_at_time: float = Field(default=0.0, ge=0.0)
    promotion_flag: bool = False
    stockout_flag: bool = False


class SalesHistoryCreate(SalesHistoryBase):
    pass


class SalesHistoryResponse(SalesHistoryBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalesHistoryBulkCreate(BaseModel):
    records: List[SalesHistoryCreate]


class SalesHistoryCSVRow(BaseModel):
    store_id: int
    sku: str
    date: date
    units_sold: int
    price_at_time: float
    promotion_flag: Optional[bool] = False
    stockout_flag: Optional[bool] = False
