# Problem 11: Click-Stream Analytics

### Problem 11: Click-Stream Analytics
```
SCALE: 100K clicks/sec, session analysis
ARCH: JS SDK → API → Kafka → Flink (sessionization) → Druid + Delta Lake
WHY FLINK: Session windows with gap detection
WHY DRUID: Sub-second slicing by dimension (page, device, campaign)
```
