# Training Data Preparation for Supervised Learning

## Overview

Before any algorithm sees your data, proper preparation determines 80% of model success. This guide covers the complete pipeline from raw data to model-ready features.

```
Raw Data → Split → Clean → Encode → Scale → Balance → Model
```

## 1. Data Splitting (Train / Validation / Test)

### Basic Split

```python
from sklearn.model_selection import train_test_split

# 60/20/20 split
X_temp, X_test, y_temp, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=0.25, random_state=42)
```

### Stratified Split (for imbalanced classification)

```python
# Preserves class proportions in each split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)
```

### Temporal Split (time series — NEVER shuffle)

```python
# Sort by time, use past to predict future
split_idx = int(len(df) * 0.8)
train = df.iloc[:split_idx]
test = df.iloc[split_idx:]

# Or use TimeSeriesSplit for cross-validation
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
```

### Grouped Split (prevent data leakage)

```python
# Keep all samples from same group (e.g., patient, user) in same split
from sklearn.model_selection import GroupShuffleSplit
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(X, y, groups=group_ids))
```

## 2. Feature Scaling

### When to Scale

| Need Scaling | Don't Need Scaling |
|---|---|
| Linear/Logistic Regression | Decision Trees |
| SVM | Random Forest |
| KNN | XGBoost/LightGBM |
| Neural Networks | Naive Bayes |
| PCA | |

### Scaler Comparison

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

# StandardScaler: z = (x - mean) / std → mean=0, std=1
# Best for: most algorithms, Gaussian-like distributions
StandardScaler()

# MinMaxScaler: x' = (x - min) / (max - min) → [0, 1]
# Best for: neural networks, bounded features
MinMaxScaler()

# RobustScaler: z = (x - median) / IQR
# Best for: data with outliers
RobustScaler()
```

**Critical rule:** Fit scaler on TRAINING data only, transform both train and test.

```python
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)   # fit + transform
X_test_scaled = scaler.transform(X_test)          # only transform!
```

## 3. Encoding Categorical Variables

### One-Hot Encoding (nominal categories, low cardinality)

```python
from sklearn.preprocessing import OneHotEncoder

# color: [red, blue, green] → [1,0,0], [0,1,0], [0,0,1]
ohe = OneHotEncoder(handle_unknown='ignore', sparse_output=False)

# Use drop='first' to avoid multicollinearity in linear models
ohe = OneHotEncoder(drop='first', handle_unknown='ignore')
```

### Label/Ordinal Encoding (ordinal categories)

```python
from sklearn.preprocessing import OrdinalEncoder

# size: [S, M, L, XL] → [0, 1, 2, 3]  (order matters!)
oe = OrdinalEncoder(categories=[['S', 'M', 'L', 'XL']])
```

### Target Encoding (high cardinality, e.g., zip codes)

```python
# Replace category with mean of target for that category
# MUST use only training data to compute means (prevent leakage!)
from sklearn.preprocessing import TargetEncoder  # sklearn 1.3+

te = TargetEncoder(smooth='auto')
X_train_encoded = te.fit_transform(X_train[['zip_code']], y_train)
X_test_encoded = te.transform(X_test[['zip_code']])
```

### When to Use Which

| Method | When | Watch Out |
|--------|------|-----------|
| One-Hot | < 10 categories, nominal | Dimensionality explosion |
| Ordinal | Natural order exists | Implies false distances if not ordinal |
| Target | High cardinality (100+) | Data leakage if done wrong |
| Binary | 2 categories | Simplest case |

## 4. Handling Missing Values

### Strategy by Mechanism

```
MCAR (Missing Completely At Random): Safe to drop or impute with mean
MAR (Missing At Random): Impute using related features
MNAR (Missing Not At Random): Missingness is informative → add indicator
```

### Imputation Code

```python
from sklearn.impute import SimpleImputer, KNNImputer
import numpy as np

# Simple strategies
mean_imp = SimpleImputer(strategy='mean')       # continuous
median_imp = SimpleImputer(strategy='median')   # continuous + outliers
mode_imp = SimpleImputer(strategy='most_frequent')  # categorical

# KNN Imputer (uses similar samples)
knn_imp = KNNImputer(n_neighbors=5)

# Add missingness indicator (when missingness is informative)
from sklearn.impute import SimpleImputer
imp = SimpleImputer(strategy='mean', add_indicator=True)
```

### Best Practices

1. Explore missingness patterns first (`df.isnull().sum()`, `missingno` library)
2. If < 5% missing randomly → simple imputation or drop rows
3. If feature > 50% missing → consider dropping the feature
4. Always add `is_missing` indicator for features where missingness has meaning
5. For tree-based models: can often handle missing natively (XGBoost, LightGBM)

## 5. Handling Class Imbalance

### Techniques

```python
# 1. Class weights (easiest, no data modification)
from sklearn.linear_model import LogisticRegression
clf = LogisticRegression(class_weight='balanced')

# 2. SMOTE (synthetic minority oversampling)
from imblearn.over_sampling import SMOTE
smote = SMOTE(random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train, y_train)

# 3. Random undersampling
from imblearn.under_sampling import RandomUnderSampler
rus = RandomUnderSampler(random_state=42)
X_resampled, y_resampled = rus.fit_resample(X_train, y_train)

# 4. Threshold tuning (after training)
from sklearn.metrics import precision_recall_curve
precisions, recalls, thresholds = precision_recall_curve(y_test, probs)
# Pick threshold that optimizes your business metric
```

### When to Use Which

| Technique | When |
|-----------|------|
| class_weight='balanced' | Always try first (no data change) |
| SMOTE | Minority class is small but not tiny (>100 samples) |
| Undersampling | Majority class is very large, can afford to lose data |
| Threshold tuning | Need to control precision/recall trade-off |
| Ensemble (BalancedRF) | Want robust solution with tree-based models |

## 6. Complete Sklearn Pipeline

```python
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer
from sklearn.model_selection import cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestClassifier

# Define column types
numeric_features = ['age', 'income', 'credit_score']
categorical_features = ['gender', 'city']
ordinal_features = ['education']  # HS < BS < MS < PhD

# Numeric pipeline: impute → scale
numeric_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

# Categorical pipeline: impute → one-hot
categorical_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore'))
])

# Ordinal pipeline: impute → ordinal encode
ordinal_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('ordinal', OrdinalEncoder(categories=[['HS', 'BS', 'MS', 'PhD']]))
])

# Combine all
preprocessor = ColumnTransformer([
    ('num', numeric_transformer, numeric_features),
    ('cat', categorical_transformer, categorical_features),
    ('ord', ordinal_transformer, ordinal_features)
])

# Full pipeline
full_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
])

# Train and evaluate
scores = cross_val_score(full_pipeline, X_train, y_train, cv=5, scoring='f1')
print(f"F1: {scores.mean():.3f} ± {scores.std():.3f}")

# Hyperparameter tuning
param_grid = {
    'preprocessor__num__imputer__strategy': ['mean', 'median'],
    'classifier__n_estimators': [100, 200],
    'classifier__max_depth': [5, 10, None]
}
grid = GridSearchCV(full_pipeline, param_grid, cv=5, scoring='f1')
grid.fit(X_train, y_train)
```

## Common Data Leakage Traps

1. **Scaling before splitting** → test statistics leak into training
2. **Target encoding with full data** → test target values leak
3. **Imputing with full data statistics** → test info leaks
4. **Time series shuffled** → future predicts past
5. **Duplicate rows in train and test** → inflated metrics

**Rule:** Everything derived from data must be fit ONLY on training set.

## Checklist Before Training

- [ ] Train/val/test split done correctly (stratified? temporal? grouped?)
- [ ] No data leakage (all transforms fit on train only)
- [ ] Missing values handled (imputation + indicators if needed)
- [ ] Categoricals encoded appropriately
- [ ] Features scaled (if algorithm requires it)
- [ ] Class imbalance addressed
- [ ] Pipeline encapsulates all transforms (for deployment reproducibility)
- [ ] Cross-validation strategy matches problem (stratified, grouped, temporal)
