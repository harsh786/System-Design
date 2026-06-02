# Ensemble Training Guide

A practical guide for building, training, and deploying ensemble models.

---

## How to Choose Base Models

### Diversity > Individual Accuracy

The #1 principle: **diverse models that make different errors** beat a collection of strong but similar models.

```
Correlation between model errors determines ensemble benefit:

High correlation (ρ→1):   Ensemble ≈ single model (no benefit)
Low correlation (ρ→0):    Ensemble variance → σ²/M (maximum benefit)

Diversity sources:
├── Different algorithms (tree vs linear vs distance-based)
├── Different feature subsets
├── Different hyperparameters (shallow vs deep trees)
├── Different preprocessing (raw vs PCA vs embeddings)
└── Different training data subsets
```

### Model Selection Strategy

```
For tabular data, good starting ensemble:
1. XGBoost or LightGBM (captures non-linear patterns)
2. Random Forest or ExtraTrees (different tree-building strategy)
3. Linear model (Ridge/Logistic - captures linear signal)
4. KNN or SVM (distance-based, different inductive bias)
5. (Optional) Neural Network (different optimization landscape)

For each model: tune individually FIRST, then combine.
```

### Checking Diversity

```python
import numpy as np
from sklearn.metrics import cohen_kappa_score

# Measure pairwise agreement between models
predictions = [model.predict(X_val) for model in models]
n_models = len(predictions)

print("Pairwise Kappa (lower = more diverse):")
for i in range(n_models):
    for j in range(i+1, n_models):
        kappa = cohen_kappa_score(predictions[i], predictions[j])
        print(f"  Model {i} vs {j}: {kappa:.3f}")
```

---

## Cross-Validation for Stacking (Avoid Leakage!)

### The Leakage Problem

```
WRONG (leaky):
1. Train base models on X_train
2. base_preds = base_models.predict(X_train)  ← LEAKAGE! Overfit predictions
3. meta_learner.fit(base_preds, y_train)      ← Learns from leaked signal

RIGHT (clean):
1. For each fold k:
   a. Train base models on folds ≠ k
   b. Predict on fold k → OOF predictions
2. meta_learner.fit(OOF_predictions, y_train)  ← Clean signal
3. Retrain base models on ALL training data for test inference
```

### Implementation Pattern

```python
from sklearn.model_selection import StratifiedKFold
import numpy as np

def generate_oof_predictions(models, X, y, n_folds=5):
    """Generate leak-free out-of-fold predictions for stacking."""
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    oof_preds = np.zeros((len(X), len(models)))
    
    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_fold_train, X_fold_val = X[train_idx], X[val_idx]
        y_fold_train = y[train_idx]
        
        for model_idx, model in enumerate(models):
            clone = type(model)(**model.get_params())
            clone.fit(X_fold_train, y_fold_train)
            oof_preds[val_idx, model_idx] = clone.predict_proba(X_fold_val)[:, 1]
    
    return oof_preds
```

### Common CV Mistakes in Ensembles

1. **Preprocessing before split** — fit scaler on ALL data, then split → leakage
2. **Target encoding without CV** — encode using full target → leakage  
3. **Feature selection using all data** — select features, then CV → optimistic
4. **Using same CV folds for tuning and OOF generation** — less of an issue but not ideal

---

## Hyperparameter Tuning Strategies for Ensembles

### Strategy 1: Tune Individually, Then Combine

```
Step 1: Tune each base model independently (Optuna, 50-100 trials each)
Step 2: Generate OOF predictions with tuned base models
Step 3: Train simple meta-learner (no tuning needed for Ridge/LR)
Step 4: Evaluate full stack on holdout
```

### Strategy 2: Joint Optimization (Advanced)

```python
import optuna

def objective(trial):
    # Tune ensemble composition and weights
    use_rf = trial.suggest_categorical('use_rf', [True, False])
    use_xgb = trial.suggest_categorical('use_xgb', [True, False])
    use_lgb = trial.suggest_categorical('use_lgb', [True, False])
    
    models = []
    if use_rf:
        models.append(RandomForestClassifier(
            n_estimators=trial.suggest_int('rf_n', 100, 500),
            max_depth=trial.suggest_int('rf_depth', 5, 20)
        ))
    if use_xgb:
        models.append(XGBClassifier(
            learning_rate=trial.suggest_float('xgb_lr', 0.01, 0.3, log=True),
            max_depth=trial.suggest_int('xgb_depth', 3, 8)
        ))
    # ... etc
    
    if len(models) < 2:
        return 0  # Need at least 2 models
    
    oof = generate_oof_predictions(models, X_train, y_train)
    meta = LogisticRegression().fit(oof, y_train)
    # Evaluate with nested CV or holdout
    return roc_auc_score(y_val, meta.predict_proba(test_oof)[:, 1])
```

### Strategy 3: Simple Weighted Average (Baseline)

```python
from scipy.optimize import minimize

def find_optimal_weights(predictions, y_true):
    """Find weights that minimize log-loss."""
    def loss(weights):
        weights = np.abs(weights) / np.abs(weights).sum()  # normalize
        blended = np.average(predictions, axis=0, weights=weights)
        return log_loss(y_true, blended)
    
    n_models = len(predictions)
    result = minimize(loss, x0=np.ones(n_models)/n_models, method='Nelder-Mead')
    weights = np.abs(result.x) / np.abs(result.x).sum()
    return weights
```

---

## When Ensembles DON'T Help

### 1. Already Good Single Model

If your best single model has 0.95 AUC and the ensemble gets 0.955, the added complexity may not be worth it. Cost-benefit analysis:
- +0.5% accuracy vs. 5x inference latency + maintenance complexity

### 2. Latency Constraints

```
Single XGBoost:     ~1ms inference
5-model ensemble:   ~5ms inference (parallel) or ~5ms (sequential)
Stacked ensemble:   ~6ms (base models + meta-learner)

Real-time serving (< 10ms budget): Single model or simple average
Batch predictions: Ensembles fine
```

### 3. Small Dataset

With < 1000 samples, meta-learner training data (OOF predictions) is tiny → overfits. Simple averaging or voting is safer.

### 4. Highly Correlated Models

If all models make the same errors, combining them adds complexity without improvement. Check pairwise prediction correlation first.

### 5. Interpretability Required

Stacked ensembles are black boxes. If you need to explain individual predictions (healthcare, finance, legal), stick with a single interpretable model.

---

## Production Ensembles

### Latency Budget Management

```
Strategy 1: Parallel inference
- Run all base models simultaneously
- Total latency = max(individual latencies)
- Requires more compute resources

Strategy 2: Cascading
- Start with fast model
- Only run expensive models if uncertain
- Most predictions use just the fast model

Strategy 3: Model distillation
- Train ensemble offline
- Distill ensemble knowledge into single fast model
- Deploy only the student model
```

### Knowledge Distillation

```python
# Train ensemble (teacher)
ensemble_probs = ensemble.predict_proba(X_train)  # soft labels

# Train single model (student) on soft labels
from sklearn.neural_network import MLPClassifier

student = MLPClassifier(hidden_layer_sizes=(100, 50))
# Use soft labels (probabilities) instead of hard labels
student.fit(X_train, ensemble_probs)  # or use temperature-scaled softmax

# Deploy only the student
# Gets ~90% of ensemble benefit with single-model latency
```

### Production Monitoring

```
Monitor each base model independently:
├── Individual model accuracy drift
├── Disagreement rate between models (sudden increase = distribution shift)
├── Inference latency per model
└── Feature pipeline health per model

Alert triggers:
- Base model accuracy drops below threshold
- Ensemble disagreement spikes (models no longer agree)
- Any base model latency exceeds SLA
```

### Versioning and Updates

```
Challenge: Updating one base model changes meta-learner input distribution

Solutions:
1. Update all models together (expensive but clean)
2. Retrain meta-learner when any base model changes
3. Use simple averaging (robust to individual model updates)
4. Shadow deployment: run new model alongside, compare before switching
```

---

## Decision Framework

```
Should I use an ensemble?

Q: Is this a competition or production?
├── Competition → Yes, always ensemble (stacking)
└── Production → Continue below

Q: Does a single model meet requirements?
├── Yes → Don't ensemble (simplicity wins)
└── No → Continue below

Q: Is latency a hard constraint?
├── Yes (< 10ms) → Use distillation or simple average of 2-3 models
└── No → Continue below

Q: Do I have diverse models with different error patterns?
├── Yes → Stack or average them
└── No → Focus on improving the single model first
```

---

## Common Mistakes

1. **Ensembling without diversity** — 5 copies of XGBoost ≈ 1 XGBoost
2. **Spending all time on ensembling, not enough on feature engineering** — features matter more than stacking tricks
3. **Not monitoring individual model health in production** — one bad model can poison the ensemble
4. **Over-engineering the meta-learner** — Logistic Regression is almost always sufficient
5. **Ignoring the data pipeline complexity** — each model may need different preprocessing

---

## Interview Questions

**Q: How do you choose base models for an ensemble?**
Maximize diversity: different algorithms (tree + linear + instance-based), different feature subsets, different hyperparameters. Measure diversity via prediction correlation or Kappa scores. A weak but diverse model adds more value than another strong but correlated model.

**Q: How do you deploy an ensemble in production with strict latency requirements?**
Options: (1) Parallel inference if resources available, (2) Knowledge distillation to single model, (3) Cascading where fast model handles easy cases, (4) Simple average of 2-3 fast models. Always measure latency vs accuracy tradeoff.

**Q: When should you NOT use an ensemble?**
When single model meets requirements, when latency is critical, when interpretability is required, when dataset is too small for stacking, or when all candidate models make the same errors (no diversity benefit).
