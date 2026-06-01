# Ensemble Methods - Complete Guide

## Why Ensembles Work

### The Wisdom of Crowds
Combining multiple diverse models reduces error. Mathematically, if we have M models each with error rate ε < 0.5, and they make independent errors, majority vote error:

```
P(ensemble wrong) = Σ_{k=⌈M/2⌉}^{M} C(M,k) · εᵏ · (1-ε)^(M-k)

Example: M=25 models, each 35% error rate
P(majority wrong) ≈ 6%  (dramatic improvement!)
```

### Bias-Variance Decomposition for Ensembles

```
Single Model:     Error = Bias² + Variance + Noise
Bagging (avg):    Error = Bias² + Variance/M + Noise    (reduces variance)
Boosting (seq):   Error ≈ 0   + Variance + Noise       (reduces bias)

                    Bias²        Variance
                  ┌─────────┬─────────────┐
Single Tree:      │█████    │█████████████│  High var, low bias
Random Forest:    │█████    │████         │  Same bias, lower var
Boosted Trees:    │██       │██████       │  Lower bias, some var
                  └─────────┴─────────────┘
```

---

## 1. Bagging (Bootstrap Aggregating)

### Algorithm

```
Bagging(D, M, LearningAlgorithm):
    for m = 1 to M:
        D_m = Bootstrap sample from D (sample n items with replacement)
        h_m = LearningAlgorithm(D_m)
    
    Prediction:
      Classification: majority_vote(h₁(x), h₂(x), ..., hₘ(x))
      Regression:     (1/M) Σ hₘ(x)
```

### Bootstrap Sampling
```
Original: [1, 2, 3, 4, 5, 6, 7, 8]

Bootstrap 1: [2, 5, 5, 1, 8, 3, 1, 7]  ← with replacement
Bootstrap 2: [3, 1, 6, 6, 4, 8, 2, 2]
Bootstrap 3: [7, 4, 1, 5, 3, 3, 8, 6]

Each sample contains ~63.2% unique items (1 - 1/e)
Remaining ~36.8% = Out-of-Bag (OOB) samples → free validation!
```

### Random Forest

Random Forest = Bagging + Random Feature Subsets

```
Key modification: At each split, only consider √p features (classification)
                  or p/3 features (regression)

This decorrelates the trees → further reduces variance!

┌─────────────────────────────────────────────────────────┐
│                    RANDOM FOREST                          │
│                                                          │
│  Bootstrap 1     Bootstrap 2     Bootstrap 3    ...     │
│  Features: √p    Features: √p    Features: √p          │
│       │               │               │                  │
│    ┌──┴──┐         ┌──┴──┐         ┌──┴──┐             │
│    │Tree1│         │Tree2│         │Tree3│    ...       │
│    └──┬──┘         └──┬──┘         └──┬──┘             │
│       │               │               │                  │
│       ▼               ▼               ▼                  │
│    pred_1          pred_2          pred_3               │
│              ╲        │        ╱                         │
│               ╲       │       ╱                          │
│                ▼      ▼      ▼                           │
│            ┌──────────────────────┐                      │
│            │   Majority Vote /    │                      │
│            │      Average         │                      │
│            └──────────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### Feature Importance in Random Forest
```python
# Method 1: Mean Decrease in Impurity (MDI)
# Sum of impurity decreases for all splits using that feature, weighted by samples

# Method 2: Permutation Importance
# Shuffle feature values, measure accuracy drop
from sklearn.inspection import permutation_importance
result = permutation_importance(rf, X_test, y_test, n_repeats=10)
```

---

## 2. Boosting

### Core Idea
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

### AdaBoost (Adaptive Boosting)

```
AdaBoost Algorithm:
───────────────────
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

```
Weight visualization:

Round 1:  ○ ○ ○ ● ○ ○ ● ○    (equal weights)
          ↓ misclassified: ● at pos 4,7

Round 2:  ○ ○ ○ ◉ ○ ○ ◉ ○    (● get larger weights)
          ↓ misclassified: ○ at pos 2,5

Round 3:  ○ ◎ ○ ● ◎ ○ ● ○    (new mistakes get weight)
```

### Gradient Boosting

```
Key Insight: Instead of reweighting, fit each new model to the RESIDUALS
(negative gradient of the loss function)

Algorithm:
──────────
F₀(x) = argmin_γ Σ L(yᵢ, γ)           (initialize with constant)

For m = 1 to M:
    1. Compute pseudo-residuals:
       rᵢₘ = -∂L(yᵢ, F_{m-1}(xᵢ))/∂F_{m-1}(xᵢ)
       
       For MSE: rᵢₘ = yᵢ - F_{m-1}(xᵢ)  (actual residuals!)
       
    2. Fit weak learner hₘ to residuals: hₘ ← fit(X, r)
    3. Update: Fₘ(x) = F_{m-1}(x) + η · hₘ(x)
       
       η = learning rate (shrinkage), typically 0.01-0.3

Final: F(x) = F₀(x) + η·h₁(x) + η·h₂(x) + ... + η·hₘ(x)
```

### XGBoost (eXtreme Gradient Boosting)

Key innovations over vanilla Gradient Boosting:

```
1. Regularized objective:
   Obj = Σ L(yᵢ, ŷᵢ) + Σₘ Ω(fₘ)
   where Ω(f) = γT + (1/2)λ||w||²
   T = number of leaves, w = leaf weights

2. Second-order Taylor approximation:
   Obj ≈ Σ [gᵢfₘ(xᵢ) + (1/2)hᵢfₘ²(xᵢ)] + Ω(fₘ)
   where gᵢ = ∂L/∂ŷ (gradient), hᵢ = ∂²L/∂ŷ² (Hessian)

3. Optimal leaf weight: w*ⱼ = -Σ_{i∈Iⱼ} gᵢ / (Σ_{i∈Iⱼ} hᵢ + λ)

4. Split gain: Gain = (1/2)[G²_L/(H_L+λ) + G²_R/(H_R+λ) - (G_L+G_R)²/(H_L+H_R+λ)] - γ

5. System optimizations:
   - Column block for parallel split finding
   - Cache-aware access
   - Sparsity-aware (handles missing values)
   - Out-of-core computation
```

### LightGBM

```
Key innovations:
1. Leaf-wise tree growth (vs level-wise in XGBoost)
   
   Level-wise (XGBoost):      Leaf-wise (LightGBM):
        ○                            ○
       / \                          / \
      ○   ○                        ○   ○
     / \ / \                      / \
    ○  ○ ○  ○                    ○   ○
                                    / \
   Balanced but wasteful          ○   ○
                                  
   Grows deepest where most gain

2. Gradient-based One-Side Sampling (GOSS):
   Keep all large-gradient samples, randomly sample small-gradient ones

3. Exclusive Feature Bundling (EFB):
   Bundle mutually exclusive features (sparse) → fewer features

4. Histogram-based splitting: bin continuous values → faster
```

### CatBoost

```
Key innovations:
1. Ordered Target Statistics for categorical features:
   - Avoids target leakage with time-based ordering
   
2. Ordered Boosting:
   - Different permutations for residual calculation
   - Reduces prediction shift (overfitting on training residuals)

3. Symmetric trees: all nodes at same level use same split
   → Faster inference, better CPU cache utilization
```

---

## 3. Stacking (Stacked Generalization)

```
┌─────────────────────────────────────────────────────────┐
│                    STACKING                               │
│                                                          │
│  Level 0 (Base Learners):                               │
│  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐           │
│  │  RF   │  │  SVM  │  │  KNN  │  │  XGB  │           │
│  └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘           │
│      │          │          │          │                  │
│      ▼          ▼          ▼          ▼                  │
│    pred_1    pred_2     pred_3     pred_4               │
│      │          │          │          │                  │
│      └──────────┴──────────┴──────────┘                  │
│                     │                                    │
│                     ▼                                    │
│  Level 1 (Meta-Learner):                               │
│  ┌─────────────────────────────────┐                    │
│  │   Logistic Regression / Ridge   │                    │
│  └────────────────┬────────────────┘                    │
│                   │                                      │
│                   ▼                                      │
│            Final Prediction                              │
└─────────────────────────────────────────────────────────┘

IMPORTANT: Use cross-validated predictions from base learners
to train meta-learner (avoid overfitting!)
```

### Python Implementation
```python
from sklearn.model_selection import cross_val_predict

# Level 0: Generate meta-features using CV predictions
meta_features = np.column_stack([
    cross_val_predict(rf, X_train, y_train, cv=5, method='predict_proba')[:, 1],
    cross_val_predict(svm, X_train, y_train, cv=5, method='decision_function'),
    cross_val_predict(xgb, X_train, y_train, cv=5, method='predict_proba')[:, 1],
])

# Level 1: Train meta-learner
meta_learner = LogisticRegression()
meta_learner.fit(meta_features, y_train)
```

---

## 4. Comparison Table

| Method | Bagging | Boosting | Stacking |
|--------|---------|----------|----------|
| Combines | Parallel | Sequential | Layered |
| Reduces | Variance | Bias | Both |
| Base learners | Strong (deep trees) | Weak (stumps) | Diverse |
| Overfitting risk | Low | Medium-High | High (need CV) |
| Parallelizable | Yes | No | Level 0: Yes |
| Example | Random Forest | XGBoost | RF+SVM+XGB→LR |

### XGBoost vs LightGBM vs CatBoost

| Feature | XGBoost | LightGBM | CatBoost |
|---------|---------|----------|----------|
| Tree growth | Level-wise | Leaf-wise | Symmetric |
| Speed | Medium | Fastest | Medium |
| Categorical | Manual encoding | Direct support | Best native |
| Missing values | Built-in | Built-in | Built-in |
| GPU support | Yes | Yes | Yes |
| Best for | General | Large data | Categorical-heavy |
| Default perf | Good | Good | Often best OOB |

---

## 5. Hyperparameter Tuning

### Key Parameters

```
Random Forest:
- n_estimators: 100-1000 (more = better, diminishing returns)
- max_depth: None or 10-30
- min_samples_split: 2-20
- max_features: sqrt(p) for clf, p/3 for reg

XGBoost/LightGBM:
- n_estimators: 100-5000 (with early stopping)
- learning_rate: 0.01-0.3 (lower = more trees needed)
- max_depth: 3-10 (XGB), -1 for LightGBM
- subsample: 0.6-1.0
- colsample_bytree: 0.6-1.0
- min_child_weight: 1-10
- reg_alpha (L1): 0-1
- reg_lambda (L2): 0-1
```

### Tuning Strategy
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
    }
    
    model = xgb.XGBClassifier(**params, early_stopping_rounds=50)
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model.best_score

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=100)
```

---

## Interview Questions

**Q: Why does Random Forest not overfit as you add more trees?**
Each tree is independent, and averaging independent estimates reduces variance without increasing bias. The generalization error converges as M→∞ (Breiman's proof).

**Q: Can Gradient Boosting overfit?**
Yes! Unlike bagging, boosting can overfit with too many iterations. Use early stopping, learning rate shrinkage, and regularization.

**Q: XGBoost vs Random Forest - when to use which?**
- RF: Less tuning needed, parallel training, robust baseline
- XGBoost: Usually better accuracy with tuning, handles imbalanced data better, more control over optimization

**Q: What makes a good base learner for stacking?**
Diversity! Combine models with different inductive biases (tree-based + linear + instance-based). Highly correlated models add little value.

**Q: How does the learning rate interact with n_estimators in boosting?**
Lower learning rate needs more estimators. The combination lr×n_estimators roughly determines model capacity. Use early stopping to find optimal n_estimators for a given learning rate.

---

## Exercises

### Exercise 1 (Beginner)
**Problem:** Explain why a Random Forest with 100 trees won't overfit even though individual trees might overfit.
**Hint:** Think about what bagging does to variance.

<details><summary>Solution</summary>

Individual deep trees have high variance (overfit). Random Forest reduces variance through:
1. **Bagging:** Each tree trained on different bootstrap sample
2. **Feature randomization:** Each split considers random subset of features
3. **Averaging:** Averaging M independent predictions reduces variance by ~1/M

Key insight: If trees make independent errors, averaging cancels them out. RF's variance ≈ ρσ²/M + (1-ρ)σ²/M where ρ is correlation between trees. Feature randomization reduces ρ.

The bias stays the same (each tree is still expressive), but variance drops dramatically.

</details>

### Exercise 2 (Beginner)
**Problem:** In boosting, why are weak learners (e.g., decision stumps) preferred over strong learners?
**Hint:** Think about the bias-variance decomposition for boosting.

<details><summary>Solution</summary>

Boosting sequentially reduces bias. Starting with weak learners (high bias, low variance):
1. **Flexibility:** Each new weak learner corrects remaining errors without overfitting
2. **Regularization:** Shallow trees (stumps) can't memorize noise
3. **Additive model:** Final model is sum of many small corrections
4. **Control:** Learning rate × weak learner gives fine-grained adjustments

Strong learners would overfit quickly to residuals (fitting noise), making the ensemble worse. The combination of many weak learners creates a strong learner with controlled complexity.

</details>

### Exercise 3 (Beginner)
**Problem:** What fraction of training data is NOT included in a single bootstrap sample? What is this used for?
**Hint:** Probability of not being selected in n draws with replacement from n items.

<details><summary>Solution</summary>

P(sample not selected) = (1 - 1/n)ⁿ → 1/e ≈ 0.368 as n → ∞

~36.8% of data is "Out-of-Bag" (OOB) for each tree.

Uses:
1. **OOB error estimate:** Free validation — predict each sample using only trees that didn't train on it
2. **No need for separate validation set** — OOB error ≈ cross-validation error
3. **Feature importance:** Permute OOB features and measure accuracy drop

</details>

### Exercise 4 (Intermediate)
**Problem:** Compare the gradient boosting update with the AdaBoost weight update. How are they conceptually different?
**Hint:** One reweights samples, the other fits residuals.

<details><summary>Solution</summary>

**AdaBoost:**
- Reweights samples: increase weight on misclassified, decrease on correct
- Each learner focuses more on "hard" examples
- Update: wᵢ ← wᵢ · exp(α·I(yᵢ ≠ hₘ(xᵢ)))
- Equivalent to additive model with exponential loss

**Gradient Boosting:**
- Fits to negative gradient (pseudo-residuals) of loss function
- Each learner predicts what's "left over" after previous predictions
- Update: F_{m+1}(x) = Fₘ(x) + η·hₘ(x) where hₘ fits -∂L/∂F
- Generalizes to any differentiable loss

**Connection:** AdaBoost is gradient boosting with exponential loss.
Gradient boosting is more flexible (any loss: MSE, log-loss, Huber, quantile).

</details>

### Exercise 5 (Intermediate)
**Problem:** You're comparing XGBoost, LightGBM, and CatBoost. When would you choose each?
**Hint:** Consider data types, dataset size, and categorical features.

<details><summary>Solution</summary>

**XGBoost:**
- General purpose, well-established
- Good for medium datasets
- Level-wise tree growth (balanced trees)
- Best when: well-tuned, medium data, Kaggle competitions

**LightGBM:**
- Fastest for large datasets
- Leaf-wise growth (deeper, can overfit on small data)
- GOSS (gradient-based one-side sampling) + EFB (exclusive feature bundling)
- Best when: large data (>100K rows), many features, speed matters

**CatBoost:**
- Native categorical feature handling (ordered target encoding)
- Ordered boosting (reduces prediction shift/target leakage)
- Minimal tuning needed
- Best when: many categorical features, want minimal preprocessing, robust defaults

</details>

### Exercise 6 (Intermediate)
**Problem:** Explain the difference between feature_importances_ (Gini importance) and permutation importance. When can Gini importance be misleading?
**Hint:** Think about what happens with high-cardinality or correlated features.

<details><summary>Solution</summary>

**Gini importance (MDI):**
- Sum of impurity decreases at all splits using that feature
- Built into tree training
- Biased toward high-cardinality features (more split opportunities)
- Biased toward continuous over categorical features

**Permutation importance:**
- Shuffle feature values, measure accuracy drop
- Model-agnostic, computed after training
- Unbiased for cardinality
- BUT: correlated features split importance (shuffling one doesn't help if correlated feature remains)

**Misleading cases for Gini:**
- Random ID feature gets high importance (many unique values)
- Categorical with many levels ranks artificially high
- Correlated features: importance split arbitrarily

**Best practice:** Use permutation importance + SHAP values for reliable interpretation.

</details>

### Exercise 7 (Intermediate)
**Problem:** Design a stacking ensemble for a binary classification problem. You have: Random Forest, XGBoost, Logistic Regression, and KNN as base models. How do you train it properly?
**Hint:** Think about data leakage in meta-learner training.

<details><summary>Solution</summary>

**Stacking architecture:**
- Level 0: RF, XGBoost, LR, KNN (base learners)
- Level 1: Meta-learner (e.g., Logistic Regression)

**Proper training (avoiding leakage):**
1. Split data into K folds
2. For each fold i:
   - Train each base learner on folds ≠ i
   - Predict on fold i → these become meta-features
3. Stack all out-of-fold predictions → training set for meta-learner
4. Retrain base learners on ALL training data
5. Meta-learner input = base learner predictions on new data

**Key considerations:**
- Meta-learner should be simple (avoid overfitting to base predictions)
- Include original features in meta-learner input? Sometimes helps.
- Diverse base learners = better (LR captures linear, RF captures non-linear)
- Can add prediction probabilities, not just class labels

</details>

### Exercise 8 (Advanced)
**Problem:** Prove that AdaBoost's training error decreases exponentially with the number of rounds (under the weak learner assumption).
**Hint:** The training error is bounded by Πₘ 2√(εₘ(1-εₘ)).

<details><summary>Solution</summary>

After M rounds, training error ≤ Πₘ₌₁ᴹ Zₘ where Zₘ = 2√(εₘ(1-εₘ))

Since each weak learner has εₘ < ½ (better than random):
Let γₘ = ½ - εₘ > 0 (edge over random)

Zₘ = 2√(εₘ(1-εₘ)) = 2√((½-γₘ)(½+γₘ)) = √(1-4γₘ²) ≤ e^(-2γₘ²)

Therefore: Training error ≤ Πₘ e^(-2γₘ²) = e^(-2Σγₘ²)

If each learner achieves at least γ edge: error ≤ e^(-2Mγ²)

This decreases exponentially with M! The training error goes to zero exponentially fast, which is why AdaBoost is prone to overfitting on noisy data.

</details>

### Exercise 9 (Advanced)
**Problem:** Explain XGBoost's regularized objective function. What do the γ and λ terms control?
**Hint:** The objective has a loss term and a complexity term.

<details><summary>Solution</summary>

XGBoost objective at round m:
Obj = Σᵢ L(yᵢ, ŷᵢ^(m-1) + fₘ(xᵢ)) + Ω(fₘ)

Regularization term: Ω(f) = γT + ½λΣⱼ₌₁ᵀ wⱼ²

Where:
- T = number of leaves in tree
- wⱼ = weight (prediction) at leaf j
- γ = minimum loss reduction to make a split (controls tree depth)
- λ = L2 regularization on leaf weights (shrinks predictions)

**Second-order Taylor approximation:**
Obj ≈ Σᵢ [gᵢfₘ(xᵢ) + ½hᵢfₘ²(xᵢ)] + γT + ½λΣwⱼ²

Optimal leaf weight: wⱼ* = -Σᵢ∈ⱼ gᵢ / (Σᵢ∈ⱼ hᵢ + λ)
Split gain: ½[G_L²/(H_L+λ) + G_R²/(H_R+λ) - (G_L+G_R)²/(H_L+H_R+λ)] - γ

- γ: Pruning — split only if gain > γ. Larger γ = simpler trees.
- λ: Smoothing — prevents extreme leaf predictions. Larger λ = more conservative.

</details>

### Exercise 10 (Advanced)
**Problem:** Implement a voting classifier that supports hard voting, soft voting, and weighted voting. Analyze when each strategy wins.
**Hint:** Soft voting uses predicted probabilities.

<details><summary>Solution</summary>

```python
import numpy as np

class VotingClassifier:
    def __init__(self, estimators, voting='hard', weights=None):
        self.estimators = estimators
        self.voting = voting
        self.weights = weights or [1]*len(estimators)
    
    def fit(self, X, y):
        for est in self.estimators:
            est.fit(X, y)
        return self
    
    def predict(self, X):
        if self.voting == 'hard':
            predictions = np.array([est.predict(X) for est in self.estimators])
            # Weighted majority vote
            return np.apply_along_axis(
                lambda x: np.bincount(x, weights=self.weights).argmax(), 
                axis=0, arr=predictions)
        else:  # soft
            probas = np.array([est.predict_proba(X) for est in self.estimators])
            weighted = np.average(probas, axis=0, weights=self.weights)
            return np.argmax(weighted, axis=1)
```

**When each wins:**
- **Hard voting:** When models don't output calibrated probabilities
- **Soft voting:** When models are well-calibrated (uses confidence information)
- **Weighted voting:** When model quality varies significantly (weight by CV score)

</details>

---

## Self-Assessment Quiz

**1. Bagging primarily reduces:**
- A) Bias
- B) Variance
- C) Irreducible error
- D) Training time

<details><summary>Answer</summary>B) Variance (by averaging multiple high-variance models)</details>

**2. In Random Forest, what is randomized at each split?**
- A) The learning rate
- B) The subset of features considered
- C) The loss function
- D) The tree depth

<details><summary>Answer</summary>B) A random subset of features (typically √p for classification, p/3 for regression)</details>

**3. Boosting builds trees:**
- A) In parallel, independently
- B) Sequentially, each correcting the previous
- C) By randomly sampling features
- D) Using different loss functions

<details><summary>Answer</summary>B) Sequentially, where each tree fits the residual/gradient of the ensemble so far</details>

**4. The learning rate (η) in gradient boosting:**
- A) Controls tree depth
- B) Shrinks each tree's contribution (regularization)
- C) Sets the number of trees
- D) Controls feature sampling

<details><summary>Answer</summary>B) Shrinks each tree's contribution — lower η needs more trees but generalizes better</details>

**5. OOB (Out-of-Bag) error is approximately equivalent to:**
- A) Training error
- B) K-fold cross-validation error
- C) Test error on unseen data
- D) Validation error on a fixed split

<details><summary>Answer</summary>B) Leave-one-out cross-validation error (similar to K-fold CV)</details>

**6. XGBoost differs from standard gradient boosting by:**
- A) Using random forests instead of trees
- B) Adding L1/L2 regularization to the objective
- C) Only supporting regression
- D) Using only decision stumps

<details><summary>Answer</summary>B) Regularized objective (γ, λ), column subsampling, approximate split finding, sparsity awareness</details>

**7. In stacking, the meta-learner should be:**
- A) The most complex model available
- B) Same as base learners
- C) Simple (e.g., logistic regression) to avoid overfitting
- D) Always a neural network

<details><summary>Answer</summary>C) Simple — it only needs to learn optimal combination weights</details>

**8. Which ensemble method is most prone to overfitting on noisy data?**
- A) Random Forest
- B) Bagging
- C) AdaBoost
- D) Averaging

<details><summary>Answer</summary>C) AdaBoost — it focuses more and more on hard/noisy examples, potentially fitting noise</details>

**9. Feature importance in Random Forest is typically measured by:**
- A) Coefficient magnitude
- B) Mean decrease in impurity (Gini) or permutation importance
- C) Correlation with target
- D) PCA loadings

<details><summary>Answer</summary>B) Mean decrease in impurity (Gini importance) or permutation importance (accuracy drop)</details>

**10. The main difference between bagging and boosting is:**
- A) Bagging uses trees, boosting uses linear models
- B) Bagging trains independently in parallel, boosting trains sequentially
- C) Bagging is for classification only
- D) Boosting always uses random feature subsets

<details><summary>Answer</summary>B) Bagging: parallel/independent (reduce variance). Boosting: sequential/adaptive (reduce bias).</details>

---

## Coding Challenges

### Challenge 1: Implement Bagging Classifier from Scratch
```python
"""
Implement bagging with bootstrap sampling.
Use decision trees as base learners.
Include OOB error estimation.
"""
import numpy as np
from sklearn.tree import DecisionTreeClassifier

class BaggingClassifierScratch:
    def __init__(self, n_estimators=10, max_samples=1.0):
        self.n_estimators = n_estimators
        self.max_samples = max_samples
    
    def fit(self, X, y):
        self.estimators = []
        self.oob_indices = []
        n_samples = len(X)
        n_draw = int(n_samples * self.max_samples)
        
        oob_predictions = np.zeros((n_samples, len(np.unique(y))))
        oob_counts = np.zeros(n_samples)
        
        for _ in range(self.n_estimators):
            # Bootstrap sample
            indices = np.random.choice(n_samples, n_draw, replace=True)
            oob_mask = np.ones(n_samples, dtype=bool)
            oob_mask[indices] = False
            
            tree = DecisionTreeClassifier()
            tree.fit(X[indices], y[indices])
            self.estimators.append(tree)
            
            # OOB predictions
            if oob_mask.any():
                oob_pred = tree.predict_proba(X[oob_mask])
                oob_predictions[oob_mask] += oob_pred
                oob_counts[oob_mask] += 1
        
        # OOB score
        valid = oob_counts > 0
        oob_labels = np.argmax(oob_predictions[valid], axis=1)
        self.oob_score_ = np.mean(oob_labels == y[valid])
        return self
    
    def predict(self, X):
        predictions = np.array([est.predict(X) for est in self.estimators])
        return np.apply_along_axis(lambda x: np.bincount(x).argmax(), axis=0, arr=predictions)
```

### Challenge 2: Implement AdaBoost from Scratch
```python
"""
Implement AdaBoost with decision stumps.
Track sample weights, learner weights, and training error per round.
"""
import numpy as np
from sklearn.tree import DecisionTreeClassifier

class AdaBoostScratch:
    def __init__(self, n_estimators=50):
        self.n_estimators = n_estimators
    
    def fit(self, X, y):
        n = len(X)
        w = np.ones(n) / n  # uniform initial weights
        self.estimators = []
        self.alphas = []
        
        for _ in range(self.n_estimators):
            stump = DecisionTreeClassifier(max_depth=1)
            stump.fit(X, y, sample_weight=w)
            pred = stump.predict(X)
            
            # Weighted error
            err = np.sum(w * (pred != y)) / np.sum(w)
            if err >= 0.5:
                break
            
            # Learner weight
            alpha = 0.5 * np.log((1 - err) / (err + 1e-10))
            
            # Update sample weights
            w *= np.exp(-alpha * y * pred)  # assumes y in {-1, +1}
            w /= w.sum()
            
            self.estimators.append(stump)
            self.alphas.append(alpha)
        return self
    
    def predict(self, X):
        predictions = np.array([alpha * est.predict(X) for alpha, est in zip(self.alphas, self.estimators)])
        return np.sign(predictions.sum(axis=0))
```

### Challenge 3: Implement Gradient Boosting for Regression
```python
"""
Implement gradient boosting for regression (MSE loss).
Include learning rate, max_depth control, and staged predictions.
"""
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

### Challenge 4: Implement Random Forest with Feature Importance
```python
"""
Implement Random Forest with:
- Bootstrap sampling
- Random feature subsets at each split
- Gini importance and permutation importance
"""
import numpy as np
from sklearn.tree import DecisionTreeClassifier

class RandomForestScratch:
    def __init__(self, n_estimators=100, max_features='sqrt', max_depth=None):
        self.n_estimators = n_estimators
        self.max_features = max_features
        self.max_depth = max_depth
    
    def fit(self, X, y):
        n_samples, n_features = X.shape
        if self.max_features == 'sqrt':
            self.max_features_ = int(np.sqrt(n_features))
        
        self.estimators = []
        self.feature_importances_ = np.zeros(n_features)
        
        for _ in range(self.n_estimators):
            # Bootstrap
            indices = np.random.choice(n_samples, n_samples, replace=True)
            tree = DecisionTreeClassifier(
                max_depth=self.max_depth,
                max_features=self.max_features_
            )
            tree.fit(X[indices], y[indices])
            self.estimators.append(tree)
            self.feature_importances_ += tree.feature_importances_
        
        self.feature_importances_ /= self.n_estimators
        return self
    
    def predict(self, X):
        predictions = np.array([est.predict(X) for est in self.estimators])
        return np.apply_along_axis(lambda x: np.bincount(x).argmax(), axis=0, arr=predictions)
    
    def permutation_importance(self, X, y, n_repeats=10):
        baseline_acc = np.mean(self.predict(X) == y)
        importances = np.zeros(X.shape[1])
        for feat in range(X.shape[1]):
            drops = []
            for _ in range(n_repeats):
                X_perm = X.copy()
                X_perm[:, feat] = np.random.permutation(X_perm[:, feat])
                perm_acc = np.mean(self.predict(X_perm) == y)
                drops.append(baseline_acc - perm_acc)
            importances[feat] = np.mean(drops)
        return importances
```

### Challenge 5: Implement Stacking Ensemble
```python
"""
Implement a stacking ensemble with cross-validated meta-features.
Properly avoid data leakage using out-of-fold predictions.
"""
import numpy as np
from sklearn.model_selection import KFold

class StackingClassifierScratch:
    def __init__(self, base_estimators, meta_estimator, cv=5):
        self.base_estimators = base_estimators
        self.meta_estimator = meta_estimator
        self.cv = cv
    
    def fit(self, X, y):
        n_samples = len(X)
        n_base = len(self.base_estimators)
        meta_features = np.zeros((n_samples, n_base))
        
        kf = KFold(n_splits=self.cv, shuffle=True, random_state=42)
        
        # Generate out-of-fold predictions for meta-features
        for i, est in enumerate(self.base_estimators):
            for train_idx, val_idx in kf.split(X):
                clone = type(est)(**est.get_params())
                clone.fit(X[train_idx], y[train_idx])
                meta_features[val_idx, i] = clone.predict_proba(X[val_idx])[:, 1]
        
        # Train meta-learner on meta-features
        self.meta_estimator.fit(meta_features, y)
        
        # Retrain base estimators on full data
        self.fitted_base = []
        for est in self.base_estimators:
            clone = type(est)(**est.get_params())
            clone.fit(X, y)
            self.fitted_base.append(clone)
        
        return self
    
    def predict(self, X):
        meta_features = np.column_stack([
            est.predict_proba(X)[:, 1] for est in self.fitted_base
        ])
        return self.meta_estimator.predict(meta_features)
```

---

## Interview Questions

### 1. Why does Random Forest work better than a single decision tree?
<details><summary>Answer</summary>

Single decision tree: low bias, high variance (overfits).
Random Forest reduces variance through two mechanisms:
1. **Bagging:** Different bootstrap samples → diverse trees
2. **Feature randomization:** Each split sees random feature subset → decorrelates trees
3. **Averaging:** Var(avg) = ρσ²/M + (1-ρ)σ² where ρ is tree correlation

Lower ρ (more diverse trees) → lower ensemble variance. Feature randomization is the key innovation that makes RF better than plain bagging of trees.

</details>

### 2. How do you tune XGBoost? What are the most important hyperparameters?
<details><summary>Answer</summary>

**Most important (in order):**
1. `n_estimators` + `learning_rate` (inversely related — more trees with lower rate)
2. `max_depth` (3-10, controls tree complexity)
3. `min_child_weight` (minimum samples in leaf)
4. `subsample` (row sampling, 0.6-0.9)
5. `colsample_bytree` (feature sampling, 0.6-0.9)
6. `reg_alpha` (L1) and `reg_lambda` (L2)

**Strategy:** Fix n_estimators=1000 with early stopping, tune max_depth and min_child_weight first, then sampling ratios, finally regularization.

</details>

### 3. When would you use stacking over simple averaging?
<details><summary>Answer</summary>

**Use stacking when:**
- Base models have different strengths on different parts of the input space
- Base models are diverse (different algorithms)
- You have enough data to train meta-learner without overfitting
- Competition setting where marginal improvement matters

**Use simple averaging when:**
- Models are similar (all XGBoost with different seeds)
- Small dataset (stacking may overfit)
- Simplicity and interpretability matter
- In production (simpler to deploy and maintain)

</details>

### 4. Explain the difference between gradient boosting and AdaBoost.
<details><summary>Answer</summary>

**AdaBoost:**
- Reweights misclassified samples
- Each learner gets weighted vote based on accuracy
- Implicitly minimizes exponential loss
- Sensitive to noise (keeps upweighting noisy samples)

**Gradient Boosting:**
- Fits residuals (negative gradients of loss)
- Each learner added with learning rate (shrinkage)
- Works with ANY differentiable loss function
- More flexible, less sensitive to noise (with robust losses like Huber)

AdaBoost is a special case of gradient boosting with exponential loss.

</details>

### 5. How does early stopping work in boosting and why is it important?
<details><summary>Answer</summary>

**Mechanism:**
- Monitor validation metric at each boosting round
- Stop adding trees when validation metric doesn't improve for N rounds
- Use the model at the best validation round

**Why important:**
- Boosting can overfit with too many rounds (keeps fitting training data perfectly)
- Acts as regularization (limits model complexity)
- More efficient than training fixed rounds and discarding
- Automatically finds optimal n_estimators

**Implementation:** `early_stopping_rounds=50` in XGBoost with eval set.

</details>

---

## Real-World Scenarios

### Scenario 1: Click-Through Rate Prediction
**Context:** You're building a CTR prediction system for an ad platform. 100M daily impressions, 2% click rate, features include: user demographics, ad content, context (time, device, page), user history.

**Questions:**
1. Why are gradient boosted trees the industry standard for this task?
2. How do you handle the massive scale?
3. How do you deal with the 98% vs 2% imbalance?
4. How do you deploy and update the model?

<details><summary>Solution</summary>

1. **Why GBT:** Handles heterogeneous features (categorical + continuous), feature interactions automatically, robust to missing values, fast inference, well-calibrated probabilities with proper loss function.

2. **Scale handling:**
   - LightGBM with histogram-based splitting (binning continuous features)
   - Distributed training (LightGBM/XGBoost support this)
   - Feature hashing for high-cardinality categoricals
   - Subsample rows and columns per tree

3. **Imbalance:**
   - Use `scale_pos_weight = neg_count/pos_count`
   - Log-loss already handles imbalance well (probability calibration)
   - Don't use accuracy — use log-loss or AUC
   - Subsample negatives during training

4. **Deployment:**
   - Train daily/weekly on recent data (user behavior shifts)
   - A/B test new models vs current
   - Feature store for real-time feature lookup
   - Model serving: convert to ONNX or use LightGBM's native serving
   - Monitor calibration: predicted CTR should match observed CTR

</details>

### Scenario 2: Kaggle Competition Strategy
**Context:** You're competing in a tabular data competition. You have 500K training rows, 200 features, binary classification. Top solutions typically use ensembles.

**Questions:**
1. Design your ensemble strategy from scratch.
2. How do you maximize diversity among base learners?
3. When should you use blending vs stacking?
4. How do you avoid overfitting the leaderboard?

<details><summary>Solution</summary>

1. **Strategy:**
   - Level 1: Train 5-10 diverse base models (XGBoost, LightGBM, CatBoost, ExtraTrees, NN, regularized linear)
   - Level 2: Stack with logistic regression or simple NN
   - Each base model: 5-fold CV to generate OOF predictions
   - Tune each base model independently

2. **Maximizing diversity:**
   - Different algorithms (tree-based, linear, NN)
   - Different hyperparameters (shallow vs deep trees)
   - Different feature subsets
   - Different preprocessing (raw vs PCA vs target-encoded)
   - Different random seeds

3. **Blending vs Stacking:**
   - Stacking (K-fold OOF): uses all data, more complex, risk of leakage if done wrong
   - Blending (holdout): simpler, less risk, wastes some data
   - Use stacking for competitions (maximize data usage)
   - Use blending in production (simpler, more robust)

4. **Avoid leaderboard overfitting:**
   - Trust local CV more than public LB
   - Limit submissions
   - Ensure CV strategy matches train/test split (time-based? stratified?)
   - Large gap between CV and LB = data leakage or distribution shift

</details>

### Scenario 3: Medical Diagnosis Support System
**Context:** You're building a system to help doctors diagnose breast cancer from cell measurements. Dataset: 569 samples, 30 features (cell nucleus characteristics). Critical that false negatives are minimized (don't miss cancer).

**Questions:**
1. Which ensemble method and why?
2. How do you handle the small dataset?
3. How do you optimize for minimizing false negatives?
4. How do you make the model interpretable for doctors?

<details><summary>Solution</summary>

1. **Method:** Random Forest or Gradient Boosting with conservative settings:
   - RF: robust, less overfitting on small data, built-in OOB estimation
   - GBM with low learning rate + early stopping
   - Avoid deep trees (overfit on 569 samples)

2. **Small dataset handling:**
   - Repeated stratified K-fold CV (e.g., 10-fold × 5 repeats) for reliable estimation
   - Don't use large test split — maximize training data
   - Consider Leave-One-Out for final evaluation
   - Feature selection (30 features for 569 samples is borderline)
   - Regularized models preferred

3. **Minimize false negatives (maximize recall):**
   - Lower classification threshold (e.g., 0.3 instead of 0.5)
   - Use class_weight={malignant: 5, benign: 1}
   - Optimize F2-score (weights recall higher than precision)
   - Accept more false positives (additional tests) to catch all cancers
   - Set operational point on ROC curve favoring sensitivity

4. **Interpretability for doctors:**
   - SHAP values: "This patient's large cell radius (+0.3) and irregular texture (+0.2) increase cancer probability"
   - Feature importance rankings (which measurements matter most)
   - Partial dependence plots showing thresholds
   - Present as "probability of malignancy" not binary label
   - Show similar historical cases from training data (prototype examples)

</details>
