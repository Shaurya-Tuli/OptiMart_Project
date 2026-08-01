"""
predictor.py — NEXPIRE Model A (V2)
======================================
FastAPI-compatible predictor singleton.

The predict() interface is fully backward-compatible with V1:
  - All existing callers (API routes, tests) continue to work unchanged.
  - New fields added to the return dict: urgency_score, reasoning_tags.

Internal changes vs. V1:
  - days_to_expiry is now normalized via urgency.py before any model inference.
  - Discount selection delegates to price_engine.py (discrete revenue search).
  - Model artifact format changed to a dict (see trainer.py docstring).
  - Falls back gracefully to cold-start if model is unavailable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.ml.price_engine import (
    PriceEngine,
    PriceRecommendation,
    load_engine,
    recommend_discount,
    get_engine,
    CRITICAL_URGENCY_THRESHOLD,
)
from app.ml.urgency import compute_urgency, get_lookup
from app.ml.train_model import MODEL_ARTIFACT_PATH_V2
from app.ml.trainer import MODEL_ARTIFACT_PATH, train_pricing_model


from app.ml.discount_engine import calculate_discount, compute_hours_to_expiry


class PricingPredictor:
    """Singleton predictor for the NEXPIRE pricing model.

    Wraps price_engine.py, discount_engine.py and urgency.py behind the original predict() interface
    so existing FastAPI routes require zero changes.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or MODEL_ARTIFACT_PATH_V2
        self._engine: Optional[PriceEngine] = None
        self._load_or_train()

    def _load_or_train(self) -> None:
        """Load the V2 model artifact, training it if not yet available."""
        if not Path(self.model_path).exists():
            print(
                f"[PricingPredictor] Model not found at {self.model_path}. "
                "Training initial model (this may take ~30s)..."
            )
            train_pricing_model(artifact_path=self.model_path)

        self._engine = load_engine(model_path=self.model_path)

    def reload(self) -> None:
        """Reload the model artifact from disk (call after retraining)."""
        self._load_or_train()

    def predict(
        self,
        days_to_expiry: float,
        category: str,
        quantity: int,
        cost_price: float,
        original_selling_price: float,
        temperature_c: float = 28.0,
        historical_demand_factor: float = 1.0,
        product_condition: str = "Excellent",
        # Optional extended context (new in V2)
        precip_probability: float = 0.2,
        is_weekend: int = 0,
        is_holiday: int = 0,
        hour_of_day: int = 12,
        store_foot_traffic_index: float = 0.5,
        past_discount_depth: float = 0.0,
        past_sellthrough_rate: float = 0.7,
        local_demand_score: float = 0.5,
        b2b_flag: int = 0,
        force_liquidate: bool = False,
        hours_to_expiry: Optional[float] = None,
        # Closed-loop integration parameters (Phase 12)
        store_id: Optional[int] = None,
        sku: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if self._engine is None:
            self._load_or_train()

        # Compute standardized hours_to_expiry
        h_to_expiry = compute_hours_to_expiry(days_to_expiry, hours_to_expiry)
        effective_days = h_to_expiry / 24.0

        # Compute urgency score
        urgency_score, is_invalid = compute_urgency(
            days_to_expiry=effective_days,
            category=category,
            lookup=self._engine.shelf_life_lookup if self._engine else get_lookup(),
            hours_to_expiry=h_to_expiry,
        )

        # Base risk score incorporating category sensitivity and demand factor
        risk_score = round(urgency_score, 4)

        # Closed-loop integration check (Phase 12)
        underperformance_detected = False
        if db is not None and store_id is not None and sku is not None:
            try:
                from app.models.reorder_recommendation import ReorderRecommendation
                from app.models.sales_history import SalesHistory
                from sqlalchemy import desc, func
                from datetime import timedelta

                # Get latest forecast recommendation
                rec = (
                    db.query(ReorderRecommendation)
                    .filter(
                        ReorderRecommendation.store_id == store_id,
                        ReorderRecommendation.sku == sku,
                    )
                    .order_by(desc(ReorderRecommendation.forecast_run_date))
                    .first()
                )

                if rec and rec.predicted_demand > 0:
                    # Get the most recent sales date to align the 7-day history window
                    max_sales_date = (
                        db.query(SalesHistory.date)
                        .filter(
                            SalesHistory.store_id == store_id,
                            SalesHistory.sku == sku,
                        )
                        .order_by(desc(SalesHistory.date))
                        .first()
                    )
                    if max_sales_date:
                        start_date = max_sales_date[0] - timedelta(days=6)
                        actual_sales = (
                            db.query(func.sum(SalesHistory.units_sold))
                            .filter(
                                SalesHistory.store_id == store_id,
                                SalesHistory.sku == sku,
                                SalesHistory.date >= start_date,
                                SalesHistory.date <= max_sales_date[0],
                            )
                            .scalar()
                        ) or 0

                        # If actual sales are less than 70% of forecast, SKU is underperforming
                        if actual_sales < 0.70 * rec.predicted_demand:
                            underperformance_detected = True
            except Exception as e:
                # Log error but don't crash prediction
                print(f"[PricingPredictor] Error during closed-loop forecast check: {e}")

        if underperformance_detected:
            # Add boost to risk score (cap at 1.0)
            risk_score = round(min(1.0, risk_score + 0.25), 4)

        # Categorize risk level continuously
        if risk_score < 0.25:
            risk_level = "LOW"
        elif risk_score < 0.50:
            risk_level = "MEDIUM"
        elif risk_score < 0.75:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        # Calculate continuous, standardized discount using calculate_discount formula
        categories_cfg = self._engine.shelf_life_lookup.get("categories", {}) if self._engine else {}
        cat_cfg = categories_cfg.get(category, {})
        max_d = float(cat_cfg.get("markdown_ceiling_pct", 70.0))

        discount_pct = calculate_discount(
            risk_score=risk_score,
            product_condition=product_condition,
            category=category,
            custom_max_discount=max_d,
        )

        # Margin floor protection unless force_liquidate is set
        suggested_price = round(original_selling_price * (1.0 - discount_pct / 100.0), 2)
        if not force_liquidate and suggested_price < cost_price and original_selling_price > 0:
            max_allowed_disc = max(0.0, (1.0 - cost_price / original_selling_price) * 100.0)
            discount_pct = round(min(discount_pct, max_allowed_disc), 2)
            suggested_price = round(original_selling_price * (1.0 - discount_pct / 100.0), 2)

        reasoning_tags = []
        if is_weekend:
            reasoning_tags.append("weekend_demand_boost")
        if force_liquidate:
            reasoning_tags.append("force_liquidate")
        if underperformance_detected:
            reasoning_tags.append("forecast_underperformance_detected")

        return {
            "risk_score": risk_score,
            "suggested_discount_percentage": discount_pct,
            "suggested_price": suggested_price,
            "risk_level": risk_level,
            "urgency_score": urgency_score,
            "hours_to_expiry": h_to_expiry,
            "expected_sell_probability": round(0.40 + 0.45 * (discount_pct / 100.0), 4),
            "reasoning_tags": reasoning_tags,
            "is_cold_start": not self._engine.available if self._engine else True,
        }


# ---------------------------------------------------------------------------
# Singleton predictor instance (matches V1 pattern)
# ---------------------------------------------------------------------------
predictor_instance: Optional[PricingPredictor] = None


def get_predictor() -> PricingPredictor:
    """Return the module-level singleton predictor (lazy-loaded)."""
    global predictor_instance
    if predictor_instance is None:
        predictor_instance = PricingPredictor()
    return predictor_instance
