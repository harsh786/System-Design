# Project 5: Time Series Forecasting

## What You'll Learn
- Time series decomposition (trend, seasonality, residuals)
- ARIMA/SARIMA modeling
- LSTM for sequence prediction
- Evaluation with proper time-series splits
- Comparing statistical vs deep learning approaches

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌───────────────────────────┐
│ Synthetic    │───►│ Decomposition│───►│ Approach 1: ARIMA/SARIMA  │
│ Time Series  │    │ & Analysis   │    ├───────────────────────────┤
│ (with trend  │    └──────────────┘    │ Approach 2: LSTM          │
│  + season)   │                        └───────────────────────────┘
└──────────────┘                                     │
                                              ┌──────▼──────┐
                                              │  Compare &  │
                                              │  Forecast   │
                                              └─────────────┘
```

## Prerequisites

```bash
pip install numpy pandas scikit-learn statsmodels torch
```

## How to Run

```bash
python time_series_forecast.py
```

## Expected Output
- Time series statistics and stationarity test
- ARIMA model summary and forecast
- LSTM training progress and predictions
- Comparison of both approaches (MAE, RMSE)

## Extension Ideas
- Prophet for business forecasting
- Transformer-based models (Temporal Fusion Transformer)
- Multi-variate time series
- Anomaly detection in time series
