# Problem 97: Time-Series Anomaly Detection at Scale

### Problem 97: Time-Series Anomaly Detection at Scale
```
ARCH: Metrics → Kafka → Flink (windowed stats) → Anomaly models → Alert
ALGORITHMS:
  • Statistical: Z-score, IQR, Grubbs test
  • ML: Isolation Forest, Autoencoders, LSTM
  • Seasonal: STL decomposition + residual analysis
SCALE: 10M time series, check every minute = 10M anomaly checks/min
OPTIMIZATION: Pre-filter (only check if deviation > 2σ from baseline)
```
