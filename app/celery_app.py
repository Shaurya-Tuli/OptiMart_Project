import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "optimart",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Suppress CPendingDeprecationWarning from Celery 5 → 6 migration:
    # explicitly retain the current "retry on startup" behaviour.
    broker_connection_retry_on_startup=True,
)

# Include task modules
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task
def ping():
    return "pong"
