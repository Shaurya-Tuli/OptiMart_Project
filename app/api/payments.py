import json
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.claim import Claim
from app.models.batch import Batch
from app.schemas.payment import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentWebhookResponse,
)
from app.services.payment import (
    create_razorpay_order,
    create_stripe_session,
    verify_razorpay_webhook,
    verify_stripe_webhook,
)
from app.services.reservation import release_reservation_lock

router = APIRouter(prefix="/api/v1/payments", tags=["Multi-rail Payments"])


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    req: CheckoutSessionRequest,
    db: Session = Depends(get_db),
):
    """Creates a payment checkout session via Razorpay or Stripe for a reserved claim.

    If the claim is marked as subsidized (NGO/Shelter priority), payment is bypassed entirely.
    """
    claim = db.query(Claim).filter(Claim.claim_token == req.claim_token).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim token '{req.claim_token}' not found.",
        )

    if claim.status not in ("RESERVED", "PENDING_PAYMENT"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Claim status '{claim.status}' cannot proceed to checkout.",
        )

    batch = db.query(Batch).filter(Batch.id == claim.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Associated batch not found.")

    # Subsidized claims (NGO/Shelter) bypass payment entirely
    if claim.is_subsidized:
        claim.status = "PAID"
        claim.payment_ref = "SUBSIDIZED_BYPASS"
        release_reservation_lock(claim.batch_id)
        db.commit()
        return CheckoutSessionResponse(
            claim_token=claim.claim_token,
            provider="subsidized_bypass",
            checkout_url=f"/api/v1/claims/{claim.claim_token}",
            order_id="subsidized_free",
            amount_paise=0,
            amount_cents=0,
            currency="INR",
            expires_at=None,
        )

    # Calculate total price
    total_price = batch.current_price * claim.reserved_quantity

    provider = req.provider.lower()
    if provider == "stripe":
        amount_cents = int(round(total_price * 100))
        session_data = create_stripe_session(
            amount_cents=amount_cents,
            claim_token=claim.claim_token,
            currency="inr",
            success_url=req.success_url,
            cancel_url=req.cancel_url,
        )
    else:  # default: razorpay
        amount_paise = int(round(total_price * 100))
        session_data = create_razorpay_order(
            amount_paise=amount_paise,
            claim_token=claim.claim_token,
            currency="INR",
        )

    claim.status = "PENDING_PAYMENT"
    db.commit()

    return CheckoutSessionResponse(
        claim_token=claim.claim_token,
        provider=session_data["provider"],
        checkout_url=session_data["checkout_url"],
        order_id=session_data.get("order_id"),
        amount_paise=session_data.get("amount_paise"),
        amount_cents=session_data.get("amount_cents"),
        currency=session_data["currency"],
        expires_at=session_data.get("expires_at"),
    )


@router.post("/webhooks/razorpay", response_model=PaymentWebhookResponse)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Handles Razorpay payment webhooks (e.g. `payment.captured`). Converts claim status to PAID."""
    body_bytes = await request.body()

    if not verify_razorpay_webhook(body_bytes, x_razorpay_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Razorpay webhook signature.",
        )

    try:
        payload = json.loads(body_bytes)
    except Exception:
        payload = {}

    event = payload.get("event", "payment.captured")
    claim_token = None
    payment_id = "rzp_pay_mock"

    # Extract claim token from notes or payload body
    if "payload" in payload and "payment" in payload["payload"]:
        entity = payload["payload"]["payment"].get("entity", {})
        payment_id = entity.get("id", payment_id)
        notes = entity.get("notes", {})
        claim_token = notes.get("claim_token")

    if not claim_token and "claim_token" in payload:
        claim_token = payload["claim_token"]

    if claim_token:
        claim = db.query(Claim).filter(Claim.claim_token == claim_token).first()
        if claim:
            claim.status = "PAID"
            claim.payment_ref = payment_id
            release_reservation_lock(claim.batch_id)
            db.commit()
            return PaymentWebhookResponse(
                event_type=event,
                claim_token=claim_token,
                payment_ref=payment_id,
                status="PAID",
                detail="Payment verified successfully via Razorpay.",
            )

    return PaymentWebhookResponse(
        event_type=event,
        claim_token=claim_token,
        payment_ref=payment_id,
        status="IGNORED",
        detail="Webhook received but no matching claim was updated.",
    )


@router.post("/webhooks/stripe", response_model=PaymentWebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Handles Stripe `checkout.session.completed` webhooks. Converts claim status to PAID."""
    body_bytes = await request.body()

    if not verify_stripe_webhook(body_bytes, stripe_signature):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        )

    try:
        payload = json.loads(body_bytes)
    except Exception:
        payload = {}

    event = payload.get("type", "checkout.session.completed")
    claim_token = None
    payment_id = "pi_stripe_mock"

    if "data" in payload and "object" in payload["data"]:
        obj = payload["data"]["object"]
        payment_id = obj.get("payment_intent", obj.get("id", payment_id))
        metadata = obj.get("metadata", {})
        claim_token = metadata.get("claim_token")

    if not claim_token and "claim_token" in payload:
        claim_token = payload["claim_token"]

    if claim_token:
        claim = db.query(Claim).filter(Claim.claim_token == claim_token).first()
        if claim:
            claim.status = "PAID"
            claim.payment_ref = payment_id
            release_reservation_lock(claim.batch_id)
            db.commit()
            return PaymentWebhookResponse(
                event_type=event,
                claim_token=claim_token,
                payment_ref=payment_id,
                status="PAID",
                detail="Payment verified successfully via Stripe.",
            )

    return PaymentWebhookResponse(
        event_type=event,
        claim_token=claim_token,
        payment_ref=payment_id,
        status="IGNORED",
        detail="Webhook received but no matching claim was updated.",
    )
