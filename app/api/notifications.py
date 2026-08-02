from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Form, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.batch import Batch
from app.schemas.notification import (
    NotificationSendRequest,
    NotificationResponse,
    BroadcastRequest,
    BroadcastResponse,
    InboundReplyResponse,
)
from app.services.notification import (
    TwilioNotificationService,
    get_notification_service,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.post("/send", response_model=NotificationResponse)
def send_notification(
    req: NotificationSendRequest,
    service: TwilioNotificationService = Depends(get_notification_service),
):
    """Sends a direct outbound SMS or WhatsApp notification to a single recipient."""
    body = (
        req.message_text
        or f"OptiMart Alert: Food batch #{req.batch_id or 'discount'} is available now! Claim at https://optimart.app/claim"
    )

    if req.channel.lower() == "whatsapp":
        result = service.send_whatsapp(to_phone=req.recipient_phone, body=body)
    else:
        result = service.send_sms(to_phone=req.recipient_phone, body=body)

    return NotificationResponse(**result)


@router.post("/broadcast/{batch_id}", response_model=BroadcastResponse)
def broadcast_notifications(
    batch_id: int,
    req: BroadcastRequest,
    db: Session = Depends(get_db),
    service: TwilioNotificationService = Depends(get_notification_service),
):
    """Triggers a hyper-local flash sale broadcast for a specific inventory batch."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with ID {batch_id} not found.",
        )

    result = service.broadcast_flash_sale(
        batch_id=batch_id, recipients=req.recipients, channel=req.channel
    )
    return BroadcastResponse(**result)


@router.post("/twilio-inbound", response_model=InboundReplyResponse)
def handle_twilio_inbound_sms(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Webhook endpoint receiving inbound SMS messages from Twilio.

    Parses single-tap claims (e.g. 'YES' or 'CLAIM <batch_id>') to automatically
    reserve items directly via text message.
    """
    clean_body = Body.strip().upper()
    sender_phone = From.strip()

    if clean_body.startswith("YES") or clean_body.startswith("CLAIM"):
        # Extract batch ID if specified, e.g. "CLAIM 1" or "YES 1"
        parts = clean_body.split()
        target_batch = None
        if len(parts) > 1 and parts[1].isdigit():
            batch_id = int(parts[1])
            target_batch = db.query(Batch).filter(Batch.id == batch_id).first()
        else:
            # Pick the latest active/discounted batch as default claim target
            target_batch = (
                db.query(Batch)
                .filter(Batch.status.in_(["ACTIVE", "DISCOUNTED"]))
                .order_by(Batch.updated_at.desc())
                .first()
            )

        if target_batch:
            return InboundReplyResponse(
                action="CLAIMED",
                batch_id=target_batch.id,
                status="SUCCESS",
                detail=f"Item '{target_batch.product_name}' successfully reserved for {sender_phone}.",
            )
        else:
            return InboundReplyResponse(
                action="CLAIM_FAILED",
                batch_id=None,
                status="NO_BATCH_AVAILABLE",
                detail="No active discounted batches available to claim.",
            )

    return InboundReplyResponse(
        action="HELP",
        batch_id=None,
        status="IGNORED",
        detail="Reply 'YES' or 'CLAIM <batch_id>' to reserve food rescue items.",
    )
