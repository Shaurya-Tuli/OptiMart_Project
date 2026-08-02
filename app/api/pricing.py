from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.store import Store
from app.models.batch import Batch
from app.ml.predictor import get_predictor
from app.ml.trainer import train_pricing_model
from app.services.weather import get_temperature_c
from app.schemas.pricing import (
    PricePredictionRequest,
    PricePredictionResponse,
    BatchRepriceResponse,
    ModelTrainResponse,
)

router = APIRouter(prefix="/api/v1/ml", tags=["ML Dynamic Discounting"])


@router.post("/predict-discount", response_model=PricePredictionResponse)
def predict_discount(request: PricePredictionRequest):
    """Infer risk score and optimal discount percentage for given item features."""
    predictor = get_predictor()
    result = predictor.predict(
        days_to_expiry=request.days_to_expiry,
        category=request.category,
        quantity=request.quantity,
        cost_price=request.cost_price,
        original_selling_price=request.original_selling_price,
        temperature_c=request.temperature_c or 25.0,
        historical_demand_factor=request.historical_demand_factor or 1.0,
        product_condition=request.product_condition or "Excellent",
    )
    return PricePredictionResponse(**result)


@router.post("/reprice-batch/{batch_id}", response_model=BatchRepriceResponse)
async def reprice_batch(batch_id: int, db: Session = Depends(get_db)):
    """Evaluate batch risk using ML model and apply optimal dynamic discount and price in database."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch with id {batch_id} not found",
        )

    store = db.query(Store).filter(Store.id == batch.store_id).first()
    lat = store.location_lat if store else None
    lng = store.location_lng if store else None

    # Fetch ambient temperature from weather service
    temp_c = await get_temperature_c(lat, lng)

    # Calculate days to expiry
    today = date.today()
    days_left = (batch.expiration_date - today).days
    days_to_expiry = max(0.1, float(days_left))

    predictor = get_predictor()
    prediction = predictor.predict(
        days_to_expiry=days_to_expiry,
        category=batch.category,
        quantity=batch.quantity,
        cost_price=batch.cost_price,
        original_selling_price=batch.original_selling_price,
        temperature_c=temp_c,
        store_id=batch.store_id,
        sku=batch.sku,
        db=db,
    )

    prev_price = batch.current_price
    prev_discount = batch.discount_percentage

    # Apply new ML prediction
    new_discount = prediction["suggested_discount_percentage"]
    new_price = prediction["suggested_price"]
    risk_score = prediction["risk_score"]
    risk_level = prediction["risk_level"]

    batch.discount_percentage = new_discount
    batch.current_price = new_price

    # Auto-update status if expired or near critical
    if days_left <= 0:
        batch.status = "EXPIRED"

    db.commit()
    db.refresh(batch)

    return BatchRepriceResponse(
        batch_id=batch.id,
        sku=batch.sku,
        product_name=batch.product_name,
        previous_price=prev_price,
        previous_discount=prev_discount,
        new_price=new_price,
        new_discount=new_discount,
        risk_score=risk_score,
        risk_level=risk_level,
        status=batch.status,
        reasoning_tags=prediction.get("reasoning_tags", []),
    )


@router.post("/train", response_model=ModelTrainResponse)
def train_model(num_samples: int = Query(1500, ge=100, le=10000)):
    """Trigger on-demand retraining of the ML pricing model."""
    try:
        artifact_path = train_pricing_model(num_samples=num_samples)
        predictor = get_predictor()
        predictor.reload()

        return ModelTrainResponse(
            status="SUCCESS",
            samples_trained=num_samples,
            artifact_path=artifact_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model training failed: {str(e)}",
        )
