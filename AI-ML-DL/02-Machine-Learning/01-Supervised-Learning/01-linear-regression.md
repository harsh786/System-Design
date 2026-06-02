# Linear Regression

## Intuition

Find the best-fit line (or hyperplane) through data by minimizing the sum of squared distances from points to the line.

```
    y │        ·  /
      │      ·  /  ·
      │    · /·      ← minimize these vertical distances
      │   /·  ·
      │  / ·
      │/·
      └──────────── x
         ŷ = w₀ + w₁x
```

## Mathematical Derivation

**Model:** ŷ = Xw where X has a bias column of ones

**Objective (OLS):** Minimize L(w) = ||y - Xw||² = (y - Xw)ᵀ(y - Xw)

**Expand:**
```
L(w) = yᵀy - 2wᵀXᵀy + wᵀXᵀXw
```

**Take gradient, set to zero:**
```
∂L/∂w = -2Xᵀy + 2XᵀXw = 0
→ w* = (XᵀX)⁻¹Xᵀy        ← Normal Equation
```

**Geometric interpretation:** OLS projects y onto the column space of X. The residual (y - Xw*) is orthogonal to this space.

## Gradient Descent Alternative

When XᵀX is too large to invert (many features or samples):

```python
def linear_regression_gd(X, y, lr=0.01, epochs=1000):
    m, n = X.shape
    w = np.zeros(n)
    b = 0
    for _ in range(epochs):
        y_pred = X @ w + b
        error = y_pred - y
        dw = (1/m) * X.T @ error
        db = (1/m) * np.sum(error)
        w -= lr * dw
        b -= lr * db
    return w, b
```

**Variants:** Batch GD (full dataset), Mini-batch GD (subsets), SGD (single sample)

## Regularization

```
┌──────────────┬────────────┬────────────────────────────────┐
│ Type         │ Penalty    │ Effect                         │
├──────────────┼────────────┼────────────────────────────────┤
│ Ridge (L2)   │ λΣwᵢ²     │ Shrinks all weights equally    │
│ Lasso (L1)   │ λΣ|wᵢ|    │ Drives some weights to zero    │
│ Elastic Net  │ L1 + L2   │ Sparse + handles correlations  │
└──────────────┴────────────┴────────────────────────────────┘
```

**Ridge closed-form:** w* = (XᵀX + λI)⁻¹Xᵀy (always invertible!)

**When to use which:**
- Ridge: all features relevant, correlated features
- Lasso: many irrelevant features, want feature selection
- Elastic Net: correlated features + sparsity desired

## Assumptions

1. **Linearity** — Y is linear in X
2. **Independence** — observations are independent
3. **Homoscedasticity** — constant error variance
4. **Normality** — errors ~ N(0, σ²)
5. **No multicollinearity** — features not highly correlated

**Diagnostics:** Residual plots (check patterns), Q-Q plot (normality), VIF (multicollinearity)

## Loss Functions

```
MSE  = (1/n) Σ(yᵢ - ŷᵢ)²        ← standard, sensitive to outliers
MAE  = (1/n) Σ|yᵢ - ŷᵢ|          ← robust to outliers, not differentiable at 0
Huber = MSE if |error|≤δ, else MAE ← best of both
```

## From-Scratch Implementation

```python
import numpy as np

class LinearRegression:
    def fit(self, X, y):
        X_b = np.c_[np.ones(X.shape[0]), X]  # add bias
        self.w = np.linalg.pinv(X_b.T @ X_b) @ X_b.T @ y  # pinv for stability
    
    def predict(self, X):
        X_b = np.c_[np.ones(X.shape[0]), X]
        return X_b @ self.w
    
    def score(self, X, y):
        y_pred = self.predict(X)
        ss_res = np.sum((y - y_pred)**2)
        ss_tot = np.sum((y - y.mean())**2)
        return 1 - ss_res / ss_tot  # R²
```

## Sklearn Usage

```python
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.preprocessing import StandardScaler, PolynomialFeatures
from sklearn.pipeline import Pipeline

# Basic
model = LinearRegression().fit(X_train, y_train)
print(f"R² = {model.score(X_test, y_test):.3f}")

# With regularization (ALWAYS scale features first for regularized models)
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('model', Ridge(alpha=1.0))  # alpha = λ
])

# Polynomial features
pipe = Pipeline([
    ('poly', PolynomialFeatures(degree=2, include_bias=False)),
    ('scaler', StandardScaler()),
    ('model', Lasso(alpha=0.01))
])
```

## Hyperparameter Guide

| Parameter | Algorithm | Values to Try | Effect |
|-----------|-----------|---------------|--------|
| alpha | Ridge/Lasso | [0.001, 0.01, 0.1, 1, 10, 100] | Regularization strength |
| l1_ratio | ElasticNet | [0.1, 0.3, 0.5, 0.7, 0.9] | L1 vs L2 balance |
| degree | Polynomial | [2, 3, 4] | Model complexity |

## When to Use / When NOT to Use

**Use when:**
- Relationship is approximately linear
- Interpretability matters (coefficients have meaning)
- Baseline model needed quickly
- n_features < n_samples

**Don't use when:**
- Highly non-linear relationships (use trees/NNs)
- Outliers dominate (use Huber or tree-based)
- Features > samples without regularization

## Common Mistakes

1. Not scaling features before regularization → penalty is unfair to large-scale features
2. Using R² on training data → always evaluate on test set
3. Ignoring multicollinearity → unstable coefficients, use VIF check
4. Extrapolating far beyond training range → linear model has no bounds

## Interview Questions

**Q1: When is the Normal Equation preferred over Gradient Descent?**
When n_features < ~10,000. Normal equation is O(n³) in features; GD is iterative but scales better to large feature spaces.

**Q2: What happens if XᵀX is singular?**
Features are linearly dependent. Fix: remove redundant features, use Ridge (adds λI making it invertible), or use pseudoinverse.

**Q3: How does Ridge regression solve multicollinearity?**
By adding λI to XᵀX, it ensures the matrix is always invertible and stabilizes coefficient estimates. Larger λ → more shrinkage → more bias but less variance.

**Q4: Explain R² and its limitations.**
R² = 1 - SS_res/SS_tot. Proportion of variance explained. Limitations: always increases with more features (use adjusted R²), can be negative on test data, doesn't indicate correct model.

**Q5: Why does Lasso produce sparse solutions but Ridge doesn't?**
L1's diamond-shaped constraint region has corners at axes where some weights = 0. L2's circular region intersects loss contours at non-zero points. Geometrically, the loss ellipses are more likely to touch the L1 diamond at a corner.
