from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class StandingOrder(Base):
    __tablename__ = "standing_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ngo_name = Column(String(255), nullable=False, index=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    category_filter = Column(String(100), nullable=False, default="ALL", index=True)
    min_quantity = Column(Integer, nullable=False, default=1)
    priority_window_hours = Column(Integer, nullable=False, default=24)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
