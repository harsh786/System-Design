# Logistic Regression

## Intuition

Model the probability of a binary outcome using a linear function passed through the sigmoid, giving a smooth S-curve from 0 to 1.

```
P(Y=1|x) = σ(wᵀx + b)

     1 ┤                    ·········
       │                ···
       │              ··
   0.5 ┤·············●
       │          ··
       │       ···
     0 ┤·······
       └──────────────┼──────────────
                      0
```

## Why Not Linear Regression for Classification?

Linear regression outputs unbounded values. We need P(Y=1) ∈ [0,1]. The sigmoid σ(z) = 1/(1+e⁻ᶻ) maps ℝ → (0,1).

## Mathematical Derivation

**Model:**
```
P(Y=1|x) = σ(wᵀx + b) = 1 / (1 + exp(-(wᵀx + b)))
Log-odds:  log[P(Y=1)/P(Y=0)] = wᵀx + b   ← linear!
```

**Maximum Likelihood Estimation:**
```
L(w) = Π σ(wᵀxᵢ)^yᵢ · (1-σ(wᵀxᵢ))^(1-yᵢ)

Log-likelihood:
ℓ(w) = Σ [yᵢ log(σ(wᵀxᵢ)) + (1-yᵢ) log(1-σ(wᵀxᵢ))]

Negative log-likelihood = Binary Cross-Entropy:
BCE = -(1/n) Σ [yᵢ log(ŷᵢ) + (1-yᵢ) log(1-ŷᵢ)]
```

**Gradient:**
```
∂BCE/∂w = (1/n) Xᵀ(ŷ - y)     where ŷ = σ(Xw + b)
```

This looks identical to linear regression's gradient — the sigmoid's derivative simplifies beautifully: dσ/dz = σ(1-σ).

## Decision Boundary

```
wᵀx + b = 0 defines the boundary (a hyperplane)
wᵀx + b > 0 → predict class 1
wᵀx + b < 0 → predict class 0

   x₂ │    Class 1    /
      │   ·  ·  ·   /
      │  ·  ·      /   Class 0
      │   ·       /     ○  ○
      │  ·      /    ○   ○
      └────────/──────────── x₁
           wᵀx + b = 0
```

## Multi-Class: Softmax Regression

For K classes, use softmax instead of sigmoid:
```
P(Y=k|x) = exp(wₖᵀx) / Σⱼ exp(wⱼᵀx)

Loss: Categorical Cross-Entropy = -Σₖ yₖ log(ŷₖ)
```

Sklearn: `LogisticRegression(multi_class='multinomial')`

## Regularization

Always regularize logistic regression (default in sklearn):
- **L2 (default):** `penalty='l2'`, controlled by `C = 1/λ` (smaller C = stronger regularization)
- **L1:** `penalty='l1'`, produces sparse coefficients, needs `solver='saga'`
- **Elastic Net:** `penalty='elasticnet'`, needs `solver='saga'`

## From-Scratch Implementation

```python
import numpy as np

class LogisticRegression:
    def __init__(self, lr=0.01, epochs=1000, reg=0.0):
        self.lr, self.epochs, self.reg = lr, epochs, reg
    
    def sigmoid(self, z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
    
    def fit(self, X, y):
        m, n = X.shape
        self.w = np.zeros(n)
        self.b = 0
        self.losses = []
        
        for _ in range(self.epochs):
            z = X @ self.w + self.b
            y_pred = self.sigmoid(z)
            
            # Binary cross-entropy + L2
            loss = -(1/m) * (y @ np.log(y_pred + 1e-8) + (1-y) @ np.log(1-y_pred + 1e-8))
            loss += (self.reg / (2*m)) * np.sum(self.w**2)
            self.losses.append(loss)
            
            # Gradients
            dw = (1/m) * X.T @ (y_pred - y) + (self.reg/m) * self.w
            db = (1/m) * np.sum(y_pred - y)
            self.w -= self.lr * dw
            self.b -= self.lr * db
    
    def predict_proba(self, X):
        return self.sigmoid(X @ self.w + self.b)
    
    def predict(self, X, threshold=0.5):
        return (self.predict_proba(X) >= threshold).astype(int)
```

## Sklearn Usage

```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, roc_auc_score

pipe = Pipeline([
    ('scaler', StandardScaler()),
    ('clf', LogisticRegression(C=1.0, max_iter=1000, random_state=42))
])
pipe.fit(X_train, y_train)

# Probabilities (useful for ranking, threshold tuning)
probs = pipe.predict_proba(X_test)[:, 1]
print(f"AUC: {roc_auc_score(y_test, probs):.3f}")

# Coefficients → feature importance
coefs = pipe.named_steps['clf'].coef_[0]
importance = pd.Series(coefs, index=feature_names).sort_values()
```

## Hyperparameter Guide

| Parameter | Values to Try | Effect |
|-----------|---------------|--------|
| C | [0.001, 0.01, 0.1, 1, 10, 100] | Inverse regularization (smaller = stronger reg) |
| penalty | l1, l2, elasticnet | Type of regularization |
| solver | lbfgs, saga, liblinear | Optimization algorithm |
| max_iter | 1000-10000 | May need to increase for convergence |
| class_weight | None, 'balanced' | Handle imbalanced classes |

## When to Use / When NOT to Use

**Use when:**
- Need calibrated probabilities (not just class labels)
- Linear decision boundary is appropriate
- Interpretability via coefficients needed
- Fast training/prediction required
- Baseline for binary classification

**Don't use when:**
- Complex non-linear boundaries needed
- Feature interactions are important (add them manually or use trees)
- Many irrelevant features without regularization

## Common Mistakes

1. **Not scaling features** → convergence issues, unfair regularization
2. **Ignoring `max_iter` warnings** → model hasn't converged, increase it
3. **Using accuracy on imbalanced data** → use AUC, F1, precision/recall
4. **Threshold = 0.5 always** → tune threshold based on business cost of FP vs FN
5. **Confusing C with lambda** → C = 1/λ, so larger C = less regularization

## Interview Questions

**Q1: Why is it called "regression" if it classifies?**
It models log-odds as a linear regression. The continuous probability output is a regression; thresholding converts to classification.

**Q2: Can logistic regression output exactly 0 or 1?**
No. σ(z) approaches but never reaches 0 or 1. In practice, floating point may round, but theoretically outputs are always in (0,1).

**Q3: What's the relationship between logistic regression and Naive Bayes?**
Both are linear classifiers. Gaussian Naive Bayes with shared covariance produces the same decision boundary form as logistic regression. LR is discriminative (models P(Y|X) directly), NB is generative (models P(X|Y)).

**Q4: How do you handle multi-class with logistic regression?**
One-vs-Rest (OvR): K binary classifiers. Multinomial (softmax): single model with K output nodes, optimizes categorical cross-entropy. Multinomial is generally preferred.

**Q5: When would you choose logistic regression over a neural network?**
Small datasets, need interpretability, need calibrated probabilities, limited compute, need fast inference, or as a strong baseline before trying complex models.
