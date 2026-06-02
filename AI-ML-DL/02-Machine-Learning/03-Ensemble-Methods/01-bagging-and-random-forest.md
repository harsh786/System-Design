# Bagging and Random Forest

## Bootstrap Aggregating (Bagging)

### Algorithm

```
Bagging(D, M, LearningAlgorithm):
    for m = 1 to M:
        D_m = Bootstrap sample from D (sample n items with replacement)
        h_m = LearningAlgorithm(D_m)
    
    Prediction:
      Classification: majority_vote(h₁(x), h₂(x), ..., hₘ(x))
      Regression:     (1/M) Σ hₘ(x)
```

### Why It Reduces Variance

For M independent models with variance σ²:
- Variance of average = σ²/M

In practice, models aren't fully independent (trained on overlapping data), so:
- Var(ensemble) = ρσ² + (1-ρ)σ²/M, where ρ = pairwise correlation

**Key insight:** The less correlated the models, the more variance reduction.

### Bootstrap Sampling

```
Original: [1, 2, 3, 4, 5, 6, 7, 8]

Bootstrap 1: [2, 5, 5, 1, 8, 3, 1, 7]  ← with replacement
Bootstrap 2: [3, 1, 6, 6, 4, 8, 2, 2]
Bootstrap 3: [7, 4, 1, 5, 3, 3, 8, 6]

Each sample contains ~63.2% unique items (1 - 1/e)
Remaining ~36.8% = Out-of-Bag (OOB) samples → free validation!
```

---

## Random Forest

**Random Forest = Bagging + Random Feature Subsets**

```
Key modification: At each split, only consider √p features (classification)
                  or p/3 features (regression)

This decorrelates the trees → further reduces variance!

┌─────────────────────────────────────────────────────────┐
│                    RANDOM FOREST                          │
│                                                          │
│  Bootstrap 1     Bootstrap 2     Bootstrap 3    ...     │
│  Features: √p    Features: √p    Features: √p          │
│       │               │               │                  │
│    ┌──┴──┐         ┌──┴──┐         ┌──┴──┐             │
│    │Tree1│         │Tree2│         │Tree3│    ...       │
│    └──┬──┘         └──┬──┘         └──┬──┘             │
│       │               │               │                  │
│       ▼               ▼               ▼                  │
│    pred_1          pred_2          pred_3               │
│              ╲        │        ╱                         │
│               ╲       │       ╱                          │
│                ▼      ▼      ▼                           │
│            ┌──────────────────────┐                      │
│            │   Majority Vote /    │                      │
│            │      Average         │                      │
│            └──────────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### OOB (Out-of-Bag) Error

Each tree doesn't see ~36.8% of training data. Use those unseen samples as free validation:

```python
from sklearn.ensemble import RandomForestClassifier

rf = RandomForestClassifier(n_estimators=500, oob_score=True, random_state=42)
rf.fit(X_train, y_train)
print(f"OOB Score: {rf.oob_score_:.4f}")  # No need for separate validation!
```

OOB error ≈ Leave-One-Out CV error (proven by Breiman).

---

## Feature Importance

### Method 1: Mean Decrease in Impurity (MDI / Gini Importance)

Sum of weighted impurity decreases for all splits using that feature across all trees.

**Caveat:** Biased toward high-cardinality features (more split opportunities).

### Method 2: Permutation Importance

Shuffle feature values, measure accuracy drop. Model-agnostic and unbiased.

```python
from sklearn.inspection import permutation_importance

result = permutation_importance(rf, X_test, y_test, n_repeats=10, random_state=42)

# Sort by importance
sorted_idx = result.importances_mean.argsort()[::-1]
for idx in sorted_idx[:10]:
    print(f"{feature_names[idx]}: {result.importances_mean[idx]:.4f} ± {result.importances_std[idx]:.4f}")
```

**Best practice:** Use permutation importance + SHAP for reliable interpretation.

---

## From-Scratch Implementation

```python
import numpy as np
from sklearn.tree import DecisionTreeClassifier

class BaggingClassifierScratch:
    def __init__(self, n_estimators=10, max_samples=1.0):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
    
    def fit(self, X, y):
        self.estimators = []
        n_samples = len(X)
        n_draw = int(n_samples * self.max_samples)
        
        oob_predictions = np.zeros((n_samples, len(np.unique(y))))
        oob_counts = np.zeros(n_samples)
        
        for _ in range(self.n_estimators):
            indices = np.random.choice(n_samples, n_draw, replace=True)
            oob_mask = np.ones(n_samples, dtype=bool)
            oob_mask[indices] = False
            
            tree = DecisionTreeClassifier()
            tree.fit(X[indices], y[indices])
            self.estimators.append(tree)
            
            if oob_mask.any():
                oob_pred = tree.predict_proba(X[oob_mask])
                oob_predictions[oob_mask] += oob_pred
                oob_counts[oob_mask] += 1
        
        valid = oob_counts > 0
        oob_labels = np.argmax(oob_predictions[valid], axis=1)
        self.oob_score_ = np.mean(oob_labels == y[valid])
        return self
    
    def predict(self, X):
        predictions = np.array([est.predict(X) for est in self.estimators])
        return np.apply_along_axis(lambda x: np.bincount(x).argmax(), axis=0, arr=predictions)
```

### Random Forest From Scratch

```python
class RandomForestScratch:
    def __init__(self, n_estimators=100, max_features='sqrt', max_depth=None):
        self.n_estimators = n_estimators
        self.max_features = max_features
        self.max_depth = max_depth
    
    def fit(self, X, y):
        n_samples, n_features = X.shape
        max_feat = int(np.sqrt(n_features)) if self.max_features == 'sqrt' else n_features
        
        self.estimators = []
        self.feature_importances_ = np.zeros(n_features)
        
        for _ in range(self.n_estimators):
            indices = np.random.choice(n_samples, n_samples, replace=True)
            tree = DecisionTreeClassifier(max_depth=self.max_depth, max_features=max_feat)
            tree.fit(X[indices], y[indices])
            self.estimators.append(tree)
            self.feature_importances_ += tree.feature_importances_
        
        self.feature_importances_ /= self.n_estimators
        return self
    
    def predict(self, X):
        predictions = np.array([est.predict(X) for est in self.estimators])
        return np.apply_along_axis(lambda x: np.bincount(x).argmax(), axis=0, arr=predictions)
    
    def permutation_importance(self, X, y, n_repeats=10):
        baseline_acc = np.mean(self.predict(X) == y)
        importances = np.zeros(X.shape[1])
        for feat in range(X.shape[1]):
            drops = []
            for _ in range(n_repeats):
                X_perm = X.copy()
                X_perm[:, feat] = np.random.permutation(X_perm[:, feat])
                drops.append(baseline_acc - np.mean(self.predict(X_perm) == y))
            importances[feat] = np.mean(drops)
        return importances
```

---

## Hyperparameter Guide

| Parameter | Range | Effect |
|-----------|-------|--------|
| `n_estimators` | 100-1000 | More = better, diminishing returns after ~500 |
| `max_depth` | None or 10-30 | None = fully grown trees (high variance per tree, but bagging handles it) |
| `min_samples_split` | 2-20 | Higher = more regularization |
| `max_features` | sqrt(p) clf, p/3 reg | Lower = more diversity, more decorrelation |
| `min_samples_leaf` | 1-10 | Higher = smoother predictions |
| `max_samples` | 0.6-1.0 | Lower = more diversity but less data per tree |

**Tuning priority:** `max_features` > `max_depth` > `min_samples_leaf` > `n_estimators`

---

## When to Use Random Forest

**Use RF when:**
- You need a strong baseline quickly (minimal tuning)
- Interpretability matters (feature importance)
- You want robustness to hyperparameters
- Parallel training is important
- You have noisy data (RF is noise-resistant)

**Don't use RF when:**
- You need absolute best accuracy (boosting often wins)
- Latency is critical (many trees = slow inference)
- Data is very high-dimensional and sparse (linear models may be better)

---

## Common Mistakes

1. **Using too few trees** — always use at least 100; more won't overfit
2. **Not using OOB score** — it's free validation, use it
3. **Trusting MDI importance with high-cardinality features** — use permutation importance
4. **Setting max_depth too low** — RF benefits from deep trees (variance is handled by averaging)

---

## Interview Questions

**Q: Why doesn't Random Forest overfit as you add more trees?**
Each tree is independent. Averaging independent estimates reduces variance without increasing bias. The generalization error converges as M→∞ (Breiman's proof).

**Q: What fraction of data is OOB per tree?**
~36.8% (1 - 1/e). This gives a free validation estimate without needing a holdout set.

**Q: How does feature randomization help beyond just bagging?**
It decorrelates trees. Without it, all trees would split on the same dominant features first, making them correlated. Lower correlation → more variance reduction from averaging.
