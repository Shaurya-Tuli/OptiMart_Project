"""
trainer.py — OptiMart Model A (V2)
====================================
Thin wrapper around train_model.py that preserves the existing import interface
used by predictor.py and the FastAPI route.

The V1 RandomForestRegressor pipeline has been replaced by:
  - HistGradientBoostingRegressor (production model)
  - LinearRegression (sanity baseline, reported but not saved)

The saved artifact format changed from a bare sklearn Pipeline to a dict:
    {
        "preprocessor": ColumnTransformer,
        "model": HistGradientBoostingRegressor,
        "feature_cols": List[str],
        "target_col": str,
        "categories": List[str],
        "train_metrics": dict,
        "val_metrics": dict,
        "synthetic_data": True,
    }

For backward compatibility, MODEL_ARTIFACT_PATH still points to the V1 path,
but predictor.py now prefers MODEL_ARTIFACT_PATH_V2.
"""

import os
from pathlib import Path

from app.ml.train_model import MODEL_ARTIFACT_PATH_V2, train, CATEGORIES

# Keep old constant for any code that imports it
MODEL_ARTIFACT_PATH = os.environ.get(
    "ML_MODEL_PATH",
    str(Path(__file__).parent / "artifacts" / "pricing_model.joblib"),
)


def train_pricing_model(
    num_samples: int = 5000,
    artifact_path: str = MODEL_ARTIFACT_PATH_V2,
) -> str:
    """Train the V2 pricing model and return the artifact path.

    Args:
        num_samples: Number of synthetic training rows to generate.
        artifact_path: Where to save the Joblib artifact.

    Returns:
        Path to the saved artifact.
    """
    train(num_samples=num_samples, artifact_path=artifact_path, verbose=True)
    return artifact_path
