import os
import secrets
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_claim_token() -> str:
    return secrets.token_urlsafe(24)


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(
        Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Hashed or plaintext token used in the claim URL
    claim_token = Column(String(64), nullable=False, unique=True, index=True)
    # Reserver contact (phone or email)
    reserver_phone = Column(String(50), nullable=True)
    reserver_email = Column(String(255), nullable=True)
    # Quantity reserved
    reserved_quantity = Column(Integer, nullable=False, default=1)
    # Fulfillment type: 'pickup' or 'delivery'
    fulfillment_type = Column(String(20), nullable=False, default="pickup")
    # Claim status: RESERVED | PAID | EXPIRED | FULFILLED | CANCELLED
    status = Column(String(30), nullable=False, default="RESERVED", index=True)
    # Subsidized (NGO/shelter) claims skip payment entirely
    is_subsidized = Column(Boolean, nullable=False, default=False)
    # TTL expiry timestamp — if not paid before this, hold is released
    reserved_until = Column(DateTime(timezone=True), nullable=True)
    # Payment reference from Stripe / Razorpay
    payment_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
