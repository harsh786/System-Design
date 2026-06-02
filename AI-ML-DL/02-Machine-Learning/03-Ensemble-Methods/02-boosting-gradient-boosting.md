# Boosting and Gradient Boosting

## Core Idea

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

**Key difference from bagging:** Boosting reduces **bias** (sequentially correcting errors), while bagging reduces **variance** (averaging independent models).

---

## AdaBoost (Adaptive Boosting)

### Algorithm

```
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

### Visualization

```
Round 1:  ○ ○ ○ ● ○ ○ ● ○    (equal weights)
          ↓ misclassified: ● at pos 4,7

Round 2:  ○ ○ ○ ◉ ○ ○ ◉ ○    (● get larger weights)
          ↓ misclassified: ○ at pos 2,5

Round 3:  ○ ◎ ○ ● ◎ ○ ● ○    (new mistakes get weight)
```

### Training Error Bound

AdaBoost's training error decreases exponentially:

```
Training error ≤ Πₘ 2√(εₘ(1-εₘ)) = e^(-2Σγₘ²)

where γₘ = ½ - εₘ (edge over random)
```

If each learner achieves at least γ edge: error ≤ e^(-2Mγ²) → exponential decrease!

### AdaBoost From Scratch

```python
import numpy as np
from sklearn.tree import DecisionTreeClassifier

class AdaBoostScratch:
    def __init__(self, n_estimators=50):
        self.n_estimators = n_estimators
    
    def fit(self, X, y):
        n = len(X)
        w = np.ones(n) / n
        self.estimators = []
        self.alphas = []
        
        for _ in range(self.n_estimators):
            stump = DecisionTreeClassifier(max_depth=1)
            stump.fit(X, y, sample_weight=w)
            pred = stump.predict(X)
            
            err = np.sum(w * (pred != y)) / np.sum(w)
            if err >= 0.5:
                break
            
            alpha = 0.5 * np.log((1 - err) / (err + 1e-10))
            
            # Update weights (assumes y in {-1, +1})
            w *= np.exp(-alpha * y * pred)
            w /= w.sum()
            
            self.estimators.append(stump)
            self.alphas.append(alpha)
        return self
    
    def predict(self, X):
        predictions = np.array([
            alpha * est.predict(X) 
            for alpha, est in zip(self.alphas, self.estimators)
        ])
        return np.sign(predictions.sum(axis=0))
```

---

## Gradient Boosting

### Key Insight

Instead of reweighting samples, fit each new model to the **negative gradient** (pseudo-residuals) of the loss function.

### Algorithm

```
F₀(x) = argmin_γ Σ L(yᵢ, γ)           (initialize with constant)

For m = 1 to M:
    1. Compute pseudo-residuals:
       rᵢₘ = -∂L(yᵢ, F_{m-1}(xᵢ))/∂F_{m-1}(xᵢ)
       
       For MSE: rᵢₘ = yᵢ - F_{m-1}(xᵢ)  (actual residuals!)
       For log-loss: rᵢₘ = yᵢ - σ(F_{m-1}(xᵢ))  (probability residuals)
       
    2. Fit weak learner hₘ to residuals: hₘ ← fit(X, r)
    3. Update: Fₘ(x) = F_{m-1}(x) + η · hₘ(x)
       
       η = learning rate (shrinkage), typically 0.01-0.3

Final: F(x) = F₀(x) + η·h₁(x) + η·h₂(x) + ... + η·hₘ(x)
```

### Why "Gradient" Boosting?

We're doing **gradient descent in function space**. Each tree is a step in the direction that reduces the loss:

```
Standard GD:  θ_{t+1} = θ_t - η · ∇L(θ_t)        (parameter space)
Gradient Boost: F_{m} = F_{m-1} + η · hₘ           (function space)
                where hₘ ≈ -∇L w.r.t. F_{m-1}
```

### Learning Rate / n_estimators Tradeoff

```
High lr (0.3) + few trees (100):     Fast but underfits
Low lr (0.01) + many trees (5000):   Slow but generalizes better

Rule: lr × n_estimators ≈ constant for similar capacity
Always use early stopping to find optimal n_estimators!
```

### Shrinkage and Subsampling

- **Shrinkage (learning rate):** Each tree contributes less → needs more trees but generalizes better
- **Subsampling (stochastic GB):** Use random fraction of data per tree → reduces overfitting, speeds training
- **Column subsampling:** Random feature subset per tree → decorrelates trees

---

## Gradient Boosting From Scratch

```python
import numpy as np
from sklearn.tree import DecisionTreeRegressor

class GradientBoostingRegressorScratch:
    def __init__(self, n_estimators=100, learning_rate=0.1, max_depth=3):
        self.n_estimators = n_estimators
        self.lr = learning_rate
        self.max_depth = max_depth
    
    def fit(self, X, y):
        self.initial_prediction = y.mean()
        self.estimators = []
        
        current_pred = np.full(len(y), self.initial_prediction)
        
        for _ in range(self.n_estimators):
            # Negative gradient (residuals for MSE)
            residuals = y - current_pred
            
            # Fit tree to residuals
            tree = DecisionTreeRegressor(max_depth=self.max_depth)
            tree.fit(X, residuals)
            
            # Update predictions
            current_pred += self.lr * tree.predict(X)
            self.estimators.append(tree)
        return self
    
    def predict(self, X):
        pred = np.full(len(X), self.initial_prediction)
        for tree in self.estimators:
            pred += self.lr * tree.predict(X)
        return pred
    
    def staged_predict(self, X):
        """Yield predictions at each stage for learning curve analysis."""
        pred = np.full(len(X), self.initial_prediction)
        for tree in self.estimators:
            pred += self.lr * tree.predict(X)
            yield pred.copy()
```

---

## sklearn GradientBoostingClassifier

```python
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

gbc = GradientBoostingClassifier(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=4,
    min_samples_leaf=5,
    subsample=0.8,
    random_state=42
)

scores = cross_val_score(gbc, X, y, cv=5, scoring='roc_auc')
print(f"AUC: {scores.mean():.4f} ± {scores.std():.4f}")

# With early stopping (using staged_predict)
gbc.fit(X_train, y_train)
val_scores = []
for y_pred in gbc.staged_predict_proba(X_val):
    val_scores.append(roc_auc_score(y_val, y_pred[:, 1]))
best_n = np.argmax(val_scores) + 1
print(f"Best n_estimators: {best_n}")
```

---

## AdaBoost vs Gradient Boosting

| Aspect | AdaBoost | Gradient Boosting |
|--------|----------|-------------------|
| Mechanism | Reweight samples | Fit residuals (gradients) |
| Loss function | Exponential (implicit) | Any differentiable loss |
| Noise sensitivity | High (upweights noisy points) | Lower (robust losses available) |
| Flexibility | Limited | Very flexible |
| Relationship | Special case of GB with exponential loss | General framework |

---

## Common Mistakes

1. **No early stopping** — boosting WILL overfit without it
2. **Learning rate too high** — use 0.01-0.1 with more trees
3. **max_depth too high** — use 3-6 for base trees (weak learners!)
4. **Ignoring feature interactions** — max_depth controls interaction order (depth=3 → 3-way interactions)
5. **Not using subsample** — stochastic GB generalizes better

---

## Interview Questions

**Q: Can Gradient Boosting overfit?**
Yes! Unlike bagging, boosting can overfit with too many iterations. Each tree fits remaining signal AND noise. Use early stopping, learning rate shrinkage, and regularization.

**Q: Why are weak learners preferred in boosting?**
Boosting reduces bias sequentially. Weak learners (high bias, low variance) avoid overfitting to residuals. Strong learners would memorize noise in the residuals.

**Q: How does learning rate interact with n_estimators?**
Lower learning rate needs more estimators. The combination lr × n_estimators roughly determines model capacity. Lower lr with early stopping typically gives best generalization.

**Q: What's the difference between AdaBoost and Gradient Boosting?**
AdaBoost reweights samples (exponential loss). Gradient Boosting fits pseudo-residuals (any loss). AdaBoost is a special case of GB. GB is more flexible and robust.
