"""
price_engine.py — OptiMart Model A
====================================
The core discount-selection engine.

Takes a batch's current state and returns the revenue-maximizing discount
subject to hard margin constraints and urgency overrides.

This module is a pure function library with no side effects — it can be called
synchronously from a FastAPI route, a Celery task, or a CLI script without
modification.

Usage:
    from app.ml.price_engine import recommend_discount, load_engine

    engine = load_engine()   # loads model + shelf-life config
    result = recommend_discount(
        batch_info={
            "category": "Dairy",
            "days_to_expiry": 2,
            "current_price": 75.0,
            "cost_price": 40.0,
            "qty_on_hand": 30,
            ...
        },
        engine=engine,
    )
    # result.discount_pct, result.final_price, result.reasoning_tags, ...

Algorithm (Steps 4 + 5 from spec):
  1. Compute urgency_score from category_shelf_life.json lookup.
  2. If model artifact is unavailable or category is unknown: cold-start fallback.
  3. Discrete price search over [0%, 10%, ..., 70%] (configurable):
       candidate_price = current_price * (1 - d/100)
       features = build_feature_vector(batch_info, discount=d)
       sell_prob = model.predict(features)
       expected_revenue = sell_prob * candidate_price
  4. Hard constraints (applied in order):
       a. urgency_score > CRITICAL_URGENCY_THRESHOLD → force max discount
       b. candidate_price < cost_price → skip unless force_liquidate=True
       c. Discount clipped to allowed discrete steps.
  5. Return PriceRecommendation dataclass.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from app.ml.urgency import compute_urgency, load_shelf_life_lookup
from app.ml.discount_engine import calculate_discount, DAMAGE_MULTIPLIERS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_DEFAULT_MODEL_PATH = str(_HERE / "artifacts" / "pricing_model_v2.joblib")
_SHELF_LIFE_CONFIG_PATH = str(_HERE / "category_shelf_life.json")

# Urgency threshold above which we override discount to maximum (sell-through > margin)
CRITICAL_URGENCY_THRESHOLD = 0.90

# Discrete discount steps to search over (percent)
DEFAULT_DISCOUNT_STEPS = [0, 10, 20, 30, 40, 50, 60, 70]

# Reasoning tag constants
TAG_HIGH_URGENCY_OVERRIDE = "high_urgency_override"
TAG_WEATHER_LOW_DEMAND = "weather_low_demand"
TAG_WEATHER_HIGH_DEMAND = "weather_high_demand"
TAG_COLD_START_FALLBACK = "cold_start_fallback"
TAG_FORCE_LIQUIDATE = "force_liquidate"
TAG_MARGIN_FLOOR_PROTECTED = "margin_floor_protected"
TAG_WEEKEND_DEMAND_BOOST = "weekend_demand_boost"
TAG_B2B_ADJUSTED = "b2b_adjusted"
TAG_INVALID_DAYS_INPUT = "invalid_days_to_expiry"


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------
@dataclass
class PriceRecommendation:
    """Output of recommend_discount().

    Attributes:
        discount_pct: Recommended discount percentage (0–70, discrete step).
        final_price: Suggested price after discount (always >= cost_price unless force_liquidate).
        expected_sell_probability: Model's predicted P(sale) at this price.
        urgency_score: Normalized urgency [0, 1].
        reasoning_tags: Human-readable tags explaining the recommendation.
        is_cold_start: True if fallback (no trained model) was used.
        is_invalid_input: True if days_to_expiry > shelf_life (data quality flag).
    """
    discount_pct: float
    final_price: float
    expected_sell_probability: float
    urgency_score: float
    reasoning_tags: List[str] = field(default_factory=list)
    is_cold_start: bool = False
    is_invalid_input: bool = False


# ---------------------------------------------------------------------------
# Engine loader
# ---------------------------------------------------------------------------
@dataclass
class PriceEngine:
    """Holds the loaded model artifact + shelf-life lookup."""
    model: Any                          # sklearn HistGradientBoostingRegressor
    preprocessor: Any                   # sklearn ColumnTransformer
    feature_cols: List[str]
    shelf_life_lookup: Dict[str, Any]
    available: bool = True              # False if model could not be loaded


def load_engine(
    model_path: Optional[str] = None,
    config_path: Optional[str] = None,
) -> PriceEngine:
    """Load the trained model artifact and shelf-life config.

    If the model artifact does not exist, returns a PriceEngine with
    available=False so recommend_discount() falls back to cold-start.

    Args:
        model_path: Override path to the Joblib artifact.
        config_path: Override path to category_shelf_life.json.

    Returns:
        PriceEngine instance.
    """
    lookup = load_shelf_life_lookup(config_path or _SHELF_LIFE_CONFIG_PATH)
    mp = model_path or _DEFAULT_MODEL_PATH

    if not Path(mp).exists():
        return PriceEngine(
            model=None,
            preprocessor=None,
            feature_cols=[],
            shelf_life_lookup=lookup,
            available=False,
        )

    artifact = joblib.load(mp)
    return PriceEngine(
        model=artifact["model"],
        preprocessor=artifact["preprocessor"],
        feature_cols=artifact["feature_cols"],
        shelf_life_lookup=lookup,
        available=True,
    )


# ---------------------------------------------------------------------------
# Cold-start fallback
# ---------------------------------------------------------------------------
def _cold_start_discount(
    urgency_score: float,
    cat_config: Dict[str, Any],
    force_liquidate: bool = False,
    product_condition: str = "Excellent",
    category: str = "Dairy",
) -> Tuple[float, float]:
    """Fallback discount selection when model is unavailable or category is unknown.

    Uses calculate_discount formula function.

    Returns:
        Tuple (discount_pct, estimated_sell_probability)
    """
    markdown_ceiling = float(cat_config.get("markdown_ceiling_pct", 70.0))
    discount = calculate_discount(
        risk_score=urgency_score,
        product_condition=product_condition,
        category=category,
        custom_max_discount=markdown_ceiling,
    )
    sell_prob = 0.40 + 0.45 * (discount / 100.0)

    if force_liquidate:
        discount = min(markdown_ceiling, 70.0)
        sell_prob = max(sell_prob, 0.80)

    return float(discount), float(sell_prob)


# ---------------------------------------------------------------------------
# Feature vector builder
# ---------------------------------------------------------------------------
def _build_feature_row(batch_info: Dict[str, Any], discount_pct: float) -> Dict[str, Any]:
    """Build a single feature row dict at a given candidate discount level.

    Applies the discount to current_price so the model sees the candidate price.
    """
    candidate_price = batch_info["current_price"] * (1.0 - discount_pct / 100.0)
    weather_sens = batch_info.get("_weather_sensitivity", 0.3)
    temp = float(batch_info.get("temperature_today", 28.0))
    precip = float(batch_info.get("precip_probability", 0.2))
    temp_norm = (temp - 25.0) / 20.0

    return {
        "urgency_score": batch_info["urgency_score"],
        "category": batch_info["category"],
        "current_price": candidate_price,
        "cost_price": batch_info["cost_price"],
        "qty_on_hand": int(batch_info.get("qty_on_hand", 20)),
        "avg_daily_velocity_7d": float(batch_info.get("avg_daily_velocity_7d", 10.0)),
        "avg_daily_velocity_28d": float(batch_info.get("avg_daily_velocity_28d", 10.0)),
        "temperature_today": temp,
        "precip_probability": precip,
        "is_weekend": int(batch_info.get("is_weekend", 0)),
        "is_holiday": int(batch_info.get("is_holiday", 0)),
        "hour_of_day": int(batch_info.get("hour_of_day", 12)),
        "store_foot_traffic_index": float(batch_info.get("store_foot_traffic_index", 0.5)),
        "past_discount_depth": float(batch_info.get("past_discount_depth", 0.0)),
        "past_sellthrough_rate": float(batch_info.get("past_sellthrough_rate", 0.7)),
        "local_demand_score": float(batch_info.get("local_demand_score", 0.5)),
        "b2b_flag": int(batch_info.get("b2b_flag", 0)),
        "cat_x_temp": round(weather_sens * temp_norm, 4),
        "cat_x_precip": round(weather_sens * precip, 4),
    }


# ---------------------------------------------------------------------------
# Core recommendation function
# ---------------------------------------------------------------------------
def recommend_discount(
    batch_info: Dict[str, Any],
    engine: PriceEngine,
    discount_steps: Optional[List[int]] = None,
    force_liquidate: bool = False,
) -> PriceRecommendation:
    """Recommend the revenue-maximizing discount for a product batch.

    Args:
        batch_info: Dict with the following keys:
            category (str), days_to_expiry (float),
            current_price (float), cost_price (float),
            qty_on_hand (int, optional),
            avg_daily_velocity_7d (float, optional),
            avg_daily_velocity_28d (float, optional),
            temperature_today (float, optional),
            precip_probability (float, optional),
            is_weekend (int 0/1, optional),
            is_holiday (int 0/1, optional),
            hour_of_day (int, optional),
            store_foot_traffic_index (float, optional),
            past_discount_depth (float, optional),
            past_sellthrough_rate (float, optional),
            local_demand_score (float, optional),
            b2b_flag (int 0/1, optional).
        engine: Loaded PriceEngine from load_engine().
        discount_steps: Discrete discount percentages to search.
                        Defaults to [0, 10, 20, ..., 70].
        force_liquidate: If True, allows price to drop below cost_price.
                         Use for near-total-loss batches (e.g. damaged, about to expire).

    Returns:
        PriceRecommendation dataclass.

    Constraint ordering (applied before revenue optimisation):
      1. urgency_score > CRITICAL_URGENCY_THRESHOLD → force max discount.
      2. candidate_price < cost_price → skip (unless force_liquidate=True).
      3. Clip to discrete steps.
    """
    steps = discount_steps if discount_steps is not None else DEFAULT_DISCOUNT_STEPS
    tags: List[str] = []

    category = batch_info.get("category", "")
    current_price = float(batch_info.get("current_price", 100.0))
    cost_price = float(batch_info.get("cost_price", 50.0))
    hours_to_expiry = batch_info.get("hours_to_expiry")
    if hours_to_expiry is None and "days_to_expiry" in batch_info:
        hours_to_expiry = float(batch_info["days_to_expiry"]) * 24.0
    
    days_to_expiry = hours_to_expiry / 24.0 if hours_to_expiry is not None else float(batch_info.get("days_to_expiry", 1.0))
    temperature = float(batch_info.get("temperature_today", 28.0))
    precip = float(batch_info.get("precip_probability", 0.2))
    is_weekend = bool(batch_info.get("is_weekend", 0))
    product_condition = str(batch_info.get("product_condition", "Excellent"))

    # --- Step 1: Urgency normalization ---
    lookup = engine.shelf_life_lookup
    categories_cfg = lookup.get("categories", {})
    cat_config = categories_cfg.get(category, lookup["_default_fallback"])
    weather_sensitivity = float(cat_config.get("weather_sensitivity", 0.2))
    markdown_ceiling = float(cat_config.get("markdown_ceiling_pct", 40.0))

    urgency_score, is_invalid = compute_urgency(days_to_expiry, category, lookup, hours_to_expiry=hours_to_expiry)

    if is_invalid:
        tags.append(TAG_INVALID_DAYS_INPUT)

    # Annotate batch_info with computed values for feature builder
    batch_info = dict(batch_info)
    batch_info["urgency_score"] = urgency_score
    batch_info["_weather_sensitivity"] = weather_sensitivity

    # --- Context-based tags ---
    if is_weekend:
        tags.append(TAG_WEEKEND_DEMAND_BOOST)
    if temperature > 33.0 and weather_sensitivity > 0.4:
        tags.append(TAG_WEATHER_HIGH_DEMAND)
    elif precip > 0.6 and weather_sensitivity > 0.3:
        tags.append(TAG_WEATHER_LOW_DEMAND)
    if batch_info.get("b2b_flag", 0):
        tags.append(TAG_B2B_ADJUSTED)
    if force_liquidate:
        tags.append(TAG_FORCE_LIQUIDATE)

    # --- Hard Constraint 1: Critical urgency → force max discount ---
    if urgency_score > CRITICAL_URGENCY_THRESHOLD:
        tags.append(TAG_HIGH_URGENCY_OVERRIDE)
        max_step = min(max(steps), int(markdown_ceiling // 10) * 10)
        final_discount = float(max_step)
        final_price = round(current_price * (1.0 - final_discount / 100.0), 2)
        # Estimate sell prob via cold start since we're overriding anyway
        if engine.available:
            try:
                row = _build_feature_row(batch_info, final_discount)
                df = pd.DataFrame([row])[engine.feature_cols]
                X_enc = engine.preprocessor.transform(df)
                sell_prob = float(np.clip(engine.model.predict(X_enc)[0], 0.01, 0.99))
            except Exception:
                sell_prob = 0.80
        else:
            sell_prob = 0.80
            tags.append(TAG_COLD_START_FALLBACK)

        return PriceRecommendation(
            discount_pct=final_discount,
            final_price=final_price,
            expected_sell_probability=sell_prob,
            urgency_score=urgency_score,
            reasoning_tags=tags,
            is_cold_start=not engine.available,
            is_invalid_input=is_invalid,
        )

    # --- Cold-start fallback ---
    if not engine.available:
        tags.append(TAG_COLD_START_FALLBACK)
        discount, sell_prob = _cold_start_discount(urgency_score, cat_config, force_liquidate, product_condition=product_condition, category=category)
        final_price = round(current_price * (1.0 - discount / 100.0), 2)
        if not force_liquidate and final_price < cost_price:
            discount = max(
                0.0, round((1.0 - cost_price / current_price) * 100.0 / 10) * 10
            )
            final_price = round(current_price * (1.0 - discount / 100.0), 2)
            tags.append(TAG_MARGIN_FLOOR_PROTECTED)
        return PriceRecommendation(
            discount_pct=discount,
            final_price=final_price,
            expected_sell_probability=sell_prob,
            urgency_score=urgency_score,
            reasoning_tags=tags,
            is_cold_start=True,
            is_invalid_input=is_invalid,
        )

    # --- Step 3: Discrete revenue search ---
    best_discount = 0.0
    best_revenue = -1.0
    best_sell_prob = 0.0

    for d in steps:
        candidate_price = current_price * (1.0 - d / 100.0)

        # Hard Constraint 2: margin floor
        if not force_liquidate and candidate_price < cost_price:
            continue

        # Build feature vector at this candidate discount
        try:
            row = _build_feature_row(batch_info, float(d))
            df = pd.DataFrame([row])[engine.feature_cols]
            X_enc = engine.preprocessor.transform(df)
            sell_prob = float(np.clip(engine.model.predict(X_enc)[0], 0.01, 0.99))
        except Exception:
            # Robust to partial model failures — use cold start for this step
            sell_prob = _cold_start_discount(urgency_score, cat_config)[1]

        expected_revenue = sell_prob * candidate_price

        if expected_revenue > best_revenue:
            best_revenue = expected_revenue
            best_discount = float(d)
            best_sell_prob = sell_prob

    # Enforce markdown ceiling from category config
    max_allowed = min(max(steps), int(markdown_ceiling // 10) * 10)
    best_discount = min(best_discount, max_allowed)

    final_price = round(current_price * (1.0 - best_discount / 100.0), 2)

    # Final margin floor check (edge case: best_discount somehow slips through)
    if not force_liquidate and final_price < cost_price:
        best_discount = max(0.0, round((1.0 - cost_price / current_price) * 100.0 / 10) * 10)
        final_price = round(current_price * (1.0 - best_discount / 100.0), 2)
        tags.append(TAG_MARGIN_FLOOR_PROTECTED)

    return PriceRecommendation(
        discount_pct=best_discount,
        final_price=final_price,
        expected_sell_probability=round(best_sell_prob, 4),
        urgency_score=round(urgency_score, 4),
        reasoning_tags=tags,
        is_cold_start=False,
        is_invalid_input=is_invalid,
    )


# ---------------------------------------------------------------------------
# Module-level singleton engine (lazily loaded)
# ---------------------------------------------------------------------------
_ENGINE: Optional[PriceEngine] = None


def get_engine(model_path: Optional[str] = None) -> PriceEngine:
    """Return the module-level cached engine (lazy-loaded on first call)."""
    global _ENGINE
    if _ENGINE is None or not _ENGINE.available:
        _ENGINE = load_engine(model_path)
    return _ENGINE


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    print("Loading engine...")
    engine = load_engine()
    if not engine.available:
        print("Model not found — running with cold-start fallback.")
    else:
        print("Model loaded successfully.")

    test_cases = [
        {
            "label": "Dairy — imminent expiry (2 days left, 45 units)",
            "batch": {
                "category": "Dairy",
                "days_to_expiry": 2,
                "current_price": 75.0,
                "cost_price": 40.0,
                "qty_on_hand": 45,
                "temperature_today": 32.0,
                "is_weekend": 1,
            },
        },
        {
            "label": "Perfume — plenty of time (300 days left)",
            "batch": {
                "category": "Perfume & Cosmetics",
                "days_to_expiry": 300,
                "current_price": 999.0,
                "cost_price": 400.0,
                "qty_on_hand": 10,
                "temperature_today": 28.0,
            },
        },
        {
            "label": "Bakery — 1 day left, force_liquidate=True",
            "batch": {
                "category": "Bakery",
                "days_to_expiry": 1,
                "current_price": 45.0,
                "cost_price": 40.0,  # very tight margin
                "qty_on_hand": 20,
                "is_holiday": 0,
            },
            "force_liquidate": True,
        },
        {
            "label": "Food Grains — brand new stock (200 days left)",
            "batch": {
                "category": "Food Grains",
                "days_to_expiry": 200,
                "current_price": 120.0,
                "cost_price": 80.0,
                "qty_on_hand": 200,
            },
        },
    ]

    print(f"\n{'='*65}")
    for tc in test_cases:
        result = recommend_discount(
            batch_info=tc["batch"],
            engine=engine,
            force_liquidate=tc.get("force_liquidate", False),
        )
        print(f"\n[{tc['label']}]")
        print(f"  Urgency Score:      {result.urgency_score:.4f}")
        print(f"  Recommended Disc:   {result.discount_pct:.0f}%")
        print(f"  Final Price:        ₹{result.final_price:.2f}")
        print(f"  Sell Probability:   {result.expected_sell_probability:.4f}")
        print(f"  Tags:               {result.reasoning_tags}")
        print(f"  Cold Start:         {result.is_cold_start}")
    print(f"\n{'='*65}")
