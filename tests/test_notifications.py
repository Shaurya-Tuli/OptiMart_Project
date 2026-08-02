from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.store import Store
from app.models.batch import Batch
from app.services.notification import TwilioNotificationService, get_notification_service

client = TestClient(app)


def test_twilio_notification_service_mock():
    service = TwilioNotificationService()
    # Test SMS dispatch
    sms_res = service.send_sms("+1234567890", "Test message")
    assert sms_res["status"] == "sent"
    assert sms_res["channel"] == "sms"
    assert sms_res["message_id"].startswith("SM")

    # Test WhatsApp dispatch
    wa_res = service.send_whatsapp("+1234567890", "Test WhatsApp message")
    assert wa_res["status"] == "sent"
    assert wa_res["channel"] == "whatsapp"
    assert wa_res["message_id"].startswith("WA")


def test_send_notification_endpoint():
    response = client.post(
        "/api/v1/notifications/send",
        json={
            "recipient_phone": "+1999888777",
            "channel": "sms",
            "message_text": "Direct test alert",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert data["recipient"] == "+1999888777"
    assert data["channel"] == "sms"


def test_broadcast_notifications_endpoint(db_session: Session):
    # 1. Create a store
    store = Store(name="Flash Sale Store", address="789 Market St")
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    # 2. Create a batch
    batch = Batch(
        store_id=store.id,
        sku="BAKERY-BREAD-01",
        product_name="Artisan Sourdough",
        category="Bakery",
        quantity=8,
        cost_price=1.0,
        original_selling_price=4.0,
        current_price=2.0,
        expiration_date=date.today() + timedelta(days=1),
        status="DISCOUNTED",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    # 3. Trigger broadcast
    response = client.post(
        f"/api/v1/notifications/broadcast/{batch.id}",
        json={"recipients": ["+1111222333", "+1444555666"], "channel": "sms"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["batch_id"] == batch.id
    assert data["total_recipients"] == 2
    assert data["successful_count"] == 2


def test_twilio_inbound_sms_webhook(db_session: Session):
    # Create store and batch
    store = Store(name="Inbound Webhook Store")
    db_session.add(store)
    db_session.commit()
    db_session.refresh(store)

    batch = Batch(
        store_id=store.id,
        sku="PRODUCE-APPLES",
        product_name="Honeycrisp Apples 1kg",
        category="Produce",
        quantity=20,
        cost_price=1.0,
        original_selling_price=3.0,
        current_price=1.5,
        expiration_date=date.today() + timedelta(days=2),
        status="ACTIVE",
    )
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)

    # Send Twilio inbound SMS form data
    response = client.post(
        "/api/v1/notifications/twilio-inbound",
        data={"From": "+1888777666", "Body": f"YES {batch.id}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "CLAIMED"
    assert data["batch_id"] == batch.id
    assert data["status"] == "SUCCESS"
