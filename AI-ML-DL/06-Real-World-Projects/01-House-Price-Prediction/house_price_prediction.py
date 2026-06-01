"""
House Price Prediction - Complete ML Pipeline
=============================================
Uses the California Housing dataset from sklearn.
Demonstrates: EDA, feature engineering, model comparison, evaluation.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.datasets import fetch_california_housing
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """Stores evaluation results for a model."""
    name: str
    mae: float
    rmse: float
    r2: float
    cv_score: float


def load_data() -> Tuple[pd.DataFrame, pd.Series]:
    """Load California Housing dataset."""
    logger.info("Loading California Housing dataset...")
    data = fetch_california_housing(as_frame=True)
    X = data.data
    y = data.target
    logger.info(f"Dataset shape: {X.shape}, Target range: [{y.min():.2f}, {y.max():.2f}]")
    return X, y


def exploratory_data_analysis(X: pd.DataFrame, y: pd.Series) -> None:
    """Perform and print EDA results."""
    print("\n" + "=" * 60)
    print("EXPLORATORY DATA ANALYSIS")
    print("=" * 60)

    print(f"\nDataset: {X.shape[0]} samples, {X.shape[1]} features")
    print(f"Target (Median House Value in $100k): mean={y.mean():.3f}, std={y.std():.3f}")

    print("\n--- Feature Statistics ---")
    print(X.describe().round(3).to_string())

    print("\n--- Top Correlations with Target ---")
    correlations = X.corrwith(y).abs().sort_values(ascending=False)
    for feat, corr in correlations.items():
        bar = "█" * int(corr * 30)
        print(f"  {feat:15s}: {corr:.3f} {bar}")

    print("\n--- Missing Values ---")
    missing = X.isnull().sum()
    if missing.sum() == 0:
        print("  No missing values found.")
    else:
        print(missing[missing > 0])


def feature_engineering(X: pd.DataFrame) -> pd.DataFrame:
    """Create new features from existing ones."""
    logger.info("Engineering features...")
    X = X.copy()

    # Interaction features
    X["rooms_per_household"] = X["AveRooms"] / X["AveOccup"].clip(lower=0.1)
    X["bedrooms_ratio"] = X["AveBedrms"] / X["AveRooms"].clip(lower=0.1)
    X["population_density"] = X["Population"] / X["AveOccup"].clip(lower=0.1)

    # Location-based features
    X["location_cluster"] = np.sqrt(X["Latitude"] ** 2 + X["Longitude"] ** 2)

    # Income bins (high-income areas tend to have higher prices)
    X["income_cat"] = pd.cut(X["MedInc"], bins=5, labels=False)

    logger.info(f"Features after engineering: {X.shape[1]}")
    return X


def train_and_evaluate_models(
    X_train: pd.DataFrame, X_test: pd.DataFrame,
    y_train: pd.Series, y_test: pd.Series
) -> List[ModelResult]:
    """Train multiple models and return evaluation results."""
    models = {
        "Linear Regression": LinearRegression(),
        "Ridge (α=1.0)": Ridge(alpha=1.0),
        "Lasso (α=0.01)": Lasso(alpha=0.01),
        "ElasticNet": ElasticNet(alpha=0.01, l1_ratio=0.5),
        "Random Forest": RandomForestRegressor(n_estimators=50, max_depth=12, random_state=42, n_jobs=1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42),
    }

    results: List[ModelResult] = []

    print("\n" + "=" * 60)
    print("MODEL TRAINING & EVALUATION")
    print("=" * 60)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    for name, model in models.items():
        logger.info(f"Training {name}...")

        # Use scaled data for linear models, raw for tree-based
        if "Forest" in name or "Boosting" in name:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            cv = cross_val_score(model, X_train, y_train, cv=3, scoring="r2", n_jobs=1)
        else:
            model.fit(X_train_scaled, y_train)
            preds = model.predict(X_test_scaled)
            cv = cross_val_score(model, X_train_scaled, y_train, cv=3, scoring="r2", n_jobs=1)

        result = ModelResult(
            name=name,
            mae=mean_absolute_error(y_test, preds),
            rmse=np.sqrt(mean_squared_error(y_test, preds)),
            r2=r2_score(y_test, preds),
            cv_score=cv.mean(),
        )
        results.append(result)

    return results


def print_results(results: List[ModelResult]) -> None:
    """Print comparison table of all models."""
    print("\n" + "=" * 60)
    print("MODEL COMPARISON")
    print("=" * 60)
    print(f"\n{'Model':<22} {'MAE':>8} {'RMSE':>8} {'R²':>8} {'CV R²':>8}")
    print("-" * 56)

    results_sorted = sorted(results, key=lambda r: r.r2, reverse=True)
    for r in results_sorted:
        print(f"{r.name:<22} {r.mae:>8.4f} {r.rmse:>8.4f} {r.r2:>8.4f} {r.cv_score:>8.4f}")

    best = results_sorted[0]
    print(f"\n🏆 Best Model: {best.name} (R² = {best.r2:.4f})")


def print_feature_importances(model: GradientBoostingRegressor, feature_names: List[str]) -> None:
    """Print top feature importances from tree-based model."""
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1][:10]

    print("\n--- Top 10 Feature Importances (Gradient Boosting) ---")
    for i, idx in enumerate(indices):
        bar = "█" * int(importances[idx] * 50)
        print(f"  {i+1:2d}. {feature_names[idx]:25s}: {importances[idx]:.4f} {bar}")


def main() -> None:
    """Run the complete house price prediction pipeline."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        HOUSE PRICE PREDICTION - ML PIPELINE             ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Step 1: Load data
    X, y = load_data()

    # Step 2: EDA
    exploratory_data_analysis(X, y)

    # Step 3: Feature engineering
    X = feature_engineering(X)

    # Step 4: Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    logger.info(f"Train: {X_train.shape[0]}, Test: {X_test.shape[0]}")

    # Step 5: Train and evaluate
    results = train_and_evaluate_models(X_train, X_test, y_train, y_test)

    # Step 6: Print comparison
    print_results(results)

    # Step 7: Feature importances from best tree model
    gb = GradientBoostingRegressor(n_estimators=100, max_depth=4, learning_rate=0.1, random_state=42)
    gb.fit(X_train, y_train)
    print_feature_importances(gb, list(X_train.columns))

    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
