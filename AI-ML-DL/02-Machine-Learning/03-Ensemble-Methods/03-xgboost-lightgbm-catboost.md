# XGBoost, LightGBM, and CatBoost

## XGBoost (eXtreme Gradient Boosting)

### Key Innovations

```
1. Regularized objective:
   Obj = Σ L(yᵢ, ŷᵢ) + Σₘ Ω(fₘ)
   where Ω(f) = γT + (1/2)λ||w||²
   T = number of leaves, w = leaf weights

2. Second-order Taylor approximation:
   Obj ≈ Σ [gᵢfₘ(xᵢ) + (1/2)hᵢfₘ²(xᵢ)] + Ω(fₘ)
   where gᵢ = ∂L/∂ŷ (gradient), hᵢ = ∂²L/∂ŷ² (Hessian)

3. Optimal leaf weight: w*ⱼ = -Σ_{i∈Iⱼ} gᵢ / (Σ_{i∈Iⱼ} hᵢ + λ)

4. Split gain: 
   Gain = (1/2)[G²_L/(H_L+λ) + G²_R/(H_R+λ) - (G_L+G_R)²/(H_L+H_R+λ)] - γ

5. System optimizations:
   - Column block for parallel split finding
   - Cache-aware access
   - Sparsity-aware (handles missing values natively)
   - Out-of-core computation for large datasets
```

### Regularization Parameters

- **γ (gamma):** Minimum split gain. Higher → fewer splits, simpler trees (pruning)
- **λ (reg_lambda):** L2 on leaf weights. Higher → more conservative predictions
- **α (reg_alpha):** L1 on leaf weights. Encourages sparsity in leaf values

### Handling Missing Values

XGBoost learns the optimal direction for missing values during training. At each split, it tries sending missing values both left and right, picks the direction with higher gain.

### Code Example

```python
import xgboost as xgb
from sklearn.model_selection import train_test_split

X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2)

model = xgb.XGBClassifier(
    n_estimators=1000,
    learning_rate=0.05,
    max_depth=6,
    min_child_weight=3,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    eval_metric='logloss',
    early_stopping_rounds=50,
    random_state=42
)

model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)
print(f"Best iteration: {model.best_iteration}")
```

---

## LightGBM

### Key Innovations

```
1. Leaf-wise tree growth (vs level-wise in XGBoost)
   
   Level-wise (XGBoost):      Leaf-wise (LightGBM):
        ○                            ○
       / \                          / \
      ○   ○                        ○   ○
     / \ / \                      / \
    ○  ○ ○  ○                    ○   ○
                                    / \
   Balanced but wasteful          ○   ○
                                  
   Grows deepest where most gain → faster convergence

2. Gradient-based One-Side Sampling (GOSS):
   Keep all large-gradient samples, randomly sample small-gradient ones
   → Fewer samples, preserves information about hard examples

3. Exclusive Feature Bundling (EFB):
   Bundle mutually exclusive features (sparse) → fewer effective features
   → Massive speedup for high-dimensional sparse data

4. Histogram-based splitting: 
   Bin continuous values into 255 bins → O(#bins) vs O(#data) split finding
```

### Why LightGBM is Faster

- Histogram binning: O(data × features) → O(data × bins)
- GOSS: Uses subset of data (all large-gradient + sample of small-gradient)
- EFB: Reduces feature count for sparse data
- Leaf-wise: Fewer splits needed for same accuracy

### Code Example

```python
import lightgbm as lgb

train_data = lgb.Dataset(X_train, label=y_train)
val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

params = {
    'objective': 'binary',
    'metric': 'binary_logloss',
    'learning_rate': 0.05,
    'num_leaves': 31,          # Key param (not max_depth!)
    'max_depth': -1,           # No limit (leaf-wise handles complexity)
    'min_child_samples': 20,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'verbose': -1
}

model = lgb.train(
    params, train_data,
    num_boost_round=1000,
    valid_sets=[val_data],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
)
```

**Important:** LightGBM uses `num_leaves` (not `max_depth`) as primary complexity control. `num_leaves` ≈ 2^max_depth for equivalent complexity.

---

## CatBoost

### Key Innovations

```
1. Ordered Target Statistics for categorical features:
   - Encodes categoricals using target mean, but with time-based ordering
   - Avoids target leakage: for sample i, only uses samples 1...(i-1) for encoding
   
2. Ordered Boosting:
   - Different permutations for residual calculation
   - Reduces prediction shift (overfitting on training residuals)
   - Each tree is built using a different ordering of samples

3. Symmetric trees: all nodes at same level use same split
   → Faster inference, better CPU cache utilization
   → Acts as regularization (less expressive per tree)
```

### Native Categorical Handling

No need for one-hot encoding or manual target encoding. CatBoost handles it properly:

```python
from catboost import CatBoostClassifier

cat_features = ['city', 'device_type', 'browser']  # column names or indices

model = CatBoostClassifier(
    iterations=1000,
    learning_rate=0.05,
    depth=6,
    l2_leaf_reg=3,
    random_seed=42,
    verbose=100,
    early_stopping_rounds=50,
    cat_features=cat_features
)

model.fit(X_train, y_train, eval_set=(X_val, y_val))
```

### Why CatBoost Often Wins Out-of-Box

- Ordered boosting reduces overfitting without explicit regularization tuning
- Proper categorical handling eliminates preprocessing errors
- Symmetric trees provide built-in regularization
- Good defaults — less tuning needed than XGBoost/LightGBM

---

## Comparison Table

| Feature | XGBoost | LightGBM | CatBoost |
|---------|---------|----------|----------|
| Tree growth | Level-wise | Leaf-wise | Symmetric |
| Speed | Medium | **Fastest** | Medium |
| Categorical | Manual encoding | Direct support | **Best native** |
| Missing values | Built-in (learned) | Built-in | Built-in |
| GPU support | Yes | Yes | Yes |
| Default performance | Good | Good | **Often best OOB** |
| Best for | General/competitions | Large data, speed | Categorical-heavy |
| Key complexity param | max_depth | num_leaves | depth |
| Overfitting risk | Medium | Higher (leaf-wise) | Lower (ordered) |
| Distributed training | Yes | Yes | Yes |

### When to Choose Each

- **XGBoost:** General purpose, well-established, good for medium datasets, most tutorials/resources
- **LightGBM:** Large data (>100K rows), need speed, many features, memory-constrained
- **CatBoost:** Many categorical features, want minimal preprocessing, need good defaults without tuning

---

## Hyperparameter Guide

### XGBoost

| Parameter | Range | Priority |
|-----------|-------|----------|
| `learning_rate` | 0.01-0.3 | High |
| `max_depth` | 3-10 | High |
| `n_estimators` | 100-5000 (early stop) | High |
| `min_child_weight` | 1-10 | Medium |
| `subsample` | 0.6-1.0 | Medium |
| `colsample_bytree` | 0.6-1.0 | Medium |
| `reg_lambda` | 0-10 | Low |
| `reg_alpha` | 0-1 | Low |
| `gamma` | 0-5 | Low |

### LightGBM

| Parameter | Range | Priority |
|-----------|-------|----------|
| `learning_rate` | 0.01-0.3 | High |
| `num_leaves` | 15-127 | High |
| `n_estimators` | 100-5000 (early stop) | High |
| `min_child_samples` | 5-100 | Medium |
| `subsample` | 0.6-1.0 | Medium |
| `colsample_bytree` | 0.6-1.0 | Medium |
| `reg_lambda` | 0-10 | Low |
| `reg_alpha` | 0-1 | Low |

### CatBoost

| Parameter | Range | Priority |
|-----------|-------|----------|
| `learning_rate` | 0.01-0.3 | High |
| `depth` | 4-10 | High |
| `iterations` | 100-5000 (early stop) | High |
| `l2_leaf_reg` | 1-10 | Medium |
| `subsample` | 0.6-1.0 | Medium |
| `random_strength` | 0-10 | Low |

---

## Tuning with Optuna

```python
import optuna

def objective(trial):
    params = {
        'n_estimators': 1000,  # Fixed, use early stopping
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 1.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }
    
    model = xgb.XGBClassifier(**params, early_stopping_rounds=50, eval_metric='logloss')
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model.best_score

study = optuna.create_study(direction='minimize')
study.optimize(objective, n_trials=100)
print(f"Best params: {study.best_params}")
```

---

## Common Mistakes

1. **Not using early stopping** — always set it; determines optimal n_estimators automatically
2. **LightGBM: setting max_depth without adjusting num_leaves** — num_leaves is the primary control
3. **CatBoost: one-hot encoding categoricals** — defeats the purpose; pass them directly
4. **XGBoost: ignoring scale_pos_weight for imbalanced data** — set to neg_count/pos_count
5. **All: tuning too many params at once** — follow priority order above

---

## Interview Questions

**Q: Why is LightGBM faster than XGBoost?**
Histogram-based binning (fewer split candidates), GOSS (fewer samples), EFB (fewer features), and leaf-wise growth (fewer total splits for same accuracy).

**Q: How does XGBoost handle missing values?**
At each split, it tries assigning missing values to both left and right child, picks the direction with higher gain. This is learned during training.

**Q: Why does CatBoost use ordered boosting?**
Standard boosting computes residuals using predictions from a model trained on the same data → biased residuals (prediction shift). Ordered boosting uses different sample orderings to compute unbiased residuals.

**Q: XGBoost vs Random Forest - when to use which?**
- RF: Less tuning, parallel training, robust baseline, won't overfit with more trees
- XGBoost: Usually better accuracy with tuning, handles imbalanced data better, more control
