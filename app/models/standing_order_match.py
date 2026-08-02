from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class StandingOrderMatch(Base):
    __tablename__ = "standing_order_matches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    standing_order_id = Column(
        Integer, ForeignKey("standing_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id = Column(
        Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allocated_quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="RESERVED", index=True)
    is_subsidized = Column(Boolean, nullable=False, default=True)
    allocated_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
