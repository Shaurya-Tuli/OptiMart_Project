"""
evaluate.py — OptiMart Model A
================================
Evaluation report on the held-out time window (most recent 20% of data).

Compares:
  - Baseline: LinearRegression (sanity floor)
  - Production: HistGradientBoostingRegressor

Metrics:
  - MAE (Mean Absolute Error) on sell_probability
  - RMSE (Root Mean Squared Error) on sell_probability
  - Per-category MAE breakdown (shows where the model under/over-performs)
  - Revenue error: difference between expected revenue at recommended discount
    vs. oracle best-possible revenue from the ground-truth sell probability.

Usage:
    python app/ml/evaluate.py
    # or:
    python -m app.ml.evaluate
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent.parent))

from app.ml.synthetic_data import generate_synthetic_dataset, CATEGORIES
from app.ml.train_model import (
    FEATURE_COLS,
    TARGET_COL,
    build_preprocessor,
    time_based_split,
    MODEL_ARTIFACT_PATH_V2,
)


def load_val_data(random_seed: int = 42, num_samples: int = 5000):
    """Re-generate the same synthetic dataset and return the held-out val split."""
    df = generate_synthetic_dataset(num_samples=num_samples, random_seed=random_seed)
    _, df_val = time_based_split(df, train_fraction=0.80)
    return df_val


def _rmse(y_true, y_pred) -> float:
    return math.sqrt(mean_squared_error(y_true, y_pred))


def evaluate(
    model_path: str = MODEL_ARTIFACT_PATH_V2,
    num_samples: int = 5000,
    random_seed: int = 42,
    verbose: bool = True,
) -> Dict:
    """Run full evaluation and return metrics dict.

    Args:
        model_path: Path to the saved Joblib artifact.
        num_samples: Must match the number used during training.
        random_seed: Must match seed used during training.
        verbose: Print results to stdout.

    Returns:
        dict with keys: baseline, production, per_category.
    """
    if verbose:
        print(f"\n{'='*60}")
        print("OptiMart Model A — Evaluation Report")
        print(f"{'='*60}")

    # --- Load held-out data ---
    df_val = load_val_data(num_samples=num_samples, random_seed=random_seed)
    X_val = df_val[FEATURE_COLS]
    y_val = df_val[TARGET_COL].values

    if verbose:
        print(f"Held-out validation rows: {len(df_val):,}")
        print(f"Date range: {df_val['date'].min().date()} → {df_val['date'].max().date()}")

    # --- Load production model ---
    if not Path(model_path).exists():
        print(f"\nERROR: Model artifact not found at {model_path}")
        print("Run: python -m app.ml.train_model  first.")
        sys.exit(1)

    artifact = joblib.load(model_path)
    preprocessor = artifact["preprocessor"]
    prod_model = artifact["model"]

    X_val_enc = preprocessor.transform(X_val)

    # --- Production model metrics ---
    prod_preds = prod_model.predict(X_val_enc)
    prod_preds = np.clip(prod_preds, 0.01, 0.99)
    prod_mae = mean_absolute_error(y_val, prod_preds)
    prod_rmse = _rmse(y_val, prod_preds)

    # --- Baseline: retrain LinearRegression on the training split ---
    df_full = generate_synthetic_dataset(num_samples=num_samples, random_seed=random_seed)
    df_train, _ = time_based_split(df_full, train_fraction=0.80)
    X_train_enc = preprocessor.transform(df_train[FEATURE_COLS])
    y_train = df_train[TARGET_COL].values

    baseline = LinearRegression()
    baseline.fit(X_train_enc, y_train)
    bl_preds = np.clip(baseline.predict(X_val_enc), 0.01, 0.99)
    bl_mae = mean_absolute_error(y_val, bl_preds)
    bl_rmse = _rmse(y_val, bl_preds)

    # --- Per-category MAE ---
    df_val = df_val.copy()
    df_val["prod_pred"] = prod_preds
    df_val["bl_pred"] = bl_preds
    df_val["prod_error"] = (df_val["prod_pred"] - df_val[TARGET_COL]).abs()
    df_val["bl_error"] = (df_val["bl_pred"] - df_val[TARGET_COL]).abs()

    per_cat = (
        df_val.groupby("category")[["prod_error", "bl_error"]]
        .mean()
        .rename(columns={"prod_error": "prod_mae", "bl_error": "baseline_mae"})
        .round(5)
    )

    # --- Revenue error (simplified) ---
    # Oracle expected revenue = y_val * current_price (no discount)
    # Model revenue = prod_preds * current_price
    # Revenue delta = model_revenue - oracle_revenue (ideally near 0)
    oracle_revenue = y_val * df_val["current_price"].values
    model_revenue = prod_preds * df_val["current_price"].values
    mean_revenue_delta = float(np.mean(model_revenue - oracle_revenue))

    # --- Print report ---
    if verbose:
        print(f"\n{'─'*60}")
        print(f"{'Model':<35}  {'MAE':>8}  {'RMSE':>8}")
        print(f"{'─'*60}")
        print(f"{'Baseline (LinearRegression)':<35}  {bl_mae:>8.5f}  {bl_rmse:>8.5f}")
        print(f"{'Production (HistGradientBoosting)':<35}  {prod_mae:>8.5f}  {prod_rmse:>8.5f}")

        improvement_pct = (bl_mae - prod_mae) / bl_mae * 100 if bl_mae > 0 else 0
        print(f"\n  Production vs. Baseline MAE improvement: {improvement_pct:.1f}%")
        print(f"  Mean revenue delta (model vs. oracle): ₹{mean_revenue_delta:.4f}/unit")

        print(f"\n{'─'*60}")
        print("Per-category MAE (production model):")
        print(f"{'─'*60}")
        print(per_cat.to_string())

        print(f"\n{'─'*60}")
        print("Urgency score distribution on val set:")
        urgency_stats = df_val["urgency_score"].describe()
        print(urgency_stats.to_string())

        print(f"\n{'='*60}")

    return {
        "baseline": {"mae": round(bl_mae, 5), "rmse": round(bl_rmse, 5)},
        "production": {"mae": round(prod_mae, 5), "rmse": round(prod_rmse, 5)},
        "per_category": per_cat.to_dict(),
        "revenue_delta_mean": round(mean_revenue_delta, 4),
    }


if __name__ == "__main__":
    evaluate(verbose=True)
