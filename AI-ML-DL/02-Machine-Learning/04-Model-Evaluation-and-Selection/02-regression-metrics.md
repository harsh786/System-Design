# Regression Metrics

## Core Metrics

```
MSE  = (1/n) Σ (yᵢ - ŷᵢ)²           Penalizes large errors heavily (squared)
RMSE = √MSE                            Same units as target
MAE  = (1/n) Σ |yᵢ - ŷᵢ|             Robust to outliers
MAPE = (100/n) Σ |yᵢ - ŷᵢ|/|yᵢ|     Percentage error (undefined when y=0)
R²   = 1 - SS_res/SS_tot              Proportion of variance explained
     = 1 - Σ(yᵢ-ŷᵢ)²/Σ(yᵢ-ȳ)²      R²=1 perfect, R²=0 = predicting mean
```

### Adjusted R²

Penalizes adding features that don't improve the model:

```
Adjusted R² = 1 - (1-R²)(n-1)/(n-p-1)

where p = number of features, n = number of samples
- Can decrease if irrelevant features are added
- Use for comparing models with different feature counts
```

---

## When to Use Which

| Metric | Use When | Properties |
|--------|----------|------------|
| MSE/RMSE | Large errors are particularly costly | Differentiable, penalizes outliers |
| MAE | Robust to outliers, median-like | Not differentiable at 0 |
| MAPE | Need percentage interpretation | Undefined at y=0, asymmetric |
| R² | Want proportion of variance explained | Scale-free, compare across datasets |
| Adjusted R² | Comparing models with different feature counts | Penalizes complexity |

### MSE vs MAE: When to Choose

```
Errors: [1, 1, 1, 1, 10]

MAE  = (1+1+1+1+10)/5 = 2.8
RMSE = √((1+1+1+1+100)/5) = √20.8 = 4.56

RMSE is dominated by the outlier (10).
If outliers are real errors: use RMSE (penalize them)
If outliers are noise: use MAE (ignore them)
```

---

## Residual Analysis

Residuals should be: random, normally distributed, constant variance (homoscedastic).

```
Good residuals:              Bad residuals (pattern):
      ·  ·                         ·     ·
  · ·   ·  ·  ·                 ·   ·
· ─────────────── 0          ·─────────────── 0
  ·  · ·   ·                       ·    ·
      ·  ·                              ·

Random scatter = good         Pattern = model misses something
```

### Checking Residuals

```python
import numpy as np
import matplotlib.pyplot as plt

residuals = y_test - y_pred

# 1. Residuals vs predicted (check for patterns)
plt.scatter(y_pred, residuals, alpha=0.5)
plt.axhline(y=0, color='r', linestyle='--')
plt.xlabel('Predicted'); plt.ylabel('Residuals')

# 2. Distribution (should be normal)
plt.hist(residuals, bins=50)

# 3. Q-Q plot
from scipy import stats
stats.probplot(residuals, plot=plt)

# 4. Check heteroscedasticity (variance should be constant)
# If residuals fan out → need log transform or weighted regression
```

---

## Code Examples

```python
from sklearn.metrics import (
    mean_squared_error, mean_absolute_error,
    r2_score, mean_absolute_percentage_error
)
import numpy as np

# All metrics
mse = mean_squared_error(y_true, y_pred)
rmse = np.sqrt(mse)  # or mean_squared_error(y_true, y_pred, squared=False)
mae = mean_absolute_error(y_true, y_pred)
mape = mean_absolute_percentage_error(y_true, y_pred) * 100
r2 = r2_score(y_true, y_pred)

print(f"MSE:  {mse:.4f}")
print(f"RMSE: {rmse:.4f}")
print(f"MAE:  {mae:.4f}")
print(f"MAPE: {mape:.2f}%")
print(f"R²:   {r2:.4f}")

# Adjusted R²
n, p = len(y_true), X_test.shape[1]
adj_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1)
print(f"Adj R²: {adj_r2:.4f}")
```

### From Scratch

```python
def mse(y_true, y_pred):
    return np.mean((y_true - y_pred) ** 2)

def rmse(y_true, y_pred):
    return np.sqrt(mse(y_true, y_pred))

def mae(y_true, y_pred):
    return np.mean(np.abs(y_true - y_pred))

def mape(y_true, y_pred):
    mask = y_true != 0  # avoid division by zero
    return 100 * np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))

def r2(y_true, y_pred):
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - ss_res / ss_tot
```

---

## Advanced Metrics

### Huber Loss (Robust to Outliers)

```
Huber(δ):
  = ½(y-ŷ)²           if |y-ŷ| ≤ δ   (MSE for small errors)
  = δ|y-ŷ| - ½δ²      if |y-ŷ| > δ   (MAE for large errors)

Combines best of MSE (differentiable) and MAE (robust).
```

### Quantile Loss (Prediction Intervals)

```
Quantile Loss(q):
  = q|y-ŷ|       if y > ŷ  (underestimate penalized by q)
  = (1-q)|y-ŷ|   if y < ŷ  (overestimate penalized by 1-q)

q=0.5 → equivalent to MAE (median prediction)
q=0.9 → 90th percentile prediction (upside risk)
```

---

## Common Mistakes

1. **Using R² alone** — R² can be high even with biased predictions; always check residuals
2. **MAPE with near-zero targets** — explodes; use SMAPE or MAE instead
3. **Comparing RMSE across different scales** — RMSE depends on target scale; use R² or normalize
4. **Ignoring residual patterns** — low RMSE doesn't mean good model if residuals show patterns
5. **Not reporting confidence intervals** — bootstrap RMSE to get uncertainty

---

## Interview Questions

**Q: When would you use MAE over RMSE?**
MAE when robust to outliers needed (housing prices with mansions). RMSE when large errors are particularly costly (safety-critical predictions).

**Q: Can R² be negative?**
Yes! If model is worse than predicting the mean. R² < 0 means your model is actively harmful.

**Q: Why check residuals?**
Low error metrics don't guarantee model quality. Patterns in residuals reveal: missing features, wrong functional form, heteroscedasticity, or data issues.
