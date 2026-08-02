from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Batch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    product_name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), nullable=False, default="General", index=True)
    quantity = Column(Integer, nullable=False, default=0)
    cost_price = Column(Float, nullable=False, default=0.0)
    original_selling_price = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, nullable=False, default=0.0)
    expiration_date = Column(Date, nullable=False, index=True)
    discount_percentage = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    store = relationship("Store", back_populates="batches")
