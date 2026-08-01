import os
import redis
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db import check_db_connection, engine, Base
import app.models  # Ensures models are imported so Base.metadata knows about them
from app.api.stores import router as stores_router
from app.api.inventory import router as inventory_router
from app.api.pricing import router as pricing_router
from app.api.standing_orders import router as standing_orders_router
from app.api.notifications import router as notifications_router
from app.api.claims import router as claims_router
from app.api.payments import router as payments_router
from app.api.analytics import router as analytics_router
from app.api.assistant import router as assistant_router
from app.api.sales_history import router as sales_history_router
from app.ml.predictor import get_predictor



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Failed to create database tables on startup: {e}")

    # Ensure ML predictor model is loaded/trained on startup
    try:
        get_predictor()
    except Exception as e:
        print(f"Warning: Failed to load/train ML model on startup: {e}")

    yield


app = FastAPI(title="NEXPIRE API", version="0.1.0", lifespan=lifespan)

# Register API Routers
app.include_router(stores_router)
app.include_router(inventory_router)
app.include_router(pricing_router)
app.include_router(standing_orders_router)
app.include_router(notifications_router)
app.include_router(claims_router)
app.include_router(payments_router)
app.include_router(analytics_router)
app.include_router(assistant_router)
app.include_router(sales_history_router)




REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL)


# Serve the frontend dashboard
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
def root():
    return FileResponse("app/static/index.html")


@app.get("/claim/new")
def claim_new():
    """Consumer claim page for new claims from auction or SMS links."""
    return FileResponse("app/static/claim.html")


@app.get("/claim/{token}")
def claim_page(token: str):
    """Consumer claim page — shows deal details and lets the buyer confirm.
    Serves the dedicated claim.html (not the store dashboard).
    """
    return FileResponse("app/static/claim.html")


@app.get("/health")
def health():
    """Phase 0 proof-of-life check: confirms Postgres+PostGIS and Redis
    are both reachable from the API container."""
    db_ok = check_db_connection()
    try:
        redis_ok = redis_client.ping()
    except Exception:
        redis_ok = False

    return {
        "database": "ok" if db_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
        "healthy": db_ok and redis_ok,
    }
