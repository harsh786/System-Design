"""
Complete Production-Quality Scikit-Learn Pipeline
=================================================
Demonstrates end-to-end ML workflow with:
- Custom transformers
- ColumnTransformer for mixed types
- Pipeline composition
- Cross-validation with custom scoring
- Hyperparameter tuning (RandomizedSearchCV)
- Model evaluation and serialization
- Inference with input validation

Requirements: sklearn, numpy, pandas (all standard)
"""

import time
import warnings
import numpy as np
import pandas as pd
import joblib
from typing import Dict, Any

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.datasets import fetch_openml
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, classification_report, roc_auc_score, make_scorer
)
from sklearn.model_selection import (
    RandomizedSearchCV, StratifiedKFold, cross_val_score, train_test_split
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.utils.validation import check_is_fitted, check_array
from scipy.stats import randint, uniform

warnings.filterwarnings('ignore')

# ============================================================
# 1. CUSTOM TRANSFORMER
# ============================================================

class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Custom transformer that creates interaction and ratio features."""
    
    def __init__(self, create_ratios=True, create_interactions=True):
        self.create_ratios = create_ratios
        self.create_interactions = create_interactions
    
    def fit(self, X, y=None):
        X = check_array(X)
        self.n_features_in_ = X.shape[1]
        self.means_ = np.mean(X, axis=0)
        self.stds_ = np.std(X, axis=0) + 1e-8
        return self
    
    def transform(self, X):
        check_is_fitted(self, ['means_', 'stds_'])
        X = check_array(X, copy=True)
        new_features = [X]
        
        if self.create_ratios and X.shape[1] >= 2:
            # Ratio of first two features
            ratios = X[:, 0:1] / (X[:, 1:2] + 1e-8)
            new_features.append(ratios)
        
        if self.create_interactions and X.shape[1] >= 2:
            # Pairwise products of first 3 features
            n = min(3, X.shape[1])
            for i in range(n):
                for j in range(i + 1, n):
                    new_features.append((X[:, i] * X[:, j]).reshape(-1, 1))
        
        return np.hstack(new_features)
    
    def get_feature_names_out(self, input_features=None):
        check_is_fitted(self)
        n = self.n_features_in_
        names = [f"feat_{i}" for i in range(n)]
        if self.create_ratios and n >= 2:
            names.append("ratio_0_1")
        if self.create_interactions and n >= 2:
            for i in range(min(3, n)):
                for j in range(i + 1, min(3, n)):
                    names.append(f"interact_{i}_{j}")
        return names


# ============================================================
# 2. DATA LOADING AND PREPARATION
# ============================================================

def load_and_prepare_data():
    """Load Titanic dataset with mixed feature types."""
    print("=" * 60)
    print("LOADING DATA")
    print("=" * 60)
    
    # Use Titanic for mixed types (numeric + categorical)
    titanic = fetch_openml('titanic', version=1, as_frame=True, parser='auto')
    df = titanic.frame
    
    # Select useful features
    features = ['pclass', 'age', 'sibsp', 'parch', 'fare', 'sex', 'embarked']
    target = 'survived'
    
    df = df[features + [target]].copy()
    df[target] = df[target].astype(int)
    
    X = df[features]
    y = df[target]
    
    print(f"  Dataset shape: {X.shape}")
    print(f"  Target distribution: {y.value_counts().to_dict()}")
    print(f"  Missing values:\n{X.isnull().sum().to_string()}\n")
    
    return X, y, features


# ============================================================
# 3. BUILD PIPELINE
# ============================================================

def build_pipeline():
    """Construct full preprocessing + model pipeline."""
    numeric_features = ['age', 'sibsp', 'parch', 'fare']
    categorical_features = ['sex', 'embarked', 'pclass']
    
    numeric_transformer = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('engineer', FeatureEngineer(create_ratios=True, create_interactions=True)),
        ('scaler', StandardScaler()),
    ])
    
    categorical_transformer = Pipeline([
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
    ])
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features),
        ],
        remainder='drop'
    )
    
    pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', GradientBoostingClassifier(random_state=42)),
    ])
    
    return pipeline


# ============================================================
# 4. CROSS-VALIDATION
# ============================================================

def cross_validate_pipeline(pipeline, X, y):
    """Run cross-validation with multiple metrics."""
    print("=" * 60)
    print("CROSS-VALIDATION")
    print("=" * 60)
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    t0 = time.time()
    scores_acc = cross_val_score(pipeline, X, y, cv=cv, scoring='accuracy', n_jobs=-1)
    scores_auc = cross_val_score(pipeline, X, y, cv=cv, scoring='roc_auc', n_jobs=-1)
    elapsed = time.time() - t0
    
    print(f"  Accuracy: {scores_acc.mean():.4f} (+/- {scores_acc.std():.4f})")
    print(f"  ROC-AUC:  {scores_auc.mean():.4f} (+/- {scores_auc.std():.4f})")
    print(f"  Time: {elapsed:.2f}s\n")
    
    return scores_acc, scores_auc


# ============================================================
# 5. HYPERPARAMETER TUNING
# ============================================================

def tune_hyperparameters(pipeline, X_train, y_train):
    """Randomized search over pipeline hyperparameters."""
    print("=" * 60)
    print("HYPERPARAMETER TUNING (RandomizedSearchCV)")
    print("=" * 60)
    
    param_distributions = {
        'classifier__n_estimators': randint(50, 300),
        'classifier__max_depth': randint(2, 10),
        'classifier__learning_rate': uniform(0.01, 0.29),
        'classifier__subsample': uniform(0.6, 0.4),
        'classifier__min_samples_leaf': randint(1, 20),
        'preprocessor__num__engineer__create_interactions': [True, False],
    }
    
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    search = RandomizedSearchCV(
        pipeline,
        param_distributions,
        n_iter=40,
        cv=cv,
        scoring='roc_auc',
        n_jobs=-1,
        random_state=42,
        verbose=0,
        refit=True,
    )
    
    t0 = time.time()
    search.fit(X_train, y_train)
    elapsed = time.time() - t0
    
    print(f"  Best ROC-AUC (CV): {search.best_score_:.4f}")
    print(f"  Best params:")
    for k, v in search.best_params_.items():
        print(f"    {k}: {v}")
    print(f"  Search time: {elapsed:.2f}s")
    print(f"  Total fits: {search.n_splits_ * 40}\n")
    
    return search.best_estimator_


# ============================================================
# 6. FINAL EVALUATION
# ============================================================

def evaluate_model(model, X_test, y_test):
    """Comprehensive evaluation on held-out test set."""
    print("=" * 60)
    print("FINAL EVALUATION (Test Set)")
    print("=" * 60)
    
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    acc = accuracy_score(y_test, y_pred)
    auc = roc_auc_score(y_test, y_prob)
    
    print(f"  Accuracy: {acc:.4f}")
    print(f"  ROC-AUC:  {auc:.4f}")
    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, indent=4))
    
    return {'accuracy': acc, 'roc_auc': auc}


# ============================================================
# 7. SERIALIZATION
# ============================================================

def save_model(model, filepath='model_production.joblib'):
    """Save model with compression."""
    print("=" * 60)
    print("MODEL SERIALIZATION")
    print("=" * 60)
    
    joblib.dump(model, filepath, compress=3)
    import os
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"  Saved to: {filepath}")
    print(f"  File size: {size_mb:.2f} MB\n")
    return filepath


# ============================================================
# 8. INFERENCE WITH VALIDATION
# ============================================================

def predict_single(model, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Production inference function with input validation.
    
    Args:
        model: Fitted sklearn pipeline
        input_data: Dict with keys matching training features
    
    Returns:
        Dict with prediction, probability, and metadata
    """
    required_fields = ['pclass', 'age', 'sibsp', 'parch', 'fare', 'sex', 'embarked']
    
    # Validate required fields
    missing = [f for f in required_fields if f not in input_data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")
    
    # Validate types and ranges
    if input_data.get('age') is not None and not (0 <= input_data['age'] <= 120):
        raise ValueError(f"Invalid age: {input_data['age']}")
    if input_data['fare'] < 0:
        raise ValueError(f"Invalid fare: {input_data['fare']}")
    if input_data['sex'] not in ('male', 'female'):
        raise ValueError(f"Invalid sex: {input_data['sex']}")
    
    # Create DataFrame (pipeline expects DataFrame input)
    df = pd.DataFrame([input_data])[required_fields]
    
    prediction = model.predict(df)[0]
    probability = model.predict_proba(df)[0]
    
    return {
        'prediction': int(prediction),
        'probability_survived': float(probability[1]),
        'probability_not_survived': float(probability[0]),
        'confidence': float(max(probability)),
    }


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == '__main__':
    total_start = time.time()
    
    # Load data
    X, y, features = load_and_prepare_data()
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train: {X_train.shape[0]}, Test: {X_test.shape[0]}\n")
    
    # Build pipeline
    pipeline = build_pipeline()
    
    # Cross-validate baseline
    cross_validate_pipeline(pipeline, X_train, y_train)
    
    # Tune hyperparameters
    best_model = tune_hyperparameters(pipeline, X_train, y_train)
    
    # Evaluate
    metrics = evaluate_model(best_model, X_test, y_test)
    
    # Save
    save_model(best_model)
    
    # Demo inference
    print("=" * 60)
    print("INFERENCE DEMO")
    print("=" * 60)
    
    sample_passenger = {
        'pclass': 1, 'age': 30.0, 'sibsp': 0, 'parch': 0,
        'fare': 50.0, 'sex': 'female', 'embarked': 'S'
    }
    
    result = predict_single(best_model, sample_passenger)
    print(f"  Input: {sample_passenger}")
    print(f"  Prediction: {'Survived' if result['prediction'] == 1 else 'Not Survived'}")
    print(f"  Confidence: {result['confidence']:.2%}")
    
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print(f"TOTAL PIPELINE TIME: {total_elapsed:.2f}s")
    print(f"{'=' * 60}")
