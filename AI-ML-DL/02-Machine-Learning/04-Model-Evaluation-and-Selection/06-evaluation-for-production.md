# Evaluation for Production

Real-world evaluation goes far beyond academic metrics. This guide covers what matters when models serve real users.

---

## Offline vs Online Metrics (And Why They Disagree!)

```
┌──────────────────────┬────────────────────────────────────┐
│ Offline Metrics      │ Online Metrics                      │
├──────────────────────┼────────────────────────────────────┤
│ AUC-ROC             │ Click-through rate                  │
│ F1 Score            │ Conversion rate                     │
│ RMSE                │ Revenue per user                    │
│ Precision@K         │ User engagement time                │
│ NDCG                │ Churn rate                          │
│                     │ Latency (p50, p99)                  │
└──────────────────────┴────────────────────────────────────┘
```

### Why They Can Disagree

1. **Distribution shift:** Test set ≠ production data
2. **Feedback loops:** Model predictions change user behavior
3. **Proxy mismatch:** Offline metric doesn't capture business value
4. **Presentation bias:** Users interact with what's shown (not what's best)
5. **Context missing:** Offline eval ignores timing, user mood, competing options

**Rule:** A model with better AUC can have worse business metrics. Always validate with online experiments.

---

## A/B Testing for Model Evaluation

### Design

```python
# Hash-based assignment for consistency
def assign_group(user_id, experiment_name, traffic_pct=0.1):
    hash_val = hash(f"{user_id}_{experiment_name}") % 1000
    if hash_val < traffic_pct * 1000:
        return 'treatment'  # new model
    return 'control'        # current model
```

### Key Principles

1. **Random assignment:** Hash user ID for consistent, reproducible splits
2. **Sufficient sample size:** Power analysis before starting
3. **Minimum duration:** 1-2 weeks (capture weekly patterns)
4. **Guard rails:** Monitor for regressions in critical metrics
5. **Pre-register:** Define primary metric and stopping criteria upfront

### Statistical Rigor

```python
from scipy import stats

# Two-sample t-test for metric comparison
control_metric = [...]  # per-user metric values
treatment_metric = [...]

t_stat, p_value = stats.ttest_ind(treatment_metric, control_metric)
effect_size = np.mean(treatment_metric) - np.mean(control_metric)
relative_lift = effect_size / np.mean(control_metric) * 100

print(f"Lift: {relative_lift:.2f}%, p-value: {p_value:.4f}")
```

### Common Pitfalls

- **Peeking:** Checking results daily inflates false positives → use sequential testing
- **Novelty effect:** Initial spike fades → run long enough
- **Network effects:** User A's experience affects User B → cluster randomization
- **Multiple comparisons:** Testing 10 metrics → Bonferroni correction

---

## Business Metric Alignment

### The Metric Hierarchy

```
Level 1: Business KPI (revenue, retention, engagement)
  ↑ validated by A/B test
Level 2: Online proxy metric (CTR, conversion, time-on-site)  
  ↑ assumed correlation
Level 3: Offline metric (AUC, F1, NDCG)
  ↑ used for model development
Level 4: Training loss (cross-entropy, MSE)

DANGER: Optimizing Level 4 without validating Levels 1-2
```

### Translating Business Goals to Metrics

| Business Goal | Wrong Metric | Right Metric |
|---------------|-------------|--------------|
| "Catch fraud" | Accuracy (99% says "not fraud") | Recall at fixed FPR, or $ saved |
| "Recommend relevant items" | RMSE of ratings | Revenue per recommendation, diversity |
| "Reduce churn" | AUC on churn prediction | # customers saved × LTV |
| "Fast search results" | NDCG | Time-to-answer + user satisfaction |

---

## Fairness Evaluation

### Per-Group Performance

```python
# Check performance across protected groups
groups = ['gender', 'age_group', 'ethnicity']

for group_col in groups:
    print(f"\n--- Performance by {group_col} ---")
    for group_val in df[group_col].unique():
        mask = df[group_col] == group_val
        y_true_g = y_true[mask]
        y_pred_g = y_pred[mask]
        
        print(f"  {group_val}: "
              f"Acc={accuracy_score(y_true_g, y_pred_g):.3f}, "
              f"FPR={fp_rate(y_true_g, y_pred_g):.3f}, "
              f"TPR={recall_score(y_true_g, y_pred_g):.3f}")
```

### Fairness Metrics

| Metric | Definition | Use When |
|--------|-----------|----------|
| Demographic parity | P(ŷ=1\|A=0) = P(ŷ=1\|A=1) | Equal selection rates |
| Equal opportunity | TPR equal across groups | Equal chance of being correctly identified |
| Equalized odds | TPR AND FPR equal across groups | Strictest fairness |
| Calibration | P(Y=1\|ŷ=p, A=a) = p for all a | Probabilities mean same thing for all groups |

### Red Flags

- FPR much higher for one demographic → disproportionate false accusations
- TPR much lower for one group → that group is underserved
- Large performance gap between groups → biased model or data

---

## Calibration

### Are Your Probabilities Trustworthy?

A model that says "70% probability" should be correct 70% of the time.

```python
from sklearn.calibration import calibration_curve, CalibratedClassifierCV

# Check calibration
fraction_positive, mean_predicted = calibration_curve(y_true, y_proba, n_bins=10)

# Plot reliability diagram
plt.plot(mean_predicted, fraction_positive, 's-', label='Model')
plt.plot([0, 1], [0, 1], '--', label='Perfect calibration')
plt.xlabel('Mean predicted probability')
plt.ylabel('Fraction of positives')
```

### Common Calibration Issues

```
Neural networks: overconfident (probabilities too extreme)
Random Forest:   pushed toward 0 and 1 (poor middle-range calibration)
SVM:            doesn't output probabilities naturally
Boosting:       usually decent, but can be overconfident with overfitting
```

### Fixing Calibration

```python
# Method 1: Platt scaling (logistic regression on outputs)
cal_model = CalibratedClassifierCV(model, method='sigmoid', cv=5)
cal_model.fit(X_train, y_train)

# Method 2: Isotonic regression (non-parametric, more flexible)
cal_model = CalibratedClassifierCV(model, method='isotonic', cv=5)

# Method 3: Temperature scaling (neural networks)
# Divide logits by learned temperature T before softmax
```

### Expected Calibration Error (ECE)

```python
def expected_calibration_error(y_true, y_proba, n_bins=10):
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0
    for i in range(n_bins):
        mask = (y_proba >= bin_boundaries[i]) & (y_proba < bin_boundaries[i+1])
        if mask.sum() == 0:
            continue
        bin_accuracy = y_true[mask].mean()
        bin_confidence = y_proba[mask].mean()
        ece += mask.sum() * abs(bin_accuracy - bin_confidence)
    return ece / len(y_true)
```

---

## Error Analysis Workflow

### Step 1: Categorize Errors

```python
# Find errors
errors = X_test[y_pred != y_true]
error_types = y_true[y_pred != y_true]  # FP vs FN

# Analyze error characteristics
print("False Positives characteristics:")
print(errors[error_types == 0].describe())  # FP: predicted 1, actual 0

print("\nFalse Negatives characteristics:")
print(errors[error_types == 1].describe())  # FN: predicted 0, actual 1
```

### Step 2: Find Patterns

```
Questions to answer:
├── Are errors concentrated in specific feature ranges?
├── Are errors correlated with specific subgroups?
├── Are errors near the decision boundary (low confidence)?
├── Are there systematic patterns (always wrong on X type)?
└── Are labels themselves noisy (human annotation errors)?
```

### Step 3: Prioritize Fixes

```
Error Impact Matrix:

              High Frequency    Low Frequency
High Cost:    FIX FIRST         Fix if easy
Low Cost:     Fix next          Ignore
```

### Step 4: Systematic Improvement

```
For each major error category:
1. Can we get more training data of this type?
2. Can we add features that distinguish this case?
3. Can we use a specialist model for this subgroup?
4. Is the label actually wrong (annotation error)?
5. Is this inherently unpredictable (irreducible error)?
```

---

## Production Monitoring Checklist

```
□ Data drift detection (feature distributions changing)
□ Concept drift (X→Y relationship changing)
□ Prediction distribution shifts
□ Per-group performance monitoring
□ Calibration drift
□ Latency and throughput SLAs
□ Feature pipeline health (nulls, outliers)
□ Model staleness (time since last retrain)
□ Business metric correlation check
```

### Monitoring Code

```python
from scipy.stats import ks_2samp

def detect_drift(reference_data, production_data, threshold=0.05):
    """Detect feature drift using KS test."""
    drift_features = []
    for col in reference_data.columns:
        stat, p_value = ks_2samp(reference_data[col], production_data[col])
        if p_value < threshold:
            drift_features.append((col, stat, p_value))
    return drift_features

# Population Stability Index
def psi(reference, production, bins=10):
    """PSI > 0.2 indicates significant shift."""
    ref_hist, edges = np.histogram(reference, bins=bins)
    prod_hist, _ = np.histogram(production, bins=edges)
    
    ref_pct = ref_hist / len(reference) + 1e-6
    prod_pct = prod_hist / len(production) + 1e-6
    
    return np.sum((prod_pct - ref_pct) * np.log(prod_pct / ref_pct))
```

---

## Common Mistakes

1. **Trusting offline metrics alone** — always validate with A/B test before full rollout
2. **Not checking per-group performance** — aggregate metrics hide disparities
3. **Ignoring calibration** — uncalibrated probabilities → bad downstream decisions
4. **No error analysis** — "model is bad" isn't actionable; understand WHY
5. **No monitoring after deployment** — models degrade silently over time

---

## Interview Questions

**Q: Your model has great AUC but poor business metrics in A/B test. Why?**
Possible reasons: (1) Offline metric doesn't capture business value, (2) Distribution shift between test set and production, (3) Model changes user behavior (feedback loops), (4) Latency issues degrading UX, (5) Presentation bias in offline evaluation.

**Q: How do you evaluate model fairness?**
Check per-group performance (TPR, FPR, precision by demographic). Apply relevant fairness criteria (demographic parity, equal opportunity, equalized odds). Investigate root causes of disparities (biased data, proxy features).

**Q: How do you know when to retrain a model?**
Triggers: (1) Performance drops below threshold, (2) Significant data drift (PSI > 0.2), (3) Major external event, (4) Scheduled interval (weekly/monthly). Also monitor calibration — if predicted probabilities no longer match reality, retrain.

**Q: What's the difference between data drift and concept drift?**
Data drift: P(X) changes (features shift). Concept drift: P(Y|X) changes (relationship between features and target changes). Both require retraining, but concept drift is harder to detect without labels.
