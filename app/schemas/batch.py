from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class BatchBase(BaseModel):
    sku: str
    product_name: str
    category: str = "General"
    quantity: int = Field(ge=0)
    cost_price: float = Field(ge=0.0)
    original_selling_price: float = Field(ge=0.0)
    current_price: Optional[float] = None
    expiration_date: date
    discount_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    status: str = "ACTIVE"


class BatchCreate(BatchBase):
    store_id: int


class BatchUpdate(BaseModel):
    sku: Optional[str] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=0)
    cost_price: Optional[float] = Field(default=None, ge=0.0)
    original_selling_price: Optional[float] = Field(default=None, ge=0.0)
    current_price: Optional[float] = Field(default=None, ge=0.0)
    expiration_date: Optional[date] = None
    discount_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    status: Optional[str] = None


class BatchResponse(BatchBase):
    id: int
    store_id: int
    current_price: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchCSVRow(BaseModel):
    store_id: int
    sku: str
    product_name: str
    category: Optional[str] = "General"
    quantity: int
    cost_price: float
    original_selling_price: float
    current_price: Optional[float] = None
    expiration_date: date
    discount_percentage: Optional[float] = 0.0
    status: Optional[str] = "ACTIVE"


class CSVImportSummary(BaseModel):
    total_processed: int
    successfully_imported: int
    failed_rows: int
    errors: List[str]
