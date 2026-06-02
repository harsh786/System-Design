"""
=============================================================================
TEMPLATE: Tabular Classification/Regression with Scikit-Learn
=============================================================================
A complete, runnable template for structured (tabular) data ML.
Uses the Iris dataset by default — runs immediately without downloads.

USAGE:
    python template_tabular.py

MODIFY:
    Search for "MODIFY THIS" to find all customization points.

REQUIREMENTS:
    pip install numpy pandas scikit-learn
    (These are likely already installed)
=============================================================================
"""

import numpy as np
import pandas as pd
from pathlib import Path
import warnings
import joblib

warnings.filterwarnings("ignore")

from sklearn.datasets import load_iris, load_wine, fetch_california_housing
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    classification_report, confusion_matrix, accuracy_score,
    mean_squared_error, r2_score
)

# Models
from sklearn.ensemble import (
    RandomForestClassifier, GradientBoostingClassifier,
    RandomForestRegressor, GradientBoostingRegressor
)
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.svm import SVC

# ============================================================
# MODIFY THIS: Configuration
# ============================================================
CONFIG = {
    # Task type: "classification" or "regression"
    "task": "classification",       # MODIFY THIS

    # Data
    "test_size": 0.2,
    "random_state": 42,

    # Model selection
    "cv_folds": 5,                  # Cross-validation folds
    "scoring_classification": "accuracy",    # or "f1_macro", "roc_auc"
    "scoring_regression": "r2",              # or "neg_mean_squared_error"

    # Output
    "save_path": "best_tabular_model.joblib",
}


# ============================================================
# MODIFY THIS: Data Loading
# ============================================================
def load_data():
    """
    Load your dataset.

    MODIFY THIS FUNCTION to load your own data.
    Options:
      - pd.read_csv("your_data.csv")
      - pd.read_sql("SELECT * FROM table", connection)
      - pd.read_excel("data.xlsx")

    Returns:
      - X: DataFrame of features
      - y: Series of target values
      - feature_names: list of feature names
    """

    # MODIFY THIS: Replace with your data loading
    # Example: df = pd.read_csv("your_data.csv")
    #          X = df.drop("target_column", axis=1)
    #          y = df["target_column"]

    # Default: Using built-in Iris dataset (works without downloads)
    data = load_iris()
    X = pd.DataFrame(data.data, columns=data.feature_names)
    y = pd.Series(data.target, name="target")
    feature_names = data.feature_names

    print(f"  Dataset shape: {X.shape}")
    print(f"  Features: {list(feature_names)}")
    print(f"  Target distribution:\n{y.value_counts().to_string()}")

    return X, y, feature_names


# ============================================================
# MODIFY THIS: Feature Engineering
# ============================================================
def create_preprocessing_pipeline(X):
    """
    Create preprocessing pipeline.

    MODIFY THIS to handle your specific feature types.
    """

    # MODIFY THIS: Identify your column types
    numeric_features = X.select_dtypes(include=[np.number]).columns.tolist()
    categorical_features = X.select_dtypes(include=["object", "category"]).columns.tolist()

    print(f"  Numeric features ({len(numeric_features)}): {numeric_features}")
    print(f"  Categorical features ({len(categorical_features)}): {categorical_features}")

    # Preprocessing for numeric columns
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),  # Handle missing values
        ("scaler", StandardScaler()),                    # Normalize
    ])

    # Preprocessing for categorical columns
    categorical_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    # Combine into a single preprocessor
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ],
        remainder="drop",  # Drop columns not specified
    )

    return preprocessor


# ============================================================
# Model Selection and Tuning
# ============================================================
def get_models(task):
    """Get candidate models based on task type."""

    if task == "classification":
        models = {
            "LogisticRegression": {
                "model": LogisticRegression(max_iter=1000, random_state=CONFIG["random_state"]),
                "params": {"model__C": [0.01, 0.1, 1.0, 10.0]},
            },
            "RandomForest": {
                "model": RandomForestClassifier(random_state=CONFIG["random_state"]),
                "params": {
                    "model__n_estimators": [100, 200],
                    "model__max_depth": [None, 10, 20],
                    "model__min_samples_leaf": [1, 5],
                },
            },
            "GradientBoosting": {
                "model": GradientBoostingClassifier(random_state=CONFIG["random_state"]),
                "params": {
                    "model__n_estimators": [100, 200],
                    "model__learning_rate": [0.05, 0.1],
                    "model__max_depth": [3, 5],
                },
            },
        }
        scoring = CONFIG["scoring_classification"]
    else:
        models = {
            "Ridge": {
                "model": Ridge(),
                "params": {"model__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
            },
            "RandomForest": {
                "model": RandomForestRegressor(random_state=CONFIG["random_state"]),
                "params": {
                    "model__n_estimators": [100, 200],
                    "model__max_depth": [None, 10, 20],
                },
            },
            "GradientBoosting": {
                "model": GradientBoostingRegressor(random_state=CONFIG["random_state"]),
                "params": {
                    "model__n_estimators": [100, 200],
                    "model__learning_rate": [0.05, 0.1],
                    "model__max_depth": [3, 5],
                },
            },
        }
        scoring = CONFIG["scoring_regression"]

    return models, scoring


# ============================================================
# Main Pipeline
# ============================================================
def main():
    print("=" * 60)
    print("TABULAR ML TEMPLATE")
    print("=" * 60)

    # Step 1: Load data
    print("\n[1/5] Loading data...")
    X, y, feature_names = load_data()

    # Step 2: Split data
    print("\n[2/5] Splitting data...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=CONFIG["test_size"],
        random_state=CONFIG["random_state"],
        stratify=y if CONFIG["task"] == "classification" else None,
    )
    print(f"  Train: {X_train.shape[0]} samples")
    print(f"  Test:  {X_test.shape[0]} samples")

    # Step 3: Create preprocessing
    print("\n[3/5] Creating preprocessing pipeline...")
    preprocessor = create_preprocessing_pipeline(X_train)

    # Step 4: Model selection with cross-validation
    print("\n[4/5] Model selection (this may take a moment)...")
    models, scoring = get_models(CONFIG["task"])

    best_score = -np.inf
    best_model_name = None
    best_pipeline = None
    results = {}

    for name, model_info in models.items():
        print(f"\n  Testing {name}...")

        # Create full pipeline: preprocessing + model
        pipeline = Pipeline(steps=[
            ("preprocessor", preprocessor),
            ("model", model_info["model"]),
        ])

        # Grid search with cross-validation
        grid_search = GridSearchCV(
            pipeline,
            param_grid=model_info["params"],
            cv=CONFIG["cv_folds"],
            scoring=scoring,
            n_jobs=-1,
            verbose=0,
        )
        grid_search.fit(X_train, y_train)

        score = grid_search.best_score_
        results[name] = {"score": score, "params": grid_search.best_params_}
        print(f"    Best CV {scoring}: {score:.4f}")
        print(f"    Best params: {grid_search.best_params_}")

        if score > best_score:
            best_score = score
            best_model_name = name
            best_pipeline = grid_search.best_estimator_

    # Step 5: Evaluate best model on test set
    print("\n[5/5] Evaluating best model on test set...")
    print(f"\n  Best model: {best_model_name} (CV {scoring}: {best_score:.4f})")

    y_pred = best_pipeline.predict(X_test)

    if CONFIG["task"] == "classification":
        print(f"\n  Test Accuracy: {accuracy_score(y_test, y_pred):.4f}")
        print(f"\n  Classification Report:")
        print(classification_report(y_test, y_pred))
        print(f"  Confusion Matrix:")
        print(confusion_matrix(y_test, y_pred))
    else:
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        print(f"  Test RMSE: {rmse:.4f}")
        print(f"  Test R²:   {r2:.4f}")

    # Save model
    joblib.dump(best_pipeline, CONFIG["save_path"])
    print(f"\n  Model saved to: {CONFIG['save_path']}")

    # Show how to load and use
    print("\n" + "=" * 60)
    print("TO USE THIS MODEL:")
    print("=" * 60)
    print(f"""
    import joblib
    import pandas as pd

    # Load
    model = joblib.load("{CONFIG['save_path']}")

    # Predict (pass a DataFrame with same columns as training data)
    new_data = pd.DataFrame({{...}})  # Your new data
    predictions = model.predict(new_data)
    """)

    # Summary
    print("\n" + "=" * 60)
    print("ALL RESULTS:")
    print("=" * 60)
    for name, res in sorted(results.items(), key=lambda x: x[1]["score"], reverse=True):
        marker = " ← BEST" if name == best_model_name else ""
        print(f"  {name:<25} {scoring}: {res['score']:.4f}{marker}")


if __name__ == "__main__":
    main()
