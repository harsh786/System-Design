# Scikit-Learn Mastery

## API Design Philosophy

Scikit-Learn's power comes from its consistent API built on three core interfaces:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scikit-Learn API Design                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  Estimator   │    │ Transformer  │    │  Predictor   │     │
│  │  .fit()      │    │ .transform() │    │  .predict()  │     │
│  │              │    │ .fit_transform│    │  .score()    │     │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘     │
│         │                   │                   │              │
│         └───────────────────┼───────────────────┘              │
│                             │                                  │
│                    ┌────────▼────────┐                         │
│                    │    Pipeline     │                         │
│                    │ step1 → step2 → │                         │
│                    │ step3 → predict │                         │
│                    └─────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

### The Three Interfaces

```python
# 1. Estimator: anything that learns from data
# Every estimator has .fit(X, y=None)
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)  # Learn from data

# 2. Transformer: transforms data
# Has .transform(X) and .fit_transform(X, y=None)
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)  # fit + transform in one step
X_test_scaled = scaler.transform(X_test)  # only transform (no fit!)

# 3. Predictor: makes predictions
# Has .predict(X) and .score(X, y)
predictions = model.predict(X_test)
accuracy = model.score(X_test, y_test)
```

### Key Design Principles

1. **Consistency**: All estimators share the same interface
2. **Inspection**: All parameters are public attributes
3. **Non-proliferation of classes**: Use numpy arrays and scipy sparse matrices
4. **Composition**: Build complex pipelines from simple blocks
5. **Sensible defaults**: Works out-of-the-box with reasonable parameters

## Complete Pipeline Workflow

```python
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib

# ============================================================
# COMPLETE END-TO-END WORKFLOW
# ============================================================

# 1. Load and explore data
df = pd.read_csv('data.csv')
print(df.info())
print(df.describe())
print(df.isnull().sum())

# 2. Define feature types
numeric_features = ['age', 'income', 'credit_score']
categorical_features = ['education', 'employment', 'region']
target = 'approved'

X = df[numeric_features + categorical_features]
y = df[target]

# 3. Train/test split (ALWAYS before preprocessing)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# 4. Build preprocessing pipeline
numeric_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline(steps=[
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
])

preprocessor = ColumnTransformer(
    transformers=[
        ('num', numeric_transformer, numeric_features),
        ('cat', categorical_transformer, categorical_features)
    ],
    remainder='drop'  # drop columns not specified
)

# 5. Full pipeline with model
pipeline = Pipeline(steps=[
    ('preprocessor', preprocessor),
    ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
])

# 6. Cross-validation
cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring='accuracy')
print(f"CV Accuracy: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

# 7. Hyperparameter tuning
param_grid = {
    'classifier__n_estimators': [100, 200, 300],
    'classifier__max_depth': [5, 10, 20, None],
    'classifier__min_samples_split': [2, 5, 10],
    'preprocessor__num__imputer__strategy': ['mean', 'median']
}

grid_search = GridSearchCV(
    pipeline, param_grid, cv=5, scoring='accuracy', n_jobs=-1, verbose=1
)
grid_search.fit(X_train, y_train)

print(f"Best params: {grid_search.best_params_}")
print(f"Best CV score: {grid_search.best_score_:.4f}")

# 8. Evaluate on test set
best_model = grid_search.best_estimator_
y_pred = best_model.predict(X_test)
print(classification_report(y_test, y_pred))
print(confusion_matrix(y_test, y_pred))

# 9. Save model
joblib.dump(best_model, 'model_pipeline.joblib')

# 10. Load and use in production
loaded_model = joblib.load('model_pipeline.joblib')
new_prediction = loaded_model.predict(new_data)
```

## Preprocessing Deep Dive

### Numeric Preprocessing

```python
from sklearn.preprocessing import (
    StandardScaler,      # z = (x - mean) / std
    MinMaxScaler,        # x_scaled = (x - min) / (max - min)
    RobustScaler,        # Uses median and IQR (robust to outliers)
    MaxAbsScaler,        # Scales by max absolute value
    Normalizer,          # Normalize samples to unit norm
    PowerTransformer,    # Gaussianize features (Box-Cox or Yeo-Johnson)
    QuantileTransformer, # Transform to uniform or normal distribution
)

# StandardScaler: Use when algorithm assumes normal distribution (SVM, LR, KNN)
scaler = StandardScaler()
# Stores: mean_, scale_, var_, n_samples_seen_

# MinMaxScaler: Use when you need bounded values [0, 1]
scaler = MinMaxScaler(feature_range=(0, 1))

# RobustScaler: Use when data has outliers
scaler = RobustScaler(quantile_range=(25.0, 75.0))

# PowerTransformer: Make data more Gaussian-like
pt = PowerTransformer(method='yeo-johnson')  # handles negative values
pt = PowerTransformer(method='box-cox')      # positive values only
```

### Categorical Preprocessing

```python
from sklearn.preprocessing import (
    OneHotEncoder,       # Creates binary columns
    OrdinalEncoder,      # Maps to integers (preserves order)
    LabelEncoder,        # For target variable only
    TargetEncoder,       # Encode by target statistics
)

# OneHotEncoder
ohe = OneHotEncoder(
    handle_unknown='ignore',    # Ignore unknown categories at predict time
    sparse_output=False,        # Return dense array
    drop='first',               # Drop first category to avoid multicollinearity
    min_frequency=5,            # Group rare categories
)

# OrdinalEncoder: When categories have natural order
oe = OrdinalEncoder(categories=[['low', 'medium', 'high']])

# TargetEncoder (sklearn 1.3+): For high-cardinality categoricals
te = TargetEncoder(smooth='auto')
```

### Missing Value Handling

```python
from sklearn.impute import SimpleImputer, KNNImputer, IterativeImputer

# Simple strategies
imp_mean = SimpleImputer(strategy='mean')
imp_median = SimpleImputer(strategy='median')
imp_mode = SimpleImputer(strategy='most_frequent')
imp_const = SimpleImputer(strategy='constant', fill_value=0)

# KNN-based imputation
imp_knn = KNNImputer(n_neighbors=5, weights='distance')

# Iterative (MICE-like) imputation
from sklearn.experimental import enable_iterative_imputer
imp_iter = IterativeImputer(max_iter=10, random_state=42)
```

### Feature Engineering

```python
from sklearn.preprocessing import PolynomialFeatures, FunctionTransformer
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif

# Polynomial features
poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)

# Custom transformation
log_transformer = FunctionTransformer(np.log1p, inverse_func=np.expm1)

# Feature selection
selector = SelectKBest(score_func=f_classif, k=10)
X_selected = selector.fit_transform(X, y)
selected_features = np.array(feature_names)[selector.get_support()]
```

## All Major Algorithms

### Classification

```python
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC, LinearSVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    AdaBoostClassifier,
    ExtraTreesClassifier,
    BaggingClassifier,
    VotingClassifier,
    StackingClassifier,
)
from sklearn.naive_bayes import GaussianNB, MultinomialNB
from sklearn.neural_network import MLPClassifier

# Algorithm Selection Guide:
# ┌─────────────────────┬────────────────────────────────────────┐
# │ Algorithm           │ Best For                               │
# ├─────────────────────┼────────────────────────────────────────┤
# │ LogisticRegression  │ Baseline, interpretable, linear sep.   │
# │ SVC                 │ Small datasets, non-linear boundaries  │
# │ KNN                 │ Simple, no assumptions, small data     │
# │ DecisionTree        │ Interpretable, feature importance      │
# │ RandomForest        │ General purpose, robust                │
# │ GradientBoosting    │ Best accuracy for tabular data         │
# │ GaussianNB          │ Fast baseline, text classification     │
# │ MLP                 │ Complex non-linear patterns            │
# └─────────────────────┴────────────────────────────────────────┘

# Ensemble example: Stacking
estimators = [
    ('rf', RandomForestClassifier(n_estimators=100)),
    ('gb', GradientBoostingClassifier(n_estimators=100)),
    ('svc', SVC(probability=True))
]
stacking = StackingClassifier(
    estimators=estimators,
    final_estimator=LogisticRegression(),
    cv=5
)
```

### Regression

```python
from sklearn.linear_model import (
    LinearRegression,
    Ridge,              # L2 regularization
    Lasso,             # L1 regularization (feature selection)
    ElasticNet,        # L1 + L2
    SGDRegressor,      # Scalable for large data
)
from sklearn.svm import SVR
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.neighbors import KNeighborsRegressor

# Regularization comparison:
# Ridge: keeps all features, shrinks coefficients
# Lasso: can zero out features (automatic feature selection)
# ElasticNet: balance of both

ridge = Ridge(alpha=1.0)  # higher alpha = more regularization
lasso = Lasso(alpha=0.1)
elastic = ElasticNet(alpha=0.1, l1_ratio=0.5)  # 0=Ridge, 1=Lasso
```

### Clustering

```python
from sklearn.cluster import (
    KMeans,
    DBSCAN,
    AgglomerativeClustering,
    MeanShift,
    SpectralClustering,
    OPTICS,
)
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, calinski_harabasz_score

# KMeans: Fast, assumes spherical clusters
kmeans = KMeans(n_clusters=5, init='k-means++', n_init=10, random_state=42)
labels = kmeans.fit_predict(X)
print(f"Silhouette: {silhouette_score(X, labels):.4f}")

# DBSCAN: Density-based, finds arbitrary shapes, handles noise
dbscan = DBSCAN(eps=0.5, min_samples=5)  # No need to specify n_clusters

# Elbow method for optimal K
inertias = []
for k in range(2, 15):
    km = KMeans(n_clusters=k, random_state=42)
    km.fit(X)
    inertias.append(km.inertia_)
```

### Dimensionality Reduction

```python
from sklearn.decomposition import PCA, TruncatedSVD, NMF
from sklearn.manifold import TSNE
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

# PCA: Linear dimensionality reduction
pca = PCA(n_components=0.95)  # Keep 95% variance
X_reduced = pca.fit_transform(X)
print(f"Components needed: {pca.n_components_}")
print(f"Explained variance: {pca.explained_variance_ratio_}")

# t-SNE: Non-linear, for visualization only (2D/3D)
tsne = TSNE(n_components=2, perplexity=30, random_state=42)
X_2d = tsne.fit_transform(X)  # DO NOT use for new data (no .transform())
```

## Pipeline and ColumnTransformer

```python
from sklearn.pipeline import Pipeline, make_pipeline, FeatureUnion
from sklearn.compose import ColumnTransformer, make_column_transformer

# ColumnTransformer: Apply different transformations to different columns
preprocessor = ColumnTransformer(
    transformers=[
        ('num', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('poly', PolynomialFeatures(degree=2, include_bias=False))
        ]), numeric_features),
        
        ('cat', Pipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value='missing')),
            ('encoder', OneHotEncoder(handle_unknown='ignore'))
        ]), categorical_features),
        
        ('text', Pipeline([
            ('tfidf', TfidfVectorizer(max_features=1000))
        ]), 'description'),  # single column
    ],
    remainder='drop',
    n_jobs=-1
)

# Full pipeline
full_pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('feature_selection', SelectKBest(k=50)),
    ('classifier', GradientBoostingClassifier())
])

# Access nested parameters (for GridSearchCV)
# Pattern: step__nested_step__parameter
params = {
    'preprocessor__num__imputer__strategy': ['mean', 'median'],
    'classifier__n_estimators': [100, 200],
    'classifier__learning_rate': [0.01, 0.1],
}
```

### FeatureUnion: Combine multiple feature extraction methods

```python
from sklearn.pipeline import FeatureUnion

feature_union = FeatureUnion([
    ('pca', PCA(n_components=10)),
    ('select_best', SelectKBest(k=5)),
])

pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('features', feature_union),
    ('classifier', LogisticRegression())
])
```

## Cross-Validation and Hyperparameter Tuning

```python
from sklearn.model_selection import (
    cross_val_score,
    cross_validate,
    KFold,
    StratifiedKFold,
    TimeSeriesSplit,
    GroupKFold,
    RepeatedStratifiedKFold,
    GridSearchCV,
    RandomizedSearchCV,
    learning_curve,
    validation_curve,
)
from scipy.stats import randint, uniform

# Stratified K-Fold (preserves class distribution)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X, y, cv=skf, scoring='f1_macro')

# Multiple metrics at once
results = cross_validate(
    pipeline, X, y, cv=5,
    scoring=['accuracy', 'f1_macro', 'roc_auc'],
    return_train_score=True
)

# Time Series Split (respects temporal order)
tscv = TimeSeriesSplit(n_splits=5)

# RandomizedSearchCV (better for large search spaces)
param_distributions = {
    'classifier__n_estimators': randint(50, 500),
    'classifier__max_depth': randint(3, 30),
    'classifier__learning_rate': uniform(0.01, 0.3),
    'classifier__subsample': uniform(0.6, 0.4),
}

random_search = RandomizedSearchCV(
    pipeline, param_distributions,
    n_iter=100, cv=5, scoring='f1_macro',
    random_state=42, n_jobs=-1
)
random_search.fit(X_train, y_train)

# Learning curve (diagnose bias/variance)
train_sizes, train_scores, val_scores = learning_curve(
    pipeline, X, y, cv=5,
    train_sizes=np.linspace(0.1, 1.0, 10),
    scoring='accuracy'
)
```

## Custom Estimators and Transformers

```python
from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
from sklearn.utils.validation import check_X_y, check_array, check_is_fitted

class OutlierRemover(BaseEstimator, TransformerMixin):
    """Custom transformer that caps outliers using IQR method."""
    
    def __init__(self, factor=1.5):
        self.factor = factor
    
    def fit(self, X, y=None):
        X = check_array(X)
        Q1 = np.percentile(X, 25, axis=0)
        Q3 = np.percentile(X, 75, axis=0)
        IQR = Q3 - Q1
        self.lower_ = Q1 - self.factor * IQR
        self.upper_ = Q3 + self.factor * IQR
        return self
    
    def transform(self, X):
        check_is_fitted(self, ['lower_', 'upper_'])
        X = check_array(X).copy()
        X = np.clip(X, self.lower_, self.upper_)
        return X


class DateFeatureExtractor(BaseEstimator, TransformerMixin):
    """Extract features from datetime columns."""
    
    def __init__(self, date_column='date'):
        self.date_column = date_column
    
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        X = X.copy()
        dt = pd.to_datetime(X[self.date_column])
        X['year'] = dt.dt.year
        X['month'] = dt.dt.month
        X['day_of_week'] = dt.dt.dayofweek
        X['is_weekend'] = (dt.dt.dayofweek >= 5).astype(int)
        X = X.drop(columns=[self.date_column])
        return X
    
    def get_feature_names_out(self, input_features=None):
        return ['year', 'month', 'day_of_week', 'is_weekend']


# Custom classifier
class ThresholdClassifier(BaseEstimator, ClassifierMixin):
    """Wrapper that allows custom threshold for binary classification."""
    
    def __init__(self, estimator=None, threshold=0.5):
        self.estimator = estimator
        self.threshold = threshold
    
    def fit(self, X, y):
        X, y = check_X_y(X, y)
        self.classes_ = np.unique(y)
        self.estimator_ = self.estimator.fit(X, y)
        return self
    
    def predict(self, X):
        check_is_fitted(self)
        proba = self.estimator_.predict_proba(X)[:, 1]
        return (proba >= self.threshold).astype(int)
    
    def predict_proba(self, X):
        check_is_fitted(self)
        return self.estimator_.predict_proba(X)

# Usage in pipeline
pipeline = Pipeline([
    ('outlier', OutlierRemover(factor=2.0)),
    ('scaler', StandardScaler()),
    ('clf', ThresholdClassifier(
        estimator=LogisticRegression(),
        threshold=0.3
    ))
])
```

## Model Persistence

```python
import joblib
import pickle

# Method 1: joblib (PREFERRED for sklearn - handles numpy arrays efficiently)
joblib.dump(pipeline, 'model.joblib')
loaded_model = joblib.load('model.joblib')

# Method 2: joblib with compression
joblib.dump(pipeline, 'model.joblib.gz', compress=3)

# Method 3: pickle (standard library)
with open('model.pkl', 'wb') as f:
    pickle.dump(pipeline, f, protocol=pickle.HIGHEST_PROTOCOL)

with open('model.pkl', 'rb') as f:
    loaded_model = pickle.load(f)

# IMPORTANT: Version compatibility
# Save metadata alongside model
import sklearn
metadata = {
    'sklearn_version': sklearn.__version__,
    'python_version': '3.10',
    'feature_names': feature_names,
    'target_names': target_names,
    'training_date': '2024-01-15',
    'metrics': {'accuracy': 0.95, 'f1': 0.93}
}
joblib.dump({'model': pipeline, 'metadata': metadata}, 'model_bundle.joblib')
```

## Production Deployment Patterns

### Pattern 1: Flask REST API

```python
from flask import Flask, request, jsonify
import joblib
import pandas as pd

app = Flask(__name__)
model = joblib.load('model_pipeline.joblib')

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    df = pd.DataFrame([data])
    prediction = model.predict(df)
    probability = model.predict_proba(df)
    return jsonify({
        'prediction': int(prediction[0]),
        'probability': probability[0].tolist()
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})
```

### Pattern 2: Batch Prediction

```python
def batch_predict(input_path, output_path, model_path, chunk_size=10000):
    """Memory-efficient batch prediction for large datasets."""
    model = joblib.load(model_path)
    
    results = []
    for chunk in pd.read_csv(input_path, chunksize=chunk_size):
        predictions = model.predict(chunk)
        probabilities = model.predict_proba(chunk)[:, 1]
        chunk['prediction'] = predictions
        chunk['probability'] = probabilities
        results.append(chunk)
    
    pd.concat(results).to_csv(output_path, index=False)
```

### Pattern 3: Model Registry Pattern

```python
class ModelRegistry:
    """Simple model registry for A/B testing and rollback."""
    
    def __init__(self, registry_dir='models/'):
        self.registry_dir = registry_dir
    
    def register(self, model, version, metrics):
        path = f"{self.registry_dir}/model_v{version}.joblib"
        bundle = {'model': model, 'metrics': metrics, 'version': version}
        joblib.dump(bundle, path)
    
    def load(self, version='latest'):
        if version == 'latest':
            # Load highest version
            files = sorted(glob.glob(f"{self.registry_dir}/model_v*.joblib"))
            path = files[-1]
        else:
            path = f"{self.registry_dir}/model_v{version}.joblib"
        return joblib.load(path)
```

## Common Patterns and Anti-Patterns

### Anti-Patterns (DON'T DO)

```python
# BAD: Fitting scaler on entire dataset before split (data leakage!)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # WRONG - uses test info
X_train, X_test = train_test_split(X_scaled)

# BAD: Feature selection on entire dataset
selector = SelectKBest(k=10)
X_selected = selector.fit_transform(X, y)  # WRONG - leaks test info
X_train, X_test = train_test_split(X_selected)

# BAD: Not using Pipeline (manual preprocessing is error-prone)
scaler.fit(X_train)
X_train_scaled = scaler.transform(X_train)
model.fit(X_train_scaled, y_train)
# Easy to forget to transform X_test the same way!
```

### Best Practices (DO)

```python
# GOOD: Use Pipeline to prevent data leakage
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('selector', SelectKBest(k=10)),
    ('model', RandomForestClassifier())
])
pipeline.fit(X_train, y_train)  # All steps fitted only on train

# GOOD: Stratified split for classification
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)

# GOOD: Use cross-validation for reliable estimates
scores = cross_val_score(pipeline, X_train, y_train, cv=5)

# GOOD: Set random_state for reproducibility
model = RandomForestClassifier(n_estimators=100, random_state=42)
```

## Performance Optimization

```python
# 1. Use n_jobs=-1 for parallelism
model = RandomForestClassifier(n_estimators=100, n_jobs=-1)
grid_search = GridSearchCV(pipeline, params, cv=5, n_jobs=-1)

# 2. Use sparse matrices for high-dimensional sparse data
from scipy.sparse import csr_matrix
X_sparse = csr_matrix(X)  # TF-IDF, one-hot encoded data

# 3. Incremental learning for large datasets
from sklearn.linear_model import SGDClassifier
sgd = SGDClassifier(loss='log_loss')
for X_batch, y_batch in data_generator:
    sgd.partial_fit(X_batch, y_batch, classes=all_classes)

# 4. Feature hashing for very high cardinality
from sklearn.feature_extraction import FeatureHasher
hasher = FeatureHasher(n_features=1024, input_type='string')

# 5. Approximate nearest neighbors
from sklearn.neighbors import KDTree, BallTree

# 6. Warm start for iterative refinement
model = GradientBoostingClassifier(n_estimators=100, warm_start=True)
model.fit(X_train, y_train)
model.n_estimators = 200  # Add more trees
model.fit(X_train, y_train)  # Continues from where it left off
```

## Integration with Pandas

```python
# sklearn 1.2+ set_output API
from sklearn import set_config
set_config(transform_output='pandas')  # Global setting

# Or per-transformer
scaler = StandardScaler().set_output(transform='pandas')
X_scaled = scaler.fit_transform(X)  # Returns DataFrame with column names!

# ColumnTransformer with pandas output
preprocessor = ColumnTransformer(
    transformers=[...],
).set_output(transform='pandas')

# Get feature names from pipeline
pipeline.fit(X_train, y_train)
feature_names = pipeline[:-1].get_feature_names_out()
```

## Summary Cheat Sheet

```
Data Flow:
Raw Data → Split → Pipeline(Preprocess → Feature Eng → Model) → Evaluate → Deploy

Key Rules:
1. ALWAYS split before preprocessing
2. ALWAYS use Pipeline to prevent leakage
3. Use cross-validation, not single train/test split
4. Use stratified splits for classification
5. Set random_state for reproducibility
6. Save entire pipeline (not just model)
7. Version your models with metadata
```
