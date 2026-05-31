# Problem 37: Time-Series Forecasting Pipeline

### Problem 37: Time-Series Forecasting Pipeline
```
ARCH: Historical → Feature Engineering (Spark) → Model Training → Serving
MODELS: Prophet, DeepAR, N-BEATS, Temporal Fusion Transformer
SCALE: 1M time series (one per SKU), retrain weekly
SERVING: Pre-compute forecasts, store in Redis for instant lookup
```
