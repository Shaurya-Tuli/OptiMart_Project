from app.celery_app import celery_app
from app.db import SessionLocal
from app.models.store import Store
from app.services.reorder_recommendation import generate_reorder_recommendations


@celery_app.task(name="app.tasks.forecasting.run_weekly_forecast_task")
def run_weekly_forecast_task() -> dict:
    """Scheduled Celery task that runs forecast calculations for all stores."""
    db = SessionLocal()
    try:
        stores = db.query(Store.id).all()
        store_ids = [s[0] for s in stores]

        results = {}
        for s_id in store_ids:
            recs = generate_reorder_recommendations(db, s_id)
            results[s_id] = len(recs)

        return {"status": "success", "processed_stores": results}
    finally:
        db.close()
