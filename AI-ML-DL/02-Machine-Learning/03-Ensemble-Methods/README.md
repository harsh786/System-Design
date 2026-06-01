# Ensemble Methods - Complete Guide

## Why Ensembles Work

### The Wisdom of Crowds
Combining multiple diverse models reduces error. Mathematically, if we have M models each with error rate ε < 0.5, and they make independent errors, majority vote error:

```
P(ensemble wrong) = Σ_{k=⌈M/2⌉}^{M} C(M,k) · εᵏ · (1-ε)^(M-k)

Example: M=25 models, each 35% error rate
P(majority wrong) ≈ 6%  (dramatic improvement!)
```

### Bias-Variance Decomposition for Ensembles

```
Single Model:     Error = Bias² + Variance + Noise
Bagging (avg):    Error = Bias² + Variance/M + Noise    (reduces variance)
Boosting (seq):   Error ≈ 0   + Variance + Noise       (reduces bias)

                    Bias²        Variance
                  ┌─────────┬─────────────┐
Single Tree:      │█████    │█████████████│  High var, low bias
Random Forest:    │█████    │████         │  Same bias, lower var
Boosted Trees:    │██       │██████       │  Lower bias, some var
                  └─────────┴─────────────┘
```

---

## 1. Bagging (Bootstrap Aggregating)

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

### Bootstrap Sampling
```
Original: [1, 2, 3, 4, 5, 6, 7, 8]

Bootstrap 1: [2, 5, 5, 1, 8, 3, 1, 7]  ← with replacement
Bootstrap 2: [3, 1, 6, 6, 4, 8, 2, 2]
Bootstrap 3: [7, 4, 1, 5, 3, 3, 8, 6]

Each sample contains ~63.2% unique items (1 - 1/e)
Remaining ~36.8% = Out-of-Bag (OOB) samples → free validation!
```

### Random Forest

Random Forest = Bagging + Random Feature Subsets

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

### Feature Importance in Random Forest
```python
# Method 1: Mean Decrease in Impurity (MDI)
# Sum of impurity decreases for all splits using that feature, weighted by samples

# Method 2: Permutation Importance
# Shuffle feature values, measure accuracy drop
from sklearn.inspection import permutation_importance
result = permutation_importance(rf, X_test, y_test, n_repeats=10)
```

---

## 2. Boosting

### Core Idea
Sequentially train weak learners, each focusing on mistakes of previous ones.

```
Boosting Process:
─────────────────
Round 1:  Train h₁ on original data
          Find misclassified points
Round 2:  Train h₂ with more weight on mistakes of h₁
          Find misclassified points
Round 3:  Train h₃ with more weight on mistakes of h₁+h₂
...
Final:    F(x) = Σ αₘ · hₘ(x)  (weighted combination)
```

### AdaBoost (Adaptive Boosting)

```
AdaBoost Algorithm:
───────────────────
Initialize: wᵢ = 1/n for all samples

For m = 1 to M:
    1. Train weak learner hₘ on weighted data
    2. Compute weighted error: εₘ = Σ wᵢ · I(hₘ(xᵢ) ≠ yᵢ) / Σ wᵢ
    3. Compute learner weight: αₘ = 0.5 · ln((1-εₘ)/εₘ)
    4. Update sample weights:
       wᵢ ← wᵢ · exp(-αₘ · yᵢ · hₘ(xᵢ))
       Normalize: wᵢ ← wᵢ / Σ wᵢ

Final: F(x) = sign(Σₘ αₘ · hₘ(x))
```

```
Weight visualization:

Round 1:  ○ ○ ○ ● ○ ○ ● ○    (equal weights)
          ↓ misclassified: ● at pos 4,7

Round 2:  ○ ○ ○ ◉ ○ ○ ◉ ○    (● get larger weights)
          ↓ misclassified: ○ at pos 2,5

Round 3:  ○ ◎ ○ ● ◎ ○ ● ○    (new mistakes get weight)
```

### Gradient Boosting

```
Key Insight: Instead of reweighting, fit each new model to the RESIDUALS
(negative gradient of the loss function)

Algorithm:
──────────
F₀(x) = argmin_γ Σ L(yᵢ, γ)           (initialize with constant)

For m = 1 to M:
    1. Compute pseudo-residuals:
       rᵢₘ = -∂L(yᵢ, F_{m-1}(xᵢ))/∂F_{m-1}(xᵢ)
       
       For MSE: rᵢₘ = yᵢ - F_{m-1}(xᵢ)  (actual residuals!)
       
    2. Fit weak learner hₘ to residuals: hₘ ← fit(X, r)
    3. Update: Fₘ(x) = F_{m-1}(x) + η · hₘ(x)
       
       η = learning rate (shrinkage), typically 0.01-0.3

Final: F(x) = F₀(x) + η·h₁(x) + η·h₂(x) + ... + η·hₘ(x)
```

### XGBoost (eXtreme Gradient Boosting)

Key innovations over vanilla Gradient Boosting:

```
1. Regularized objective:
   Obj = Σ L(yᵢ, ŷᵢ) + Σₘ Ω(fₘ)
   where Ω(f) = γT + (1/2)λ||w||²
   T = number of leaves, w = leaf weights

2. Second-order Taylor approximation:
   Obj ≈ Σ [gᵢfₘ(xᵢ) + (1/2)hᵢfₘ²(xᵢ)] + Ω(fₘ)
   where gᵢ = ∂L/∂ŷ (gradient), hᵢ = ∂²L/∂ŷ² (Hessian)

3. Optimal leaf weight: w*ⱼ = -Σ_{i∈Iⱼ} gᵢ / (Σ_{i∈Iⱼ} hᵢ + λ)

4. Split gain: Gain = (1/2)[G²_L/(H_L+λ) + G²_R/(H_R+λ) - (G_L+G_R)²/(H_L+H_R+λ)] - γ

5. System optimizations:
   - Column block for parallel split finding
   - Cache-aware access
   - Sparsity-aware (handles missing values)
   - Out-of-core computation
```

### LightGBM

```
Key innovations:
1. Leaf-wise tree growth (vs level-wise in XGBoost)
   
   Level-wise (XGBoost):      Leaf-wise (LightGBM):
        ○                            ○
       / \                          / \
      ○   ○                        ○   ○
     / \ / \                      / \
    ○  ○ ○  ○                    ○   ○
                                    / \
   Balanced but wasteful          ○   ○
                                  
   Grows deepest where most gain

2. Gradient-based One-Side Sampling (GOSS):
   Keep all large-gradient samples, randomly sample small-gradient ones

3. Exclusive Feature Bundling (EFB):
   Bundle mutually exclusive features (sparse) → fewer features

4. Histogram-based splitting: bin continuous values → faster
```

### CatBoost

```
Key innovations:
1. Ordered Target Statistics for categorical features:
   - Avoids target leakage with time-based ordering
   
2. Ordered Boosting:
   - Different permutations for residual calculation
   - Reduces prediction shift (overfitting on training residuals)

3. Symmetric trees: all nodes at same level use same split
   → Faster inference, better CPU cache utilization
```

---

## 3. Stacking (Stacked Generalization)

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

IMPORTANT: Use cross-validated predictions from base learners
to train meta-learner (avoid overfitting!)
```

### Python Implementation
```python
from sklearn.model_selection import cross_val_predict

# Level 0: Generate meta-features using CV predictions
meta_features = np.column_stack([
    cross_val_predict(rf, X_train, y_train, cv=5, method='predict_proba')[:, 1],
    cross_val_predict(svm, X_train, y_train, cv=5, method='decision_function'),
    cross_val_predict(xgb, X_train, y_train, cv=5, method='predict_proba')[:, 1],
])

# Level 1: Train meta-learner
meta_learner = LogisticRegression()
meta_learner.fit(meta_features, y_train)
```

---

## 4. Comparison Table

| Method | Bagging | Boosting | Stacking |
|--------|---------|----------|----------|
| Combines | Parallel | Sequential | Layered |
| Reduces | Variance | Bias | Both |
| Base learners | Strong (deep trees) | Weak (stumps) | Diverse |
| Overfitting risk | Low | Medium-High | High (need CV) |
| Parallelizable | Yes | No | Level 0: Yes |
| Example | Random Forest | XGBoost | RF+SVM+XGB→LR |

### XGBoost vs LightGBM vs CatBoost

| Feature | XGBoost | LightGBM | CatBoost |
|---------|---------|----------|----------|
| Tree growth | Level-wise | Leaf-wise | Symmetric |
| Speed | Medium | Fastest | Medium |
| Categorical | Manual encoding | Direct support | Best native |
| Missing values | Built-in | Built-in | Built-in |
| GPU support | Yes | Yes | Yes |
| Best for | General | Large data | Categorical-heavy |
| Default perf | Good | Good | Often best OOB |

---

## 5. Hyperparameter Tuning

### Key Parameters

```
Random Forest:
- n_estimators: 100-1000 (more = better, diminishing returns)
- max_depth: None or 10-30
- min_samples_split: 2-20
- max_features: sqrt(p) for clf, p/3 for reg

XGBoost/LightGBM:
- n_estimators: 100-5000 (with early stopping)
- learning_rate: 0.01-0.3 (lower = more trees needed)
- max_depth: 3-10 (XGB), -1 for LightGBM
- subsample: 0.6-1.0
- colsample_bytree: 0.6-1.0
- min_child_weight: 1-10
- reg_alpha (L1): 0-1
- reg_lambda (L2): 0-1
```

### Tuning Strategy
```python
import optuna

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 2000),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
    }
    
    model = xgb.XGBClassifier(**params, early_stopping_rounds=50)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model.best_score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)
```

---

## Interview Questions

**Q: Why does Random Forest not overfit as you add more trees?**
Each tree is independent, and averaging independent estimates reduces variance without increasing bias. The generalization error converges as M→∞ (Breiman's proof).

**Q: Can Gradient Boosting overfit?**
Yes! Unlike bagging, boosting can overfit with too many iterations. Use early stopping, learning rate shrinkage, and regularization.

**Q: XGBoost vs Random Forest - when to use which?**
- RF: Less tuning needed, parallel training, robust baseline
- XGBoost: Usually better accuracy with tuning, handles imbalanced data better, more control over optimization

**Q: What makes a good base learner for stacking?**
Diversity! Combine models with different inductive biases (tree-based + linear + instance-based). Highly correlated models add little value.

**Q: How does the learning rate interact with n_estimators in boosting?**
Lower learning rate needs more estimators. The combination lr×n_estimators roughly determines model capacity. Use early stopping to find optimal n_estimators for a given learning rate.
