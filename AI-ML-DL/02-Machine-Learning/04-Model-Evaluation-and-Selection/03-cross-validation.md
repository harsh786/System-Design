# Cross-Validation

## Why Cross-Validation?

A single train/test split is unreliable — performance depends on which samples end up in each split. Cross-validation gives a more robust estimate by averaging over multiple splits.

---

## K-Fold Cross-Validation

```
K-Fold (K=5):

Fold 1: [VAL] [Train] [Train] [Train] [Train] → score₁
Fold 2: [Train] [VAL] [Train] [Train] [Train] → score₂
Fold 3: [Train] [Train] [VAL] [Train] [Train] → score₃
Fold 4: [Train] [Train] [Train] [VAL] [Train] → score₄
Fold 5: [Train] [Train] [Train] [Train] [VAL] → score₅

Final score = mean(scores) ± std(scores)
```

**Typical K values:**
- K=5 or K=10: Standard (good bias-variance tradeoff)
- K=N (LOO): Very small datasets (<100 samples), low bias but high variance
- K=3: Very large datasets or expensive models (for speed)

---

## Stratified K-Fold

Preserves class distribution in each fold. **Always use for classification.**

```python
from sklearn.model_selection import StratifiedKFold

skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = []
for train_idx, val_idx in skf.split(X, y):
    model.fit(X[train_idx], y[train_idx])
    scores.append(model.score(X[val_idx], y[val_idx]))
print(f"{np.mean(scores):.4f} ± {np.std(scores):.4f}")
```

Without stratification on imbalanced data: some folds may have very few minority samples → unstable estimates.

---

## Group K-Fold

Ensures all samples from the same group stay together (same fold).

**Use when:** Samples within a group are correlated (e.g., multiple readings from same patient, multiple photos from same user).

```python
from sklearn.model_selection import GroupKFold

# groups = patient_id for each sample
gkf = GroupKFold(n_splits=5)
for train_idx, val_idx in gkf.split(X, y, groups=groups):
    # No patient appears in both train and val
    model.fit(X[train_idx], y[train_idx])
```

**Why it matters:** Without group splitting, model sees training examples from the same patient and "memorizes" patient-specific patterns → overoptimistic CV score.

---

## Time Series Split

```
Fold 1: [Train] [Val]
Fold 2: [Train    ] [Val]
Fold 3: [Train        ] [Val]
Fold 4: [Train            ] [Val]
Fold 5: [Train                ] [Val]

NEVER let future data leak into training!
```

```python
from sklearn.model_selection import TimeSeriesSplit

tscv = TimeSeriesSplit(n_splits=5, gap=30)  # 30-sample gap to prevent leakage
for train_idx, val_idx in tscv.split(X):
    model.fit(X[train_idx], y[train_idx])
    score = model.score(X[val_idx], y[val_idx])
```

### Key considerations:
- **Gap:** Insert gap between train and test equal to forecast horizon (prevents feature leakage from lagged features)
- **Minimum training size:** Need enough history to learn patterns
- **Expanding vs sliding window:** Expanding uses all history; sliding if old data is harmful

---

## Leave-One-Out (LOO)

K=N: Train on N-1 samples, validate on 1. Repeat N times.

**Pros:** Low bias (uses almost all data for training)
**Cons:** High variance, expensive (N model fits), no stratification

**Use only for:** Very small datasets (<100 samples) where every sample matters.

---

## Nested Cross-Validation

For **unbiased** model selection + evaluation simultaneously.

```
Outer loop (K=5): Model assessment (final performance estimate)
  Inner loop (K=5): Model selection (hyperparameter tuning)

┌── Outer Fold 1 ──────────────────────────────────────┐
│  [═══ Inner CV for tuning ═══] [Outer Val → score₁]  │
├── Outer Fold 2 ──────────────────────────────────────┤
│  [═══ Inner CV for tuning ═══] [Outer Val → score₂]  │
├── ...                                                 │
└───────────────────────────────────────────────────────┘

Final unbiased estimate = mean(outer scores)
```

```python
from sklearn.model_selection import cross_val_score, GridSearchCV

# Inner loop: tune hyperparameters
inner_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
grid = GridSearchCV(model, param_grid, cv=inner_cv, scoring='roc_auc')

# Outer loop: unbiased performance estimate
outer_cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
nested_scores = cross_val_score(grid, X, y, cv=outer_cv, scoring='roc_auc')
print(f"Nested CV AUC: {nested_scores.mean():.4f} ± {nested_scores.std():.4f}")
```

**When to use:** When you need an unbiased performance estimate AND are tuning hyperparameters. Standard CV + tuning gives an optimistic estimate.

---

## When to Use Which Split Strategy

| Strategy | Use When | Example |
|----------|----------|---------|
| Stratified K-Fold | Classification (default) | Any classification task |
| K-Fold | Regression | Predicting house prices |
| Group K-Fold | Correlated samples | Multiple samples per patient |
| Time Series Split | Temporal data | Stock prediction, demand forecast |
| LOO | Very small data (n<100) | Rare disease study |
| Nested CV | Need unbiased eval + tuning | Comparing model families |
| Repeated K-Fold | Need robust estimate | Small-medium datasets |

---

## From-Scratch Implementation

```python
import numpy as np

class StratifiedKFoldScratch:
    def __init__(self, n_splits=5, shuffle=True, random_state=42):
        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state
    
    def split(self, X, y):
        rng = np.random.RandomState(self.random_state)
        classes = np.unique(y)
        fold_indices = [[] for _ in range(self.n_splits)]
        
        for cls in classes:
            cls_indices = np.where(y == cls)[0]
            if self.shuffle:
                rng.shuffle(cls_indices)
            
            for i, idx in enumerate(cls_indices):
                fold_indices[i % self.n_splits].append(idx)
        
        for i in range(self.n_splits):
            test_idx = np.array(fold_indices[i])
            train_idx = np.concatenate([fold_indices[j] for j in range(self.n_splits) if j != i])
            yield train_idx, test_idx
```

---

## Common Mistakes (Data Leakage!)

### 1. Preprocessing Before Split

```python
# WRONG: Scaler sees test data!
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)  # ← fit on ALL data including test
X_train, X_test = X_scaled[train_idx], X_scaled[test_idx]

# RIGHT: Fit only on training data
scaler = StandardScaler()
X_train = scaler.fit_transform(X[train_idx])  # fit on train only
X_test = scaler.transform(X[test_idx])         # transform test
```

### 2. Feature Selection Before Split

```python
# WRONG: Feature selection uses all data
selector = SelectKBest(k=10)
X_selected = selector.fit_transform(X, y)  # ← sees all labels!
# Then do CV on X_selected → optimistic

# RIGHT: Feature selection inside CV loop
for train_idx, val_idx in kf.split(X, y):
    selector.fit(X[train_idx], y[train_idx])  # fit on train only
    X_train_sel = selector.transform(X[train_idx])
    X_val_sel = selector.transform(X[val_idx])
```

### 3. Target Encoding Without CV

```python
# WRONG: Encode using all targets
X['city_encoded'] = X.groupby('city')['target'].transform('mean')
# Then CV → target leakage!

# RIGHT: Target encode within each fold
for train_idx, val_idx in kf.split(X, y):
    means = X.iloc[train_idx].groupby('city')['target'].mean()
    X_train['city_enc'] = X.iloc[train_idx]['city'].map(means)
    X_val['city_enc'] = X.iloc[val_idx]['city'].map(means)
```

### 4. Using Standard K-Fold for Time Series

```python
# WRONG: Random folds for time series
kf = KFold(n_splits=5, shuffle=True)  # Future leaks into past!

# RIGHT: Time-aware split
tscv = TimeSeriesSplit(n_splits=5)
```

---

## Code: Complete CV Workflow

```python
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Use Pipeline to prevent leakage
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('model', LogisticRegression())
])

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

results = cross_validate(
    pipe, X, y, cv=cv,
    scoring=['accuracy', 'roc_auc', 'f1'],
    return_train_score=True
)

for metric in ['accuracy', 'roc_auc', 'f1']:
    train = results[f'train_{metric}']
    test = results[f'test_{metric}']
    print(f"{metric}: train={train.mean():.4f}, val={test.mean():.4f} ± {test.std():.4f}")
    print(f"  Gap: {train.mean() - test.mean():.4f} (overfitting indicator)")
```

---

## Interview Questions

**Q: Why use Stratified K-Fold over regular K-Fold for classification?**
Preserves class distribution in each fold. Without it, some folds may have few minority samples → high variance in estimates, especially for imbalanced data.

**Q: What's the problem with preprocessing before the CV split?**
The test fold "leaks" into preprocessing (e.g., scaler mean includes test data). This makes CV scores optimistically biased. Always fit preprocessing on training fold only.

**Q: How many folds should you use?**
K=5-10 is standard. Higher K: less bias but more variance and computation. K=N (LOO) for tiny datasets. K=3 for very large or expensive models.

**Q: When is nested CV necessary?**
When you need an unbiased estimate of the model's performance after hyperparameter tuning. Single-loop CV with tuning gives an optimistic estimate because the tuning process "peeks" at validation data.
