# Hyperparameter Tuning

## Overview

Hyperparameters are set before training (not learned from data). Finding good values requires systematic search.

---

## Grid Search

Exhaustive search over all combinations.

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'max_depth': [3, 5, 7, 10],
    'learning_rate': [0.01, 0.05, 0.1, 0.3],
    'n_estimators': [100, 500, 1000]
}
# Total: 4 × 4 × 3 = 48 combinations × 5 folds = 240 fits

grid = GridSearchCV(model, param_grid, cv=5, scoring='roc_auc', n_jobs=-1)
grid.fit(X_train, y_train)
print(f"Best params: {grid.best_params_}")
print(f"Best score: {grid.best_score_:.4f}")
```

**Pros:** Exhaustive, reproducible
**Cons:** Exponential cost (curse of dimensionality), wastes time on unimportant regions

---

## Random Search

Sample random combinations from parameter distributions.

```python
from sklearn.model_selection import RandomizedSearchCV
from scipy.stats import uniform, randint, loguniform

param_dist = {
    'max_depth': randint(3, 15),
    'learning_rate': loguniform(0.01, 0.3),
    'n_estimators': randint(100, 2000),
    'subsample': uniform(0.5, 0.5),
    'colsample_bytree': uniform(0.5, 0.5),
}

random_search = RandomizedSearchCV(
    model, param_dist, n_iter=100, cv=5, scoring='roc_auc', n_jobs=-1
)
random_search.fit(X_train, y_train)
```

**Why random beats grid:** With many parameters, only 1-2 actually matter. Random search explores more values of important params while grid wastes budget on unimportant ones.

```
Grid (4×4=16 trials):        Random (16 trials):
× × × ×                      ×   ×  ×     ×
× × × ×                       × ×    ×  ×
× × × ×                      ×    ×  ×  ×
× × × ×                        ×  ×   × ×

Only 4 unique values          16 unique values for each param!
per dimension                 Better coverage with same budget
```

---

## Bayesian Optimization (Optuna)

Uses past evaluations to model the objective and choose promising next points.

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
        'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 1.0, log=True),
        'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
    }
    
    model = xgb.XGBClassifier(**params, early_stopping_rounds=50, eval_metric='logloss')
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    
    y_pred = model.predict_proba(X_val)[:, 1]
    return roc_auc_score(y_val, y_pred)

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)

print(f"Best AUC: {study.best_value:.4f}")
print(f"Best params: {study.best_params}")
```

### How Many Trials?

```
Rule of thumb:
- 2-3 parameters: 20-50 trials
- 5-8 parameters: 50-200 trials
- 10+ parameters: 200+ trials

Diminishing returns after ~100 trials for most problems.
Use early stopping within Optuna: prune unpromising trials.
```

### Optuna with Pruning

```python
def objective(trial):
    params = {...}
    
    model = xgb.XGBClassifier(**params, n_estimators=1000)
    
    # Pruning callback - stop early if trial is unpromising
    pruning_callback = optuna.integration.XGBoostPruningCallback(trial, 'validation-logloss')
    
    model.fit(X_train, y_train, 
              eval_set=[(X_val, y_val)],
              callbacks=[pruning_callback],
              verbose=False)
    
    return model.best_score

study = optuna.create_study(direction='minimize',
                            pruner=optuna.pruners.MedianPruner())
study.optimize(objective, n_trials=200)
```

---

## Comparison

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| Grid | Exhaustive, reproducible | Exponential cost | Few params, small ranges |
| Random | Better coverage, any budget | May miss narrow optima | Many params, limited budget |
| Bayesian | Most sample-efficient | Setup complexity, sequential | Expensive models |
| Successive Halving | Fast elimination | May discard good configs early | Large search spaces |

---

## Early Stopping

Stop training when validation metric stops improving — avoids overfitting and finds optimal n_estimators automatically.

```python
model = xgb.XGBClassifier(
    n_estimators=5000,  # Set high
    learning_rate=0.05,
    early_stopping_rounds=50,  # Stop if no improvement for 50 rounds
    eval_metric='logloss'
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=100)
print(f"Best iteration: {model.best_iteration}")
```

---

## Learning Curves and Validation Curves

### Learning Curve: Score vs Training Set Size

```python
from sklearn.model_selection import learning_curve

train_sizes, train_scores, val_scores = learning_curve(
    model, X, y, train_sizes=np.linspace(0.1, 1.0, 10),
    cv=5, scoring='accuracy'
)

# Diagnose:
# - Both low → high bias (underfitting)
# - Large gap → high variance (overfitting)
# - Both converge high → good fit
```

### Validation Curve: Score vs Hyperparameter

```python
from sklearn.model_selection import validation_curve

param_range = [1, 2, 3, 5, 7, 10, 15, 20]
train_scores, val_scores = validation_curve(
    model, X, y, param_name='max_depth', param_range=param_range,
    cv=5, scoring='accuracy'
)

# Find max_depth where val score peaks (before overfitting)
```

---

## Practical Tuning Workflow

```
Step 1: Establish baseline
  - Default parameters, measure CV score

Step 2: Fix n_estimators with early stopping
  - Set lr=0.1, n_estimators=5000, early_stopping_rounds=50
  - This determines roughly how many trees you need

Step 3: Tune tree structure (most impactful)
  - max_depth: 3-10
  - min_child_weight (XGB) / min_child_samples (LGB): 1-100

Step 4: Tune sampling (regularization)
  - subsample: 0.6-1.0
  - colsample_bytree: 0.6-1.0

Step 5: Tune regularization
  - reg_alpha, reg_lambda: 0-10

Step 6: Lower learning rate, increase trees
  - lr=0.01-0.05, let early stopping find n_estimators

Step 7: Final evaluation on test set
```

---

## From-Scratch Grid Search

```python
import numpy as np
from itertools import product

class GridSearchCVScratch:
    def __init__(self, estimator, param_grid, cv=5):
        self.estimator = estimator
        self.param_grid = param_grid
        self.cv = cv
    
    def fit(self, X, y):
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        combinations = list(product(*values))
        
        best_score = -np.inf
        self.cv_results_ = []
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            scores = []
            
            kf = StratifiedKFold(n_splits=self.cv, shuffle=True, random_state=42)
            for train_idx, val_idx in kf.split(X, y):
                model = type(self.estimator)(**params)
                model.fit(X[train_idx], y[train_idx])
                scores.append(np.mean(model.predict(X[val_idx]) == y[val_idx]))
            
            mean_score = np.mean(scores)
            self.cv_results_.append({'params': params, 'mean_score': mean_score})
            
            if mean_score > best_score:
                best_score = mean_score
                self.best_params_ = params
                self.best_score_ = best_score
        
        self.best_estimator_ = type(self.estimator)(**self.best_params_)
        self.best_estimator_.fit(X, y)
        return self
```

---

## Common Mistakes

1. **Tuning on test set** — test set becomes validation set, no unbiased estimate remains
2. **Too many grid points** — exponential explosion; use random or Bayesian instead
3. **Not using early stopping with boosting** — wastes time and risks overfitting
4. **Tuning everything simultaneously** — tune in stages (structure → sampling → regularization)
5. **Not setting random_state** — results not reproducible

---

## Interview Questions

**Q: Why is random search often better than grid search?**
With many params, only 1-2 matter. Grid search evaluates the same 4 values of an important param regardless of other params. Random search evaluates n_trials unique values of each param — much better coverage.

**Q: How does Bayesian optimization work?**
It builds a surrogate model (e.g., Gaussian Process or TPE) of the objective function from past evaluations. It uses an acquisition function (e.g., Expected Improvement) to decide which point to try next — balancing exploration and exploitation.

**Q: How do you know when to stop tuning?**
Diminishing returns: if last 20 trials haven't improved by >0.1% on CV score, stop. Also consider: time budget, importance of marginal gain, and whether the improvement is statistically significant.
