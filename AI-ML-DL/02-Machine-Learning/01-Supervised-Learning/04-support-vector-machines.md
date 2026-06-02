# Support Vector Machines (SVM)

## Intuition

Find the hyperplane that maximizes the margin (gap) between classes. Only the closest points (support vectors) determine the boundary.

```
   x₂ │     + + +
      │   +   + ←── support vector
      │  +  ┊   ┊
      │     ┊   ┊  margin = 2/||w||
      │     ┊   ┊
      │  ─  ┊   ┊  ─ ─
      │     ┊   ┊
      │  ─    ─  ─ ←── support vector
      │    ─   ─
      └──────────────── x₁
           wᵀx + b = 0
```

## Mathematical Formulation

### Hard Margin (linearly separable)

```
minimize    (1/2)||w||²
subject to  yᵢ(wᵀxᵢ + b) ≥ 1,  ∀i

Margin = 2/||w||, so minimizing ||w||² maximizes margin.
```

### Soft Margin (real-world, non-separable)

```
minimize    (1/2)||w||² + C Σᵢ ξᵢ
subject to  yᵢ(wᵀxᵢ + b) ≥ 1 - ξᵢ,  ξᵢ ≥ 0

ξᵢ = slack variable (how much point i violates margin)
C = trade-off parameter:
  Large C → narrow margin, fewer violations (may overfit)
  Small C → wide margin, more violations (may underfit)
```

### Dual Formulation (via Lagrange multipliers)

```
maximize    Σᵢ αᵢ - (1/2) Σᵢ Σⱼ αᵢαⱼyᵢyⱼ(xᵢᵀxⱼ)
subject to  0 ≤ αᵢ ≤ C,  Σᵢ αᵢyᵢ = 0

Key insight: only dot products xᵢᵀxⱼ appear → kernel trick!
Solution: w* = Σᵢ αᵢyᵢxᵢ  (only support vectors have αᵢ > 0)
```

## The Kernel Trick

Replace dot product with kernel function K(xᵢ,xⱼ) = φ(xᵢ)ᵀφ(xⱼ) — compute similarity in high-dimensional space without explicitly mapping there.

```
┌───────────────┬──────────────────────────┬─────────────────────┐
│ Kernel        │ Formula                  │ Use Case            │
├───────────────┼──────────────────────────┼─────────────────────┤
│ Linear        │ xᵀz                     │ Linearly separable  │
│ Polynomial    │ (γ·xᵀz + r)^d          │ Feature interactions│
│ RBF (Gaussian)│ exp(-γ||x-z||²)         │ Most common default │
│ Sigmoid       │ tanh(γ·xᵀz + r)        │ Neural-net-like     │
└───────────────┴──────────────────────────┴─────────────────────┘

RBF maps to infinite-dimensional space but computes in O(d) time!
```

### Why RBF works:

```
Before kernel (not separable):     After RBF (separable in higher dim):
    ─ ─ + + + ─ ─                     ─     ─
   ─   + + + +   ─                  ─         ─
    ─ ─ + + + ─ ─                       + + +
                                       + + + +
                                     ─         ─
                                       ─     ─
```

## Hinge Loss Interpretation

```
SVM minimizes: (1/n) Σ max(0, 1 - yᵢ(wᵀxᵢ + b)) + λ||w||²
                        ↑ hinge loss                    ↑ regularization

Hinge loss = 0 when point is correctly classified with margin ≥ 1
```

## From-Scratch Implementation (Linear SVM with SGD)

```python
import numpy as np

class LinearSVM:
    def __init__(self, C=1.0, lr=0.001, epochs=1000):
        self.C, self.lr, self.epochs = C, lr, epochs
    
    def fit(self, X, y):
        y = np.where(y <= 0, -1, 1)  # SVM needs {-1, +1}
        m, n = X.shape
        self.w = np.zeros(n)
        self.b = 0
        
        for _ in range(self.epochs):
            for i in range(m):
                condition = y[i] * (X[i] @ self.w + self.b) >= 1
                if condition:
                    self.w -= self.lr * (2 * (1/self.C) * self.w)
                else:
                    self.w -= self.lr * (2 * (1/self.C) * self.w - y[i] * X[i])
                    self.b -= self.lr * (-y[i])
    
    def predict(self, X):
        return np.sign(X @ self.w + self.b)
```

## Sklearn Usage

```python
from sklearn.svm import SVC, LinearSVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# ALWAYS scale for SVM
pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('svm', SVC(kernel='rbf', C=1.0, gamma='scale', probability=True))
])
pipe.fit(X_train, y_train)

# For large datasets, use LinearSVC (much faster)
pipe_fast = Pipeline([
    ('scaler', StandardScaler()),
    ('svm', LinearSVC(C=1.0, max_iter=10000))
])

# Get probabilities (slower, uses Platt scaling)
probs = pipe.predict_proba(X_test)
```

## Hyperparameter Guide

| Parameter | Values to Try | Effect |
|-----------|---------------|--------|
| C | [0.01, 0.1, 1, 10, 100] | Regularization (smaller = wider margin) |
| kernel | linear, rbf, poly | Decision boundary shape |
| gamma (RBF) | [0.001, 0.01, 0.1, 1, 'scale'] | RBF reach (small=smooth, large=complex) |
| degree (poly) | [2, 3, 4] | Polynomial degree |

**Tip:** Use GridSearchCV on C and gamma together — they interact strongly.

## When to Use / When NOT to Use

**Use when:**
- Clear margin of separation exists
- High-dimensional data (text classification, genomics)
- n_features > n_samples (kernel SVM works well)
- Medium-sized datasets (1K-100K samples)

**Don't use when:**
- Very large datasets (>100K) — too slow, use LinearSVC or SGDClassifier
- Need probability estimates (Platt scaling is approximate)
- Need interpretability (black box with kernels)
- Noisy data with overlapping classes (try ensemble methods)

## Common Mistakes

1. **Not scaling features** → SVM uses distances, unscaled features dominate
2. **Using RBF without tuning gamma** → default may over/underfit
3. **Using SVC on large data** → O(n²) to O(n³) complexity, use LinearSVC
4. **Forgetting to encode labels as -1/+1** for custom implementations
5. **Ignoring C-gamma interaction** → always tune together

## Interview Questions

**Q1: Why do only support vectors matter?**
The optimization solution depends only on points at or within the margin. Removing non-support-vector points doesn't change the decision boundary. This makes SVM memory-efficient.

**Q2: Explain the kernel trick intuitively.**
Instead of explicitly computing features in high-dimensional space φ(x), we compute K(x,z) = φ(x)·φ(z) directly. For RBF, this corresponds to infinite dimensions but costs only O(d) to compute.

**Q3: SVM vs Logistic Regression — when to prefer which?**
SVM: maximizes geometric margin, no probabilistic interpretation, kernel trick for non-linearity. LR: maximizes likelihood, gives calibrated probabilities, faster, easier online learning. Use LR as default, SVM when kernels needed or high-dimensional sparse data.

**Q4: What happens with very large C?**
Approaches hard-margin SVM — very narrow margin, tries to classify all training points correctly. Overfits noisy data. Equivalent to less regularization.

**Q5: Can SVM do regression?**
Yes — SVR (Support Vector Regression). Uses ε-insensitive loss: ignores errors within ε of the prediction, penalizes errors outside. Creates an ε-tube around predictions.
