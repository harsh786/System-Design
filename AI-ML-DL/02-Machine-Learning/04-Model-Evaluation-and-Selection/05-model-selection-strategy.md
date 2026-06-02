# Model Selection Strategy

## How to Pick the Final Model

Model selection isn't just "pick the highest accuracy." Consider statistical significance, complexity, and deployment constraints.

---

## Statistical Comparison of Models

### Don't Just Compare Point Estimates!

```
Model A: AUC = 0.92 ± 0.03 (from 5-fold CV)
Model B: AUC = 0.89 ± 0.04

Are they truly different? Maybe not — confidence intervals overlap!
```

### Paired t-test on CV Scores

```python
from scipy import stats

scores_A = cross_val_score(model_A, X, y, cv=10, scoring='roc_auc')
scores_B = cross_val_score(model_B, X, y, cv=10, scoring='roc_auc')

t_stat, p_value = stats.ttest_rel(scores_A, scores_B)
print(f"t={t_stat:.3f}, p={p_value:.4f}")
if p_value < 0.05:
    print("Statistically significant difference")
else:
    print("No significant difference — pick simpler model")
```

### Wilcoxon Signed-Rank Test

Non-parametric alternative (no normality assumption):

```python
stat, p_value = stats.wilcoxon(scores_A, scores_B)
```

### McNemar's Test (Comparing Classifiers)

```
              Model B
           Correct  Wrong
Model A  ┌────────┬───────┐
Correct  │  n₀₀   │  n₀₁  │
Wrong    │  n₁₀   │  n₁₁  │
         └────────┴───────┘

χ² = (|n₀₁ - n₁₀| - 1)² / (n₀₁ + n₁₀)

Tests whether models make different types of errors.
```

---

## Bias-Variance Tradeoff Visualization

```
Error
  │
  │╲  Training error
  │ ╲───────────────────────── (increases with data/regularization)
  │                      ╱─── Validation error
  │                   ╱──     (decreases then increases)
  │                ╱──
  │             ╱──
  │──────────╱──
  │
  └────────────────────────── Model Complexity
  
  Underfitting │ Sweet Spot │ Overfitting
```

### Diagnosing from Train/Val Gap

| Pattern | Diagnosis | Action |
|---------|-----------|--------|
| Train high, Val high, small gap | High bias (underfitting) | More features, complex model |
| Train low, Val high, large gap | High variance (overfitting) | More data, regularize, simplify |
| Both low, small gap | Good fit | Ship it |
| Train perfect (0 error) | Likely memorizing | Always suspicious |

---

## Model Complexity vs Performance

### Occam's Razor for ML

> Among models with similar performance, prefer the simpler one.

**Why simpler is better:**
- Generalizes more reliably to new data
- Faster inference in production
- Easier to debug and maintain
- Less likely to exploit data artifacts
- More robust to distribution shifts

### Practical Rule

```
If Model B is 0.3% better than Model A, but:
- Model B is 10x slower
- Model B has 50 hyperparameters (vs 3)
- Model B requires a GPU

→ Choose Model A unless that 0.3% has massive business impact.
```

---

## Deployment Constraints

### Latency

```
Model            Inference Time    Accuracy
Logistic Reg     ~0.01ms           85%
Random Forest    ~1ms              91%
XGBoost          ~0.5ms            93%
Deep Ensemble    ~50ms             94%

If latency budget = 5ms: XGBoost is best choice.
If latency budget = 0.1ms: Logistic Regression only option.
```

### Memory

```
Model            Size (typical)
Linear model     ~KB
Single tree      ~KB-MB
Random Forest    ~10-100MB (many trees)
XGBoost          ~1-50MB
Neural Network   ~10MB-10GB
```

### Other Constraints

- **Interpretability:** Regulated industries (finance, healthcare) may require explainable models
- **Update frequency:** Models needing daily retraining must be fast to train
- **Edge deployment:** Mobile/IoT limits model size and compute

---

## Complete Model Selection Workflow

```
1. Define success criteria
   - Minimum metric threshold (e.g., AUC > 0.85)
   - Latency budget (e.g., < 10ms p99)
   - Interpretability requirements

2. Train candidate models (3-5 diverse approaches)
   - Linear baseline (logistic regression / ridge)
   - Tree-based (random forest, XGBoost)
   - Optional: neural network, SVM

3. Tune each independently
   - Use Optuna with 50-100 trials each
   - Use proper CV (stratified, grouped, etc.)

4. Compare statistically
   - Paired t-test or Wilcoxon on CV scores
   - If no significant difference → pick simpler model

5. Check deployment constraints
   - Measure inference latency
   - Measure model size
   - Verify interpretability needs are met

6. Final evaluation on test set
   - Report with confidence intervals
   - Compare against business threshold
   - If multiple models pass: pick simplest

7. Document decision
   - Why this model over alternatives
   - Known limitations
   - Expected failure modes
```

---

## Practical Model Selection Code

```python
import numpy as np
from scipy import stats
from sklearn.model_selection import cross_val_score, RepeatedStratifiedKFold

# Robust comparison with repeated CV
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=42)

models = {
    'Logistic': LogisticRegression(),
    'RF': RandomForestClassifier(n_estimators=200),
    'XGBoost': XGBClassifier(n_estimators=200, learning_rate=0.1),
}

results = {}
for name, model in models.items():
    scores = cross_val_score(model, X, y, cv=cv, scoring='roc_auc')
    results[name] = scores
    print(f"{name}: {scores.mean():.4f} ± {scores.std():.4f}")

# Pairwise comparison
for name_a, name_b in [('RF', 'XGBoost'), ('Logistic', 'XGBoost')]:
    t, p = stats.ttest_rel(results[name_a], results[name_b])
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
    print(f"{name_a} vs {name_b}: p={p:.4f} {sig}")
```

---

## Common Mistakes

1. **Choosing based on single CV score without significance testing** — noise in estimates!
2. **Ignoring practical constraints** — the "best" model useless if too slow to serve
3. **Over-optimizing** — 0.1% accuracy gain rarely worth 10x complexity
4. **Not establishing a baseline** — always start with simple model to understand problem difficulty
5. **Choosing model before understanding data** — EDA and feature engineering matter more than model choice

---

## Interview Questions

**Q: How do you decide between two models with similar performance?**
1. Statistical test (paired t-test on CV scores) — if not significant, they're equivalent
2. Pick simpler model (fewer params, faster inference, easier to maintain)
3. Consider production requirements (latency, memory, interpretability)
4. Consider robustness (which degrades more gracefully with distribution shift?)

**Q: What is the bias-variance tradeoff in model selection?**
Simple models: high bias (underfit), low variance (stable). Complex models: low bias (fit well), high variance (overfit). Goal: find complexity level that minimizes total error = bias² + variance.

**Q: How do you justify model choice to stakeholders?**
1. Show baseline comparison (improvement over naive)
2. Show statistical significance
3. Show business metric impact (not just accuracy)
4. Address constraints (latency, interpretability)
5. Show failure analysis (what types of errors remain?)
