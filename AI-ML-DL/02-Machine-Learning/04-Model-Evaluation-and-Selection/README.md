# Model Evaluation and Selection

## Why Evaluation Matters

Proper evaluation is the difference between a model that works in a notebook and one that works in production. Without rigorous evaluation, you're just curve-fitting.

### No Free Lunch Theorem

No single model is best for all problems. Model selection requires empirical evaluation on your specific data and problem.

### Bias-Variance Decomposition

```
Expected Error = Bias² + Variance + Irreducible Noise

                    Bias²        Variance
                  ┌─────────┬─────────────┐
Simple model:     │█████████│██           │  High bias, low variance
Complex model:    │██       │█████████████│  Low bias, high variance
Right complexity: │████     │████         │  Sweet spot
                  └─────────┴─────────────┘
```

### The Evaluation Workflow

```
1. Split data properly (train/val/test or CV)
2. Choose metric aligned with business goal
3. Train and compare models with statistical rigor
4. Tune hyperparameters (without touching test set!)
5. Final evaluation on held-out test set
6. Monitor in production
```

## Index

1. [Classification Metrics](01-classification-metrics.md) - Precision, recall, F1, ROC/AUC, PR curves, multi-class
2. [Regression Metrics](02-regression-metrics.md) - MSE, RMSE, MAE, MAPE, R², residual analysis
3. [Cross-Validation](03-cross-validation.md) - K-fold, stratified, time series, nested CV, common mistakes
4. [Hyperparameter Tuning](04-hyperparameter-tuning.md) - Grid, random, Bayesian (Optuna), practical workflow
5. [Model Selection Strategy](05-model-selection-strategy.md) - Statistical comparison, complexity tradeoffs, final selection
6. [Evaluation for Production](06-evaluation-for-production.md) - A/B testing, fairness, calibration, error analysis

## Key Principle

> Your offline metric is only useful if it correlates with your business metric. Always validate the connection between what you optimize and what matters.
