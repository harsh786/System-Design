# Problem 85: Telecom Network Analytics

### Problem 85: Telecom Network Analytics
```
ARCH: CDRs + Network probes → Kafka → Flink + Spark → Druid + Data Lake
SCALE: 10B call records/day, 1B network events/hour
USE CASES: Fraud detection, network optimization, churn prediction
STORAGE: Hot (Druid, 7 days) → Warm (Iceberg, 1 year) → Archive (Glacier)
```
