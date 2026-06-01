"""
End-to-End ML Pipeline
=======================
Complete training pipeline with data validation, model training,
evaluation, and model registry (file-based).
"""

import hashlib
import json
import logging
import os
import pickle
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.datasets import fetch_california_housing
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MODEL_REGISTRY = Path("./model_registry")
MODEL_REGISTRY.mkdir(exist_ok=True)


# =============================================================================
# Data Validation
# =============================================================================

@dataclass
class DataSchema:
    """Expected schema for input data."""
    expected_columns: list
    expected_dtypes: Dict[str, str]
    min_rows: int = 100
    max_null_ratio: float = 0.1


def validate_data(df: pd.DataFrame, schema: DataSchema) -> Tuple[bool, list]:
    """Validate data against schema. Returns (is_valid, errors)."""
    errors = []

    # Check columns
    missing_cols = set(schema.expected_columns) - set(df.columns)
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")

    # Check row count
    if len(df) < schema.min_rows:
        errors.append(f"Too few rows: {len(df)} < {schema.min_rows}")

    # Check nulls
    null_ratio = df.isnull().mean()
    high_nulls = null_ratio[null_ratio > schema.max_null_ratio]
    if len(high_nulls) > 0:
        errors.append(f"High null ratio columns: {dict(high_nulls)}")

    # Check for infinite values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    inf_counts = np.isinf(df[numeric_cols]).sum()
    if inf_counts.sum() > 0:
        errors.append(f"Infinite values found in: {inf_counts[inf_counts > 0].to_dict()}")

    is_valid = len(errors) == 0
    return is_valid, errors


# =============================================================================
# Model Registry
# =============================================================================

@dataclass
class ModelMetadata:
    """Metadata for a registered model."""
    model_id: str
    version: str
    created_at: str
    metrics: Dict[str, float]
    parameters: Dict[str, Any]
    data_hash: str


def register_model(model: Any, scaler: Any, metadata: ModelMetadata) -> str:
    """Save model and metadata to registry."""
    model_dir = MODEL_REGISTRY / metadata.model_id
    model_dir.mkdir(exist_ok=True)

    # Save model
    model_path = model_dir / f"model_v{metadata.version}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "scaler": scaler}, f)

    # Save metadata
    meta_path = model_dir / f"metadata_v{metadata.version}.json"
    with open(meta_path, "w") as f:
        json.dump(asdict(metadata), f, indent=2)

    logger.info(f"Model registered: {metadata.model_id} v{metadata.version}")
    return str(model_path)


def load_latest_model(model_id: str) -> Tuple[Any, Any, ModelMetadata]:
    """Load the latest model version from registry."""
    model_dir = MODEL_REGISTRY / model_id
    if not model_dir.exists():
        raise FileNotFoundError(f"Model {model_id} not found in registry")

    # Find latest version
    meta_files = sorted(model_dir.glob("metadata_v*.json"))
    if not meta_files:
        raise FileNotFoundError(f"No versions found for {model_id}")

    latest_meta = meta_files[-1]
    with open(latest_meta) as f:
        metadata = ModelMetadata(**json.load(f))

    model_path = model_dir / f"model_v{metadata.version}.pkl"
    with open(model_path, "rb") as f:
        artifacts = pickle.load(f)

    return artifacts["model"], artifacts["scaler"], metadata


# =============================================================================
# Training Pipeline
# =============================================================================

def run_pipeline() -> None:
    """Execute the full training pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         END-TO-END ML TRAINING PIPELINE                 ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Step 1: Load data
    logger.info("Step 1: Loading data...")
    data = fetch_california_housing(as_frame=True)
    df = data.data.copy()
    df["target"] = data.target

    # Step 2: Validate data
    logger.info("Step 2: Validating data...")
    schema = DataSchema(
        expected_columns=list(data.feature_names) + ["target"],
        expected_dtypes={col: "float64" for col in data.feature_names},
        min_rows=1000,
    )
    is_valid, errors = validate_data(df, schema)
    print(f"\n  Data Validation: {'PASSED' if is_valid else 'FAILED'}")
    if errors:
        for err in errors:
            print(f"    - {err}")
        return

    # Data hash for tracking
    data_hash = hashlib.md5(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest()[:12]
    print(f"  Data hash: {data_hash}")
    print(f"  Shape: {df.shape}")

    # Step 3: Prepare features
    logger.info("Step 3: Feature preparation...")
    X = df.drop("target", axis=1)
    y = df["target"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Step 4: Train model
    logger.info("Step 4: Training model...")
    params = {"n_estimators": 100, "max_depth": 4, "learning_rate": 0.1, "random_state": 42}
    model = GradientBoostingRegressor(**params)

    start = time.time()
    model.fit(X_train_scaled, y_train)
    train_time = time.time() - start
    print(f"\n  Training time: {train_time:.2f}s")

    # Step 5: Evaluate
    logger.info("Step 5: Evaluating model...")
    preds = model.predict(X_test_scaled)
    metrics = {
        "mae": mean_absolute_error(y_test, preds),
        "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
        "r2": r2_score(y_test, preds),
    }

    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=3, scoring="r2", n_jobs=1)
    metrics["cv_r2_mean"] = float(cv_scores.mean())
    metrics["cv_r2_std"] = float(cv_scores.std())

    print(f"\n  Evaluation Metrics:")
    print(f"    MAE:     {metrics['mae']:.4f}")
    print(f"    RMSE:    {metrics['rmse']:.4f}")
    print(f"    R²:      {metrics['r2']:.4f}")
    print(f"    CV R²:   {metrics['cv_r2_mean']:.4f} ± {metrics['cv_r2_std']:.4f}")

    # Step 6: Register model
    logger.info("Step 6: Registering model...")
    metadata = ModelMetadata(
        model_id="house_price_model",
        version="1.0",
        created_at=datetime.now().isoformat(),
        metrics=metrics,
        parameters=params,
        data_hash=data_hash,
    )
    model_path = register_model(model, scaler, metadata)
    print(f"\n  Model saved to: {model_path}")

    # Step 7: Verify loading
    loaded_model, loaded_scaler, loaded_meta = load_latest_model("house_price_model")
    verify_preds = loaded_model.predict(loaded_scaler.transform(X_test[:5]))
    print(f"\n  Verification (5 predictions): {verify_preds.round(3)}")

    print("\n✅ Pipeline complete! Model ready for serving.")


if __name__ == "__main__":
    run_pipeline()
