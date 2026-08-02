from app.api.stores import router as stores_router
from app.api.inventory import router as inventory_router
from app.api.pricing import router as pricing_router

__all__ = ["stores_router", "inventory_router", "pricing_router"]
