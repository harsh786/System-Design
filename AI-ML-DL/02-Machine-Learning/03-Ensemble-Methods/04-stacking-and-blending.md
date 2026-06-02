# Stacking and Blending

## Stacking (Stacked Generalization)

### Concept

Train multiple diverse base models, then train a **meta-learner** that learns how to optimally combine their predictions.

```
┌─────────────────────────────────────────────────────────┐
│                    STACKING                               │
│                                                          │
│  Level 0 (Base Learners):                               │
│  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐           │
│  │  RF   │  │  SVM  │  │  KNN  │  │  XGB  │           │
│  └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘           │
│      │          │          │          │                  │
│      ▼          ▼          ▼          ▼                  │
│    pred_1    pred_2     pred_3     pred_4               │
│      │          │          │          │                  │
│      └──────────┴──────────┴──────────┘                  │
│                     │                                    │
│                     ▼                                    │
│  Level 1 (Meta-Learner):                               │
│  ┌─────────────────────────────────┐                    │
│  │   Logistic Regression / Ridge   │                    │
│  └────────────────┬────────────────┘                    │
│                   │                                      │
│                   ▼                                      │
│            Final Prediction                              │
└─────────────────────────────────────────────────────────┘
```

### Critical: Use Cross-Validated Predictions!

**WRONG:** Train base models on all training data, predict on same training data → meta-learner sees overfit predictions → data leakage!

**RIGHT:** Use out-of-fold (OOF) predictions to generate meta-features:

```
For each fold:
  1. Train base models on other folds
  2. Predict on held-out fold → these become meta-features
  
Result: Each training sample has OOF predictions (no leakage)
```

---

## Implementation with Cross-Validation

```python
from sklearn.model_selection import cross_val_predict
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
import numpy as np

# Level 0: Generate meta-features using CV predictions
rf = RandomForestClassifier(n_estimators=200)
gb = GradientBoostingClassifier(n_estimators=200)
svc = SVC(probability=True)

meta_features_train = np.column_stack([
    cross_val_predict(rf, X_train, y_train, cv=5, method='predict_proba')[:, 1],
    cross_val_predict(gb, X_train, y_train, cv=5, method='predict_proba')[:, 1],
    cross_val_predict(svc, X_train, y_train, cv=5, method='predict_proba')[:, 1],
])

# Level 1: Train meta-learner on OOF predictions
meta_learner = LogisticRegression()
meta_learner.fit(meta_features_train, y_train)

# For test predictions: retrain base models on ALL training data
rf.fit(X_train, y_train)
gb.fit(X_train, y_train)
svc.fit(X_train, y_train)

meta_features_test = np.column_stack([
    rf.predict_proba(X_test)[:, 1],
    gb.predict_proba(X_test)[:, 1],
    svc.predict_proba(X_test)[:, 1],
])

final_pred = meta_learner.predict(meta_features_test)
```

### sklearn StackingClassifier

```python
from sklearn.ensemble import StackingClassifier

estimators = [
    ('rf', RandomForestClassifier(n_estimators=200)),
    ('gb', GradientBoostingClassifier(n_estimators=200)),
    ('svc', SVC(probability=True)),
]

stack = StackingClassifier(
    estimators=estimators,
    final_estimator=LogisticRegression(),
    cv=5,
    stack_method='predict_proba'
)

stack.fit(X_train, y_train)
print(f"Test accuracy: {stack.score(X_test, y_test):.4f}")
```

---

## Blending (Holdout-Based Stacking)

### Concept

Simpler alternative to stacking: use a holdout set instead of cross-validation.

```
Training data split:
├── Train (70%) → Train base models
└── Blend set (30%) → Generate meta-features

Steps:
1. Train base models on Train portion
2. Predict on Blend set → meta-features
3. Train meta-learner on Blend set predictions
4. For test: base model predictions → meta-learner → final prediction
```

### Blending vs Stacking

| Aspect | Stacking (CV) | Blending (Holdout) |
|--------|---------------|-------------------|
| Data usage | All data for meta-features | Wastes blend set for base training |
| Leakage risk | Low if done properly | Very low (clean separation) |
| Complexity | Higher (K-fold for each base) | Simpler |
| Variance | Lower (averages over folds) | Higher (single split) |
| Best for | Competitions, max performance | Production, simplicity |

---

## When Stacking Helps vs Doesn't

### Stacking HELPS when:
- Base models are **diverse** (different algorithms, different errors)
- Models have complementary strengths on different regions of input space
- Enough data to train meta-learner without overfitting
- Marginal improvement matters (competitions)

### Stacking DOESN'T help when:
- All base models are similar (e.g., 5 XGBoost with different seeds → just average)
- Small dataset (meta-learner overfits)
- Single model already near-perfect
- Latency/complexity constraints in production
- Diminishing returns vs. simple averaging

---

## Practical Tips

### 1. Diversity Matters!

```
Good diversity:                 Poor diversity:
- Random Forest                 - XGBoost seed=1
- XGBoost                       - XGBoost seed=2
- Logistic Regression           - XGBoost seed=3
- KNN                           - XGBoost seed=4
- Neural Network                - XGBoost seed=5

Different inductive biases!     Same algorithm, same biases.
```

### 2. Meta-Learner Should Be Simple

Use Logistic Regression or Ridge — it only needs to learn combination weights. Complex meta-learners overfit to the small meta-feature space.

### 3. Include Original Features?

Sometimes adding original features alongside meta-features helps the meta-learner, especially if base models miss certain patterns. But increases overfitting risk.

### 4. Use Probabilities, Not Labels

Feed predicted probabilities (not hard class labels) as meta-features — preserves confidence information.

### 5. Multi-Level Stacking

Can stack multiple levels, but diminishing returns. 2 levels is usually enough:
- Level 0: Diverse base models
- Level 1: Simple meta-learner

---

## Competition-Winning Stacking Recipes

### Recipe 1: Standard Tabular Competition

```
Level 0 (5+ diverse models):
- XGBoost (depth 6, lr 0.05)
- LightGBM (num_leaves 63, lr 0.05)
- CatBoost (depth 8, lr 0.03)
- ExtraTreesClassifier (500 trees)
- Ridge/LogisticRegression
- KNN (with scaled features)

Level 1:
- Logistic Regression (or simple Ridge)
- Or: Another light XGBoost on meta-features

All base models: 5-fold OOF predictions as meta-features
```

### Recipe 2: Maximum Diversity

```
Level 0:
- 3 XGBoost (different depths: 4, 6, 8)
- 3 LightGBM (different num_leaves: 31, 63, 127)
- 2 CatBoost (different depths)
- 1 Neural Network (2-layer MLP)
- 1 Regularized Linear Model
- Different feature subsets for some models

Level 1:
- Ridge regression on all OOF predictions
```

### Recipe 3: Two-Level Stack

```
Level 0: 10+ models as above
Level 1: 3 models (XGB, Ridge, NN) trained on Level 0 outputs
Level 2: Simple average or weighted average of Level 1
```

---

## From-Scratch Implementation

```python
import numpy as np
from sklearn.model_selection import KFold

class StackingClassifierScratch:
    def __init__(self, base_estimators, meta_estimator, cv=5):
        self.base_estimators = base_estimators
        self.meta_estimator = meta_estimator
        self.cv = cv
    
    def fit(self, X, y):
        n_samples = len(X)
        n_base = len(self.base_estimators)
        meta_features = np.zeros((n_samples, n_base))
        
        kf = KFold(n_splits=self.cv, shuffle=True, random_state=42)
        
        # Generate out-of-fold predictions
        for i, est in enumerate(self.base_estimators):
            for train_idx, val_idx in kf.split(X):
                clone = type(est)(**est.get_params())
                clone.fit(X[train_idx], y[train_idx])
                meta_features[val_idx, i] = clone.predict_proba(X[val_idx])[:, 1]
        
        # Train meta-learner
        self.meta_estimator.fit(meta_features, y)
        
        # Retrain base estimators on full data
        self.fitted_base = []
        for est in self.base_estimators:
            clone = type(est)(**est.get_params())
            clone.fit(X, y)
            self.fitted_base.append(clone)
        
        return self
    
    def predict(self, X):
        meta_features = np.column_stack([
            est.predict_proba(X)[:, 1] for est in self.fitted_base
        ])
        return self.meta_estimator.predict(meta_features)
    
    def predict_proba(self, X):
        meta_features = np.column_stack([
            est.predict_proba(X)[:, 1] for est in self.fitted_base
        ])
        return self.meta_estimator.predict_proba(meta_features)
```

---

## Common Mistakes

1. **Training meta-learner on base model's in-sample predictions** → massive data leakage
2. **Using same algorithm for all base models** → no diversity, stacking won't help
3. **Complex meta-learner** → overfits to few meta-features
4. **Not retraining base models on full data for test predictions** → wastes data
5. **Too many stacking levels** → diminishing returns, increased complexity

---

## Interview Questions

**Q: What makes a good base learner for stacking?**
Diversity! Combine models with different inductive biases (tree-based + linear + instance-based). Highly correlated models add little value. Accuracy matters less than diversity.

**Q: Why must you use CV predictions to train the meta-learner?**
If base models predict on their own training data, predictions are overfit (near-perfect). The meta-learner would learn to trust these overfit predictions → catastrophic leakage.

**Q: When would you use stacking over simple averaging?**
When base models have complementary strengths on different input regions. If models are similar (same algorithm, different seeds), simple averaging works just as well.

**Q: Stacking vs blending?**
Stacking uses all data via CV (better for competitions). Blending uses holdout (simpler, less leakage risk, better for production). On large datasets, difference is minimal.
