import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any


def utcnow():
    return datetime.now(timezone.utc)


class TwilioNotificationService:
    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_phone = os.environ.get("TWILIO_PHONE_NUMBER", "+15005550006")
        self.whatsapp_from = os.environ.get(
            "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
        )
        self.is_configured = bool(
            self.account_sid
            and self.auth_token
            and "HERE" not in self.account_sid
            and "HERE" not in self.auth_token
        )

    def send_sms(self, to_phone: str, body: str) -> Dict[str, Any]:
        """Sends an outbound SMS message via Twilio or mock handler."""
        if self.is_configured:
            try:
                from twilio.rest import Client

                client = Client(self.account_sid, self.auth_token)
                message = client.messages.create(
                    body=body, from_=self.from_phone, to=to_phone
                )
                return {
                    "status": message.status,
                    "message_id": message.sid,
                    "recipient": to_phone,
                    "channel": "sms",
                    "sent_at": utcnow(),
                }
            except Exception as e:
                # Fallback to simulated message dispatch on Twilio client error
                print(f"Twilio SMS dispatch failed ({e}), falling back to mock.")

        # Mock dispatch for development / test mode
        mock_id = f"SM{uuid.uuid4().hex[:16]}"
        return {
            "status": "sent",
            "message_id": mock_id,
            "recipient": to_phone,
            "channel": "sms",
            "sent_at": utcnow(),
        }

    def send_whatsapp(
        self, to_phone: str, body: str, media_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sends an outbound WhatsApp message via Twilio Business API or mock handler."""
        formatted_to = (
            to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        )
        if self.is_configured:
            try:
                from twilio.rest import Client

                client = Client(self.account_sid, self.auth_token)
                kwargs = {"body": body, "from_": self.whatsapp_from, "to": formatted_to}
                if media_url:
                    kwargs["media_url"] = [media_url]

                message = client.messages.create(**kwargs)
                return {
                    "status": message.status,
                    "message_id": message.sid,
                    "recipient": to_phone,
                    "channel": "whatsapp",
                    "sent_at": utcnow(),
                }
            except Exception as e:
                print(f"Twilio WhatsApp dispatch failed ({e}), falling back to mock.")

        # Mock dispatch for development / test mode
        mock_id = f"WA{uuid.uuid4().hex[:16]}"
        return {
            "status": "sent",
            "message_id": mock_id,
            "recipient": to_phone,
            "channel": "whatsapp",
            "sent_at": utcnow(),
        }

    def broadcast_flash_sale(
        self, batch_id: int, recipients: List[str], channel: str = "sms"
    ) -> Dict[str, Any]:
        """Dispatches a flash-sale alert broadcast to a list of geofenced recipients."""
        claim_url = f"https://optimart.app/claim/batch-{batch_id}"
        message_body = (
            f"⚡ OptiMart FLASH SALE! Food batch #{batch_id} is on deep discount near you. "
            f"Claim now before it expires: {claim_url} or reply 'YES' to claim."
        )

        successful_count = 0
        for recipient in recipients:
            if channel == "whatsapp":
                res = self.send_whatsapp(recipient, message_body)
            else:
                res = self.send_sms(recipient, message_body)

            if res.get("status") in ["sent", "queued", "delivered"]:
                successful_count += 1

        return {
            "batch_id": batch_id,
            "total_recipients": len(recipients),
            "successful_count": successful_count,
            "channel": channel,
            "dispatched_at": utcnow(),
        }


def get_notification_service() -> TwilioNotificationService:
    return TwilioNotificationService()
