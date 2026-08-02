from typing import List, Dict, Any
from app.celery_app import celery_app
from app.services.notification import get_notification_service


@celery_app.task(name="app.tasks.dispatch.dispatch_batch_notifications_task")
def dispatch_batch_notifications_task(
    batch_id: int, recipients: List[str], channel: str = "sms"
) -> Dict[str, Any]:
    """Celery background worker task for broadcasting flash-sale alerts off the API event loop."""
    service = get_notification_service()
    return service.broadcast_flash_sale(
        batch_id=batch_id, recipients=recipients, channel=channel
    )
