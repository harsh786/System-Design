# Ensemble Methods

## Why Ensembles Work

### The Wisdom of Crowds
Combining multiple diverse models reduces error. If we have M models each with error rate ε < 0.5, making independent errors:

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

## Taxonomy

| Method | Strategy | Reduces | Base Learners |
|--------|----------|---------|---------------|
| Bagging | Parallel, average | Variance | Strong (deep trees) |
| Boosting | Sequential, correct | Bias | Weak (stumps) |
| Stacking | Layered, meta-learn | Both | Diverse |

## Index

1. [Bagging and Random Forest](01-bagging-and-random-forest.md) - Bootstrap aggregating, RF, OOB error, feature importance
2. [Boosting and Gradient Boosting](02-boosting-gradient-boosting.md) - AdaBoost, Gradient Boosting, from-scratch implementations
3. [XGBoost, LightGBM, CatBoost](03-xgboost-lightgbm-catboost.md) - Modern boosting frameworks, comparison, tuning
4. [Stacking and Blending](04-stacking-and-blending.md) - Meta-learners, CV-based stacking, practical tips
5. [Ensemble Training Guide](05-ensemble-training-guide.md) - Practical guide for building production ensembles

## Quick Comparison

| Feature | XGBoost | LightGBM | CatBoost |
|---------|---------|----------|----------|
| Tree growth | Level-wise | Leaf-wise | Symmetric |
| Speed | Medium | Fastest | Medium |
| Categorical | Manual encoding | Direct support | Best native |
| Best for | General | Large data | Categorical-heavy |

## Key Interview Insight

> The fundamental tradeoff: Bagging reduces variance (independent models averaged), Boosting reduces bias (sequential correction). Stacking can reduce both by learning optimal combination.
