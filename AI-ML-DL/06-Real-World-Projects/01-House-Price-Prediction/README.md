# Project 1: House Price Prediction

## What You'll Learn
- End-to-end ML regression pipeline
- Exploratory Data Analysis (EDA)
- Feature engineering and selection
- Comparing multiple models (Linear, Ridge, Lasso, Random Forest, Gradient Boosting)
- Cross-validation and hyperparameter tuning

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌────────────────┐    ┌────────────┐
│ Data Loading│───►│ EDA &        │───►│ Feature        │───►│ Model      │
│ (sklearn)   │    │ Visualization│    │ Engineering    │    │ Training   │
└─────────────┘    └──────────────┘    └────────────────┘    └────────────┘
                                                                    │
                                                                    ▼
                                       ┌────────────────┐    ┌────────────┐
                                       │ Model          │◄───│ Evaluation │
                                       │ Comparison     │    │ & Metrics  │
                                       └────────────────┘    └────────────┘
```

## Prerequisites

```bash
pip install numpy pandas scikit-learn matplotlib seaborn
```

## How to Run

```bash
python house_price_prediction.py
```

## Expected Output
- Dataset statistics and correlations
- Model comparison table (MAE, RMSE, R²)
- Best model identification with feature importances

## Extension Ideas
- Add polynomial features
- Try stacking/blending ensembles
- Deploy as a REST API
- Add SHAP explanations
