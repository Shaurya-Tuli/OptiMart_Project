from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class NotificationSendRequest(BaseModel):
    recipient_phone: str = Field(..., json_schema_extra={"example": "+1234567890"})
    channel: str = Field(default="sms", json_schema_extra={"example": "sms"})
    batch_id: Optional[int] = Field(None, json_schema_extra={"example": 1})
    message_text: Optional[str] = Field(
        None,
        json_schema_extra={
            "example": "Flash Sale: Organic Milk 50% off! Claim now: https://optimart.app/c/abc"
        },
    )


class NotificationResponse(BaseModel):
    status: str
    message_id: str
    recipient: str
    channel: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BroadcastRequest(BaseModel):
    recipients: List[str] = Field(
        ..., json_schema_extra={"example": ["+1234567890", "+1987654321"]}
    )
    channel: str = Field(default="sms", json_schema_extra={"example": "sms"})


class BroadcastResponse(BaseModel):
    batch_id: int
    total_recipients: int
    successful_count: int
    channel: str
    dispatched_at: datetime


class InboundReplyResponse(BaseModel):
    action: str
    batch_id: Optional[int]
    status: str
    detail: str
