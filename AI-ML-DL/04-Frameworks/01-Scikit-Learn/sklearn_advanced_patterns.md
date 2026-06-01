# Scikit-Learn Advanced Patterns

## 1. Custom Estimators

### Implementing fit(), predict(), transform()

```python
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin, ClassifierMixin
from sklearn.utils.validation import check_is_fitted, check_X_y, check_array

class OutlierRemover(BaseEstimator, TransformerMixin):
    """Custom transformer that caps outliers using IQR method."""
    
    def __init__(self, factor=1.5):
        self.factor = factor
    
    def fit(self, X, y=None):
        X = check_array(X)
        Q1 = np.percentile(X, 25, axis=0)
        Q3 = np.percentile(X, 75, axis=0)
        IQR = Q3 - Q1
        self.lower_bound_ = Q1 - self.factor * IQR
        self.upper_bound_ = Q3 + self.factor * IQR
        return self
    
    def transform(self, X):
        check_is_fitted(self, ['lower_bound_', 'upper_bound_'])
        X = check_array(X)
        return np.clip(X, self.lower_bound_, self.upper_bound_)


class WeightedKNN(BaseEstimator, ClassifierMixin):
    """Custom classifier with distance-weighted KNN."""
    
    def __init__(self, n_neighbors=5, power=2):
        self.n_neighbors = n_neighbors
        self.power = power
    
    def fit(self, X, y):
        X, y = check_X_y(X, y)
        self.X_train_ = X
        self.y_train_ = y
        self.classes_ = np.unique(y)
        return self
    
    def predict(self, X):
        check_is_fitted(self, ['X_train_', 'y_train_'])
        X = check_array(X)
        distances = np.linalg.norm(X[:, np.newaxis] - self.X_train_, axis=2)
        nearest_idx = np.argsort(distances, axis=1)[:, :self.n_neighbors]
        nearest_labels = self.y_train_[nearest_idx]
        nearest_dists = np.take_along_axis(distances, nearest_idx, axis=1)
        weights = 1 / (nearest_dists ** self.power + 1e-8)
        
        predictions = []
        for i in range(X.shape[0]):
            class_weights = {}
            for cls in self.classes_:
                mask = nearest_labels[i] == cls
                class_weights[cls] = weights[i][mask].sum()
            predictions.append(max(class_weights, key=class_weights.get))
        return np.array(predictions)
```

### Custom Scorer Functions

```python
from sklearn.metrics import make_scorer, fbeta_score

# Custom business metric
def profit_score(y_true, y_pred, revenue_per_tp=100, cost_per_fp=50):
    tp = ((y_pred == 1) & (y_true == 1)).sum()
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    return tp * revenue_per_tp - fp * cost_per_fp

profit_scorer = make_scorer(profit_score, greater_is_better=True)

# Weighted F-beta scorer
f2_scorer = make_scorer(fbeta_score, beta=2)
```

### Parameter Validation Pattern

```python
from sklearn.utils import check_random_state

class ValidatedEstimator(BaseEstimator, TransformerMixin):
    def __init__(self, alpha=1.0, method='mean', random_state=None):
        self.alpha = alpha
        self.method = method
        self.random_state = random_state
    
    def _validate_params(self):
        if self.alpha <= 0:
            raise ValueError(f"alpha must be > 0, got {self.alpha}")
        if self.method not in ('mean', 'median'):
            raise ValueError(f"method must be 'mean' or 'median', got {self.method}")
    
    def fit(self, X, y=None):
        self._validate_params()
        self.rng_ = check_random_state(self.random_state)
        X = check_array(X)
        if self.method == 'mean':
            self.center_ = np.mean(X, axis=0)
        else:
            self.center_ = np.median(X, axis=0)
        return self
    
    def transform(self, X):
        check_is_fitted(self, ['center_'])
        X = check_array(X)
        return (X - self.center_) * self.alpha
```

---

## 2. Advanced Pipelines

### ColumnTransformer (Different Transforms Per Column Type)

```python
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.impute import SimpleImputer

numeric_features = ['age', 'income', 'score']
categorical_features = ['gender', 'city', 'category']
ordinal_features = ['education']  # low < medium < high

preprocessor = ColumnTransformer(
    transformers=[
        ('num', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ]), numeric_features),
        
        ('cat', Pipeline([
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
        ]), categorical_features),
        
        ('ord', OrdinalEncoder(
            categories=[['low', 'medium', 'high']]
        ), ordinal_features),
    ],
    remainder='drop'  # or 'passthrough'
)
```

### FeatureUnion (Parallel Feature Extraction)

```python
from sklearn.pipeline import FeatureUnion
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_classif

# Combine multiple feature extraction methods
feature_union = FeatureUnion([
    ('pca', PCA(n_components=5)),
    ('select_best', SelectKBest(f_classif, k=10)),
    ('custom', OutlierRemover(factor=2.0)),  # custom transformer
])

# Full pipeline with FeatureUnion
pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('features', feature_union),
    ('classifier', RandomForestClassifier())
])
```

### Nested Pipelines

```python
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

# Inner pipeline for feature engineering
feature_pipeline = Pipeline([
    ('impute', SimpleImputer(strategy='median')),
    ('scale', StandardScaler()),
    ('reduce', PCA(n_components=10)),
])

# Outer pipeline combining everything
full_pipeline = Pipeline([
    ('features', feature_pipeline),
    ('classify', LogisticRegression())
])

# Access nested parameters with double underscore
full_pipeline.set_params(features__reduce__n_components=15)
```

### Pipeline with Custom Steps

```python
from sklearn.base import BaseEstimator, TransformerMixin

class FeatureInteractions(BaseEstimator, TransformerMixin):
    """Generate polynomial interactions for selected features."""
    def __init__(self, degree=2, interaction_only=True):
        self.degree = degree
        self.interaction_only = interaction_only
    
    def fit(self, X, y=None):
        self.n_features_in_ = X.shape[1]
        return self
    
    def transform(self, X):
        check_is_fitted(self)
        X = check_array(X)
        interactions = []
        for i in range(X.shape[1]):
            for j in range(i+1, X.shape[1]):
                interactions.append(X[:, i] * X[:, j])
        return np.column_stack([X] + interactions)

pipeline = Pipeline([
    ('preprocess', preprocessor),
    ('interactions', FeatureInteractions(degree=2)),
    ('select', SelectKBest(k=20)),
    ('model', GradientBoostingClassifier())
])
```

### Caching Pipeline Steps (`memory` Parameter)

```python
from tempfile import mkdtemp
from shutil import rmtree

# Cache expensive transformations to disk
cachedir = mkdtemp()

cached_pipeline = Pipeline(
    [
        ('preprocess', preprocessor),          # cached after first run
        ('pca', PCA(n_components=50)),         # cached after first run
        ('model', RandomForestClassifier()),   # re-trained each time
    ],
    memory=cachedir  # or use joblib.Memory
)

# When tuning only model params, preprocessing is loaded from cache
# Clean up: rmtree(cachedir)
```

---

## 3. Hyperparameter Tuning Deep Dive

### GridSearchCV Internals

```python
from sklearn.model_selection import GridSearchCV, StratifiedKFold

param_grid = {
    'model__n_estimators': [100, 200, 500],
    'model__max_depth': [3, 5, 10, None],
    'model__min_samples_split': [2, 5, 10],
    'preprocess__num__imputer__strategy': ['mean', 'median'],
}

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

grid_search = GridSearchCV(
    pipeline,
    param_grid,
    cv=cv,
    scoring='roc_auc',
    n_jobs=-1,
    verbose=2,
    refit=True,           # refit best model on full training set
    return_train_score=True,
    error_score='raise',  # fail loudly on errors
)

grid_search.fit(X_train, y_train)

# Access results
print(f"Best score: {grid_search.best_score_:.4f}")
print(f"Best params: {grid_search.best_params_}")
results_df = pd.DataFrame(grid_search.cv_results_)
```

### RandomizedSearchCV with Distributions

```python
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import uniform, randint, loguniform

param_distributions = {
    'model__n_estimators': randint(50, 500),
    'model__max_depth': randint(2, 20),
    'model__learning_rate': loguniform(1e-4, 1e-1),
    'model__subsample': uniform(0.6, 0.4),
    'model__min_samples_leaf': randint(1, 20),
    'model__max_features': uniform(0.3, 0.7),
}

random_search = RandomizedSearchCV(
    pipeline,
    param_distributions,
    n_iter=100,          # number of parameter settings sampled
    cv=5,
    scoring='f1_weighted',
    n_jobs=-1,
    random_state=42,
    refit=True,
)
```

### Bayesian Optimization (with scikit-optimize)

```python
from skopt import BayesSearchCV
from skopt.space import Real, Integer, Categorical

bayes_search = BayesSearchCV(
    pipeline,
    search_spaces={
        'model__n_estimators': Integer(50, 500),
        'model__max_depth': Integer(2, 20),
        'model__learning_rate': Real(1e-4, 0.3, prior='log-uniform'),
        'model__subsample': Real(0.5, 1.0),
    },
    n_iter=50,
    cv=5,
    scoring='roc_auc',
    n_jobs=-1,
    random_state=42,
)
```

### Halving Search (Successive Halving)

```python
from sklearn.experimental import enable_halving_search_cv
from sklearn.model_selection import HalvingRandomSearchCV

# Starts with many candidates on small data, progressively eliminates
halving_search = HalvingRandomSearchCV(
    pipeline,
    param_distributions,
    n_candidates=200,    # start with 200 candidates
    factor=3,           # eliminate 2/3 each round
    resource='n_samples',  # increase data each round
    min_resources=100,
    cv=5,
    scoring='accuracy',
    random_state=42,
    n_jobs=-1,
)
```

### Custom Cross-Validation Strategies

```python
from sklearn.model_selection import (
    TimeSeriesSplit, GroupKFold, RepeatedStratifiedKFold, LeaveOneGroupOut
)

# Time series - no future leakage
tscv = TimeSeriesSplit(n_splits=5, gap=10)

# Group-aware - ensure same group isn't in train and test
group_cv = GroupKFold(n_splits=5)
# Usage: cross_val_score(model, X, y, groups=patient_ids, cv=group_cv)

# Repeated stratified - more stable estimates
rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)

# Custom splitter
class PurgedTimeSeriesSplit:
    """Time series CV with purge gap to prevent leakage."""
    def __init__(self, n_splits=5, purge_gap=5):
        self.n_splits = n_splits
        self.purge_gap = purge_gap
    
    def split(self, X, y=None, groups=None):
        n = len(X)
        fold_size = n // (self.n_splits + 1)
        for i in range(self.n_splits):
            train_end = fold_size * (i + 1)
            test_start = train_end + self.purge_gap
            test_end = test_start + fold_size
            if test_end > n:
                break
            yield (np.arange(train_end), np.arange(test_start, test_end))
    
    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits
```

---

## 4. Model Interpretation

### Permutation Importance

```python
from sklearn.inspection import permutation_importance

# Compute on TEST set to avoid bias
result = permutation_importance(
    model, X_test, y_test,
    n_repeats=30,
    random_state=42,
    n_jobs=-1,
    scoring='accuracy'
)

# Sort and display
sorted_idx = result.importances_mean.argsort()[::-1]
for idx in sorted_idx[:10]:
    print(f"{feature_names[idx]:<30} "
          f"{result.importances_mean[idx]:.4f} "
          f"+/- {result.importances_std[idx]:.4f}")
```

### Partial Dependence Plots

```python
from sklearn.inspection import PartialDependenceDisplay

fig, ax = plt.subplots(figsize=(12, 8))
PartialDependenceDisplay.from_estimator(
    model, X_train, 
    features=['age', 'income', ('age', 'income')],  # 2D interaction
    kind='both',  # individual + average
    subsample=200,
    ax=ax,
    random_state=42,
)
plt.tight_layout()
```

### Learning Curves and Validation Curves

```python
from sklearn.model_selection import learning_curve, validation_curve

# Learning curve - how more data helps
train_sizes, train_scores, val_scores = learning_curve(
    model, X, y,
    train_sizes=np.linspace(0.1, 1.0, 10),
    cv=5, scoring='accuracy', n_jobs=-1
)

# Validation curve - effect of one hyperparameter
param_range = np.logspace(-4, 2, 20)
train_scores, val_scores = validation_curve(
    model, X, y,
    param_name='C', param_range=param_range,
    cv=5, scoring='accuracy', n_jobs=-1
)
```

---

## 5. Production Patterns

### Model Serialization

```python
import joblib
import pickle

# Method 1: joblib (preferred for numpy arrays)
joblib.dump(pipeline, 'model_v1.2.joblib', compress=3)
loaded_model = joblib.load('model_v1.2.joblib')

# Method 2: pickle
with open('model.pkl', 'wb') as f:
    pickle.dump(pipeline, f, protocol=pickle.HIGHEST_PROTOCOL)

# Method 3: ONNX export (framework-agnostic)
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

initial_type = [('float_input', FloatTensorType([None, X_train.shape[1]]))]
onnx_model = convert_sklearn(pipeline, initial_types=initial_type)
with open("model.onnx", "wb") as f:
    f.write(onnx_model.SerializeToString())
```

### Sklearn Pipeline in FastAPI

```python
# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
import joblib
import numpy as np

app = FastAPI()
model = joblib.load("model_v1.2.joblib")

class PredictionInput(BaseModel):
    age: float
    income: float
    score: float
    gender: str
    city: str
    
    @validator('age')
    def age_must_be_positive(cls, v):
        if v < 0 or v > 150:
            raise ValueError('age must be between 0 and 150')
        return v

class PredictionOutput(BaseModel):
    prediction: int
    probability: float
    model_version: str = "1.2"

@app.post("/predict", response_model=PredictionOutput)
async def predict(input_data: PredictionInput):
    try:
        X = np.array([[input_data.age, input_data.income, input_data.score]])
        pred = model.predict(X)[0]
        prob = model.predict_proba(X)[0].max()
        return PredictionOutput(prediction=int(pred), probability=float(prob))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Model Versioning Pattern

```python
import hashlib
import json
from datetime import datetime

class ModelRegistry:
    def __init__(self, base_path='./models'):
        self.base_path = base_path
    
    def save_model(self, model, metrics, params, dataset_hash):
        version = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_path = f"{self.base_path}/model_{version}.joblib"
        meta_path = f"{self.base_path}/model_{version}_meta.json"
        
        joblib.dump(model, model_path, compress=3)
        
        metadata = {
            'version': version,
            'metrics': metrics,
            'params': params,
            'dataset_hash': dataset_hash,
            'sklearn_version': sklearn.__version__,
            'created_at': datetime.now().isoformat(),
        }
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return version
```

---

## 6. Scalability

### n_jobs and Parallelism

```python
# Most sklearn estimators support n_jobs
from sklearn.ensemble import RandomForestClassifier

# -1 = use all cores, -2 = all but one
model = RandomForestClassifier(n_estimators=1000, n_jobs=-1)

# Cross-validation in parallel
from sklearn.model_selection import cross_val_score
scores = cross_val_score(model, X, y, cv=10, n_jobs=-1)

# Note: nested parallelism can cause issues
# Outer parallel (GridSearchCV n_jobs=-1) + inner (RF n_jobs=-1) = oversubscription
# Solution: set inner n_jobs=1 when using parallel CV
```

### Dask-ML for Larger-than-Memory Datasets

```python
import dask.dataframe as dd
from dask_ml.preprocessing import StandardScaler as DaskScaler
from dask_ml.model_selection import GridSearchCV as DaskGridSearchCV
from dask_ml.wrappers import ParallelPostFit

# Load data that doesn't fit in memory
ddf = dd.read_parquet('large_dataset/*.parquet')

# Wrap sklearn model for parallel prediction
model = ParallelPostFit(estimator=LogisticRegression())
model.fit(X_train, y_train)  # fit on sample
predictions = model.predict(ddf)  # predict in parallel on full data
```

### Incremental Learning (partial_fit)

```python
from sklearn.linear_model import SGDClassifier
from sklearn.naive_bayes import MultinomialNB

# Models supporting partial_fit:
# SGDClassifier, SGDRegressor, MiniBatchKMeans, 
# MultinomialNB, BernoulliNB, Perceptron

model = SGDClassifier(loss='log_loss', random_state=42)

# Stream data in chunks
chunk_size = 10000
classes = np.array([0, 1])  # must specify all classes upfront

for chunk in pd.read_csv('huge_file.csv', chunksize=chunk_size):
    X_chunk = chunk.drop('target', axis=1).values
    y_chunk = chunk['target'].values
    model.partial_fit(X_chunk, y_chunk, classes=classes)
```

### Out-of-Core Learning Pattern

```python
from sklearn.feature_extraction.text import HashingVectorizer

# HashingVectorizer doesn't need fit - works for streaming
vectorizer = HashingVectorizer(n_features=2**18, alternate_sign=False)
model = SGDClassifier(loss='log_loss')

batch_size = 5000
for i in range(0, len(texts), batch_size):
    batch_texts = texts[i:i+batch_size]
    batch_labels = labels[i:i+batch_size]
    X_batch = vectorizer.transform(batch_texts)
    model.partial_fit(X_batch, batch_labels, classes=[0, 1])
```

---

## Architecture: Production ML Pipeline Deployment

```
┌─────────────────────────────────────────────────────────┐
│                    Production Architecture                │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Client  │───▶│   FastAPI    │───▶│  Model Pool  │  │
│  │ Request  │    │  + Pydantic  │    │  (joblib)    │  │
│  └──────────┘    └──────────────┘    └──────────────┘  │
│                         │                     │          │
│                         ▼                     ▼          │
│                  ┌─────────────┐     ┌──────────────┐   │
│                  │  Input      │     │   Pipeline   │   │
│                  │  Validation │     │   (cached)   │   │
│                  └─────────────┘     └──────────────┘   │
│                                            │            │
│                         ┌──────────────────┼──────┐     │
│                         ▼                  ▼      ▼     │
│                  ┌───────────┐    ┌─────┐  ┌────────┐  │
│                  │Preprocess │    │Model│  │Logging │  │
│                  │Transform  │    │Pred │  │Monitor │  │
│                  └───────────┘    └─────┘  └────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Model Registry: version, metrics, lineage       │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Reference: Estimator API Contract

| Method | Required By | Purpose |
|--------|-------------|---------|
| `fit(X, y)` | All estimators | Learn from data |
| `predict(X)` | Classifiers, Regressors | Generate predictions |
| `transform(X)` | Transformers | Transform features |
| `fit_transform(X, y)` | TransformerMixin | Fit + transform (optimized) |
| `predict_proba(X)` | Probabilistic classifiers | Class probabilities |
| `score(X, y)` | All estimators | Default metric evaluation |
| `get_params()` | BaseEstimator | Get constructor parameters |
| `set_params()` | BaseEstimator | Set constructor parameters |
| `partial_fit(X, y)` | Incremental learners | Online learning |
