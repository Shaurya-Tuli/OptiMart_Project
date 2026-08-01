from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class SalesHistory(Base):
    __tablename__ = "sales_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    units_sold = Column(Integer, nullable=False, default=0)
    price_at_time = Column(Float, nullable=False, default=0.0)
    promotion_flag = Column(Boolean, nullable=False, default=False)
    stockout_flag = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    store = relationship("Store")

    __table_args__ = (
        UniqueConstraint("store_id", "sku", "date", name="uix_sales_history_store_sku_date"),
    )
