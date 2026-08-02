"""
train_model.py — OptiMart Model A
==================================
Trains the pricing ML model on synthetic (or real) data.

Pipeline:
  1. Generate (or load) dataset via generate_synthetic_dataset()
  2. Apply time-based train/test split (80% earlier, 20% most recent)
     — NOT random split, to avoid future-data leakage.
  3. Train a baseline LinearRegression sanity check.
  4. Train a HistGradientBoostingRegressor (production model).
  5. Report train/validation MAE and RMSE for both models.
  6. Save the production model artifact via Joblib.

Usage:
    # From project root:
    python -m app.ml.train_model
    # or:
    python app/ml/train_model.py

Output:
    app/ml/artifacts/pricing_model_v2.joblib

!! Training data is SYNTHETIC — see synthetic_data.py !!
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler

# Resolve imports whether run as module or script
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent.parent))

from app.ml.synthetic_data import generate_synthetic_dataset, CATEGORIES

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACT_DIR = _HERE / "artifacts"
MODEL_ARTIFACT_PATH_V2 = str(ARTIFACT_DIR / "pricing_model_v2.joblib")

# ---------------------------------------------------------------------------
# Feature columns (the model sees these — NOT raw days_to_expiry)
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "urgency_score",          # PRIMARY time signal — normalized per category
    "category",               # categorical
    "current_price",
    "cost_price",
    "qty_on_hand",
    "avg_daily_velocity_7d",
    "avg_daily_velocity_28d",
    "temperature_today",
    "precip_probability",
    "is_weekend",
    "is_holiday",
    "hour_of_day",
    "store_foot_traffic_index",
    "past_discount_depth",
    "past_sellthrough_rate",
    "local_demand_score",
    "b2b_flag",
    "cat_x_temp",             # category × temperature interaction
    "cat_x_precip",           # category × precip interaction
]

TARGET_COL = "sell_probability"

# Categorical features for one-hot encoding
CAT_FEATURES = ["category"]

# Numerical features for StandardScaler
NUM_FEATURES = [f for f in FEATURE_COLS if f not in CAT_FEATURES]


def build_preprocessor() -> ColumnTransformer:
    """Build the sklearn ColumnTransformer for feature preprocessing."""
    return ColumnTransformer(
        transformers=[
            (
                "num",
                StandardScaler(),
                NUM_FEATURES,
            ),
            (
                "cat",
                OneHotEncoder(
                    categories=[CATEGORIES],
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
                CAT_FEATURES,
            ),
        ],
        remainder="drop",
    )


def time_based_split(
    df: pd.DataFrame,
    train_fraction: float = 0.80,
    date_col: str = "date",
):
    """Split DataFrame on time, not randomly.

    All rows in the earliest train_fraction of dates go to train.
    The remaining most-recent rows go to validation.

    Args:
        df: DataFrame sorted by date_col (ascending).
        train_fraction: Fraction of data to use for training.
        date_col: Name of the datetime column.

    Returns:
        Tuple (df_train, df_val)
    """
    df = df.sort_values(date_col).reset_index(drop=True)
    cutoff_idx = int(len(df) * train_fraction)
    df_train = df.iloc[:cutoff_idx].copy()
    df_val = df.iloc[cutoff_idx:].copy()
    return df_train, df_val


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mae = mean_absolute_error(y_true, y_pred)
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    return {"mae": round(mae, 5), "rmse": round(rmse, 5)}


def train(
    num_samples: int = 5000,
    artifact_path: str = MODEL_ARTIFACT_PATH_V2,
    random_seed: int = 42,
    verbose: bool = True,
) -> dict:
    """Train baseline + production models, save artifact, return metrics dict.

    Args:
        num_samples: Number of synthetic rows to generate.
        artifact_path: Where to save the Joblib model artifact.
        random_seed: Random seed for dataset generation.
        verbose: Print progress to stdout.

    Returns:
        dict with keys: baseline_train, baseline_val, prod_train, prod_val,
        each containing {"mae": float, "rmse": float}.
    """
    import math  # local import for _metrics closure

    if verbose:
        print(f"\n{'='*60}")
        print("OptiMart Model A — Training Pipeline")
        print(f"{'='*60}")
        print("!! Training data is SYNTHETIC — not real retailer data !!")
        print(f"Generating {num_samples:,} synthetic samples...")

    df = generate_synthetic_dataset(num_samples=num_samples, random_seed=random_seed)

    if verbose:
        print(f"Dataset shape: {df.shape}")
        print(f"Date range: {df['date'].min().date()} → {df['date'].max().date()}")
        print(f"Categories: {df['category'].value_counts().to_dict()}")

    # --- Time-based split ---
    df_train, df_val = time_based_split(df, train_fraction=0.80)
    if verbose:
        print(f"\nTime-based split (80/20 on date):")
        print(f"  Train: {len(df_train):,} rows  "
              f"(up to {df_train['date'].max().date()})")
        print(f"  Val:   {len(df_val):,} rows  "
              f"(from {df_val['date'].min().date()})")

    X_train = df_train[FEATURE_COLS]
    y_train = df_train[TARGET_COL].values
    X_val = df_val[FEATURE_COLS]
    y_val = df_val[TARGET_COL].values

    preprocessor = build_preprocessor()
    X_train_enc = preprocessor.fit_transform(X_train)
    X_val_enc = preprocessor.transform(X_val)

    # --- Baseline: LinearRegression ---
    if verbose:
        print("\n--- Baseline: LinearRegression ---")
    baseline = LinearRegression()
    baseline.fit(X_train_enc, y_train)
    bl_train = _metrics(y_train, baseline.predict(X_train_enc))
    bl_val = _metrics(y_val, baseline.predict(X_val_enc))
    if verbose:
        print(f"  Train — MAE: {bl_train['mae']:.5f}  RMSE: {bl_train['rmse']:.5f}")
        print(f"  Val   — MAE: {bl_val['mae']:.5f}  RMSE: {bl_val['rmse']:.5f}")

    # --- Production: HistGradientBoostingRegressor ---
    if verbose:
        print("\n--- Production: HistGradientBoostingRegressor ---")

    # HistGradientBoosting handles missing values natively and trains fast.
    # max_iter=300 is sufficient for this feature set; increasing to 500+
    # gives diminishing returns on synthetic data.
    prod_model = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_depth=6,
        min_samples_leaf=20,
        l2_regularization=0.1,
        random_state=random_seed,
        loss="squared_error",
    )
    prod_model.fit(X_train_enc, y_train)
    prod_train = _metrics(y_train, prod_model.predict(X_train_enc))
    prod_val = _metrics(y_val, prod_model.predict(X_val_enc))
    if verbose:
        print(f"  Train — MAE: {prod_train['mae']:.5f}  RMSE: {prod_train['rmse']:.5f}")
        print(f"  Val   — MAE: {prod_val['mae']:.5f}  RMSE: {prod_val['rmse']:.5f}")

    # --- Save artifact ---
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "preprocessor": preprocessor,
        "model": prod_model,
        "feature_cols": FEATURE_COLS,
        "target_col": TARGET_COL,
        "categories": CATEGORIES,
        "train_metrics": prod_train,
        "val_metrics": prod_val,
        "synthetic_data": True,
    }
    joblib.dump(artifact, artifact_path)
    if verbose:
        print(f"\nArtifact saved to: {artifact_path}")
        print(f"\n{'='*60}\nTraining complete.\n{'='*60}")

    return {
        "baseline_train": bl_train,
        "baseline_val": bl_val,
        "prod_train": prod_train,
        "prod_val": prod_val,
    }


# Needed for _metrics inside train()
import math


if __name__ == "__main__":
    metrics = train(num_samples=5000, verbose=True)
    print("\nFinal metrics summary:")
    print(json.dumps(metrics, indent=2))
