from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class CheckoutSessionRequest(BaseModel):
    claim_token: str = Field(..., json_schema_extra={"example": "abc123xyz"})
    provider: str = Field(
        default="razorpay",
        json_schema_extra={"example": "razorpay"},
    )
    success_url: Optional[str] = Field(
        None,
        json_schema_extra={"example": "https://optimart.app/claim/success"},
    )
    cancel_url: Optional[str] = Field(
        None,
        json_schema_extra={"example": "https://optimart.app/claim/cancel"},
    )


class CheckoutSessionResponse(BaseModel):
    claim_token: str
    provider: str
    checkout_url: str
    order_id: Optional[str]
    amount_paise: Optional[int]  # Razorpay: smallest currency unit (paise for INR)
    amount_cents: Optional[int]  # Stripe: smallest currency unit (cents for USD)
    currency: str
    expires_at: Optional[datetime]


class PaymentWebhookResponse(BaseModel):
    event_type: str
    claim_token: Optional[str]
    payment_ref: str
    status: str
    detail: str
