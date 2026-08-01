from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.ml.forecaster import get_forecaster
from app.schemas.forecasting import ForecastResponse, ForecastTrainResponse

router = APIRouter(prefix="/api/v1/forecast", tags=["Demand Forecasting (Model D)"])


@router.post("/train", response_model=ForecastTrainResponse)
def train_forecasting_model(db: Session = Depends(get_db)):
    """Trigger training of Model D (Demand Forecasting) against live sales_history."""
    forecaster = get_forecaster()
    result = forecaster.train(db)
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("reason", "Model training failed"),
        )
    return result


@router.get("/predict", response_model=ForecastResponse)
def predict_demand(
    store_id: int = Query(..., description="Store ID"),
    sku: str = Query(..., description="SKU identifier"),
    category: Optional[str] = Query("General", description="Product category"),
    price_at_time: Optional[float] = Query(100.0, description="Price at forecast window"),
    promotion_flag: Optional[bool] = Query(False, description="Is promotion scheduled"),
    stockout_flag: Optional[bool] = Query(False, description="Is stockout currently active"),
    db: Session = Depends(get_db),
):
    """Get 7-day predicted demand, confidence interval bands, and top contributing factors."""
    forecaster = get_forecaster()
    return forecaster.predict_demand(
        db=db,
        store_id=store_id,
        sku=sku,
        category=category,
        price_at_time=price_at_time,
        promotion_flag=promotion_flag,
        stockout_flag=stockout_flag,
    )
