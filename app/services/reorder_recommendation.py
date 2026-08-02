from datetime import date
import json
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.batch import Batch
from app.models.reorder_recommendation import ReorderRecommendation
from app.ml.forecaster import get_forecaster
from app.schemas.reorder_recommendation import ReorderDecisionRequest


def generate_reorder_recommendations(db: Session, store_id: int) -> List[ReorderRecommendation]:
    """Generate optimal reorder recommendations for a store using Model D forecasts."""
    # Find all unique store/SKU combinations from batches to evaluate
    unique_skus = db.query(Batch.sku, Batch.category, Batch.original_selling_price).filter(
        Batch.store_id == store_id
    ).distinct().all()

    if not unique_skus:
        return []

    forecaster = get_forecaster()
    run_date = date.today()
    recommendations = []

    base_pct_map = {
        "Dairy": 0.10,
        "Produce": 0.10,
        "Bakery": 0.15,
        "Meat": 0.15,
        "Beverages": 0.20,
        "General": 0.15
    }

    for sku, category, price in unique_skus:
        # 1. Query current quantity on hand (sum of ACTIVE/DISCOUNTED batches)
        current_qty = db.query(func.sum(Batch.quantity)).filter(
            Batch.store_id == store_id,
            Batch.sku == sku,
            Batch.status.in_(["ACTIVE", "DISCOUNTED"])
        ).scalar() or 0

        # 2. Get predictions from forecaster
        pred = forecaster.predict_demand(
            db=db,
            store_id=store_id,
            sku=sku,
            category=category,
            price_at_time=price or 100.0,
        )

        pred_demand = pred["predicted_demand_next_7d"]
        conf_low = pred["confidence_low"]
        conf_high = pred["confidence_high"]
        is_cold_start = pred["is_cold_start"]
        top_factors = pred["top_factors"]

        # 3. Calculate safety stock buffer scaling inversely with confidence
        # confidence maps from 0.0 (maximum uncertainty) to 1.0 (perfect certainty)
        spread = conf_high - conf_low
        if pred_demand > 0:
            confidence = 1.0 - min(1.0, spread / pred_demand)
        else:
            confidence = 1.0

        base_pct = base_pct_map.get(category, 0.15)
        # Scales inversely with confidence: confidence=1.0 -> multiplier=1.0; confidence=0.0 -> multiplier=2.0
        safety_stock = pred_demand * base_pct * (2.0 - confidence)

        # 4. Compute recommended reorder quantity
        recommended_qty = max(0, int(round(pred_demand + safety_stock - current_qty)))

        # 5. Upsert recommendation record
        stmt = insert(ReorderRecommendation).values(
            store_id=store_id,
            sku=sku,
            forecast_run_date=run_date,
            predicted_demand=pred_demand,
            confidence_low=conf_low,
            confidence_high=conf_high,
            recommended_qty=recommended_qty,
            top_factors=top_factors,
            retailer_decision="PENDING",
            adjusted_qty=None,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["store_id", "sku", "forecast_run_date"],
            set_={
                "predicted_demand": stmt.excluded.predicted_demand,
                "confidence_low": stmt.excluded.confidence_low,
                "confidence_high": stmt.excluded.confidence_high,
                "recommended_qty": stmt.excluded.recommended_qty,
                "top_factors": stmt.excluded.top_factors,
            }
        )
        db.execute(stmt)

    db.commit()

    # Query and return recommendations for the run_date
    return db.query(ReorderRecommendation).filter(
        ReorderRecommendation.store_id == store_id,
        ReorderRecommendation.forecast_run_date == run_date
    ).all()


def update_reorder_decision(
    db: Session, recommendation_id: int, payload: ReorderDecisionRequest
) -> ReorderRecommendation:
    """Accept, adjust, or dismiss a reorder recommendation."""
    rec = db.query(ReorderRecommendation).filter(ReorderRecommendation.id == recommendation_id).first()
    if not rec:
        return None

    decision = payload.decision.upper()
    if decision not in ["ACCEPTED", "ADJUSTED", "DISMISSED"]:
        raise ValueError("Invalid decision type. Must be ACCEPTED, ADJUSTED, or DISMISSED.")

    rec.retailer_decision = decision
    if decision == "ADJUSTED":
        if payload.adjusted_qty is None:
            raise ValueError("adjusted_qty is required when decision is ADJUSTED.")
        rec.adjusted_qty = payload.adjusted_qty
    else:
        rec.adjusted_qty = None

    db.commit()
    db.refresh(rec)
    return rec


def get_store_recommendations(
    db: Session, store_id: int, forecast_run_date: Optional[date] = None
) -> List[ReorderRecommendation]:
    """Retrieve reorder recommendations for a store, default to the latest date."""
    query = db.query(ReorderRecommendation).filter(ReorderRecommendation.store_id == store_id)
    if forecast_run_date:
        query = query.filter(ReorderRecommendation.forecast_run_date == forecast_run_date)
    else:
        # Default to latest date
        latest_date = db.query(func.max(ReorderRecommendation.forecast_run_date)).filter(
            ReorderRecommendation.store_id == store_id
        ).scalar()
        if latest_date:
            query = query.filter(ReorderRecommendation.forecast_run_date == latest_date)
        else:
            return []

    return query.order_by(ReorderRecommendation.sku).all()
