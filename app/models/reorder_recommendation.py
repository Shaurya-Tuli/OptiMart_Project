from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class ReorderRecommendation(Base):
    __tablename__ = "reorder_recommendations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), nullable=False, index=True)
    forecast_run_date = Column(Date, nullable=False, index=True)
    predicted_demand = Column(Float, nullable=False, default=0.0)
    confidence_low = Column(Float, nullable=False, default=0.0)
    confidence_high = Column(Float, nullable=False, default=0.0)
    recommended_qty = Column(Integer, nullable=False, default=0)
    top_factors = Column(JSON, nullable=True)
    retailer_decision = Column(String(50), nullable=False, default="PENDING", index=True)
    adjusted_qty = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    store = relationship("Store")

    __table_args__ = (
        UniqueConstraint("store_id", "sku", "forecast_run_date", name="uix_reorder_rec_store_sku_date"),
    )
