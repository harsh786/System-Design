# Problem 13: Feature Store for ML

### Problem 13: Feature Store for ML
```
SCALE: 10,000 features, 100ms serving SLA, 50K requests/sec
ARCH: Offline (Spark → Iceberg) + Online (Flink → Redis)
WHY DUAL STORE: Training needs historical, serving needs real-time
POINT-IN-TIME: Prevent data leakage in training
```
