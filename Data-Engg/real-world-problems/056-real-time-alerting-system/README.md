# Problem 56: Real-Time Alerting System

### Problem 56: Real-Time Alerting System
```
ARCH: Metrics → Kafka → Flink (CEP rules) → Alert Router → PagerDuty/Slack
CEP: Complex Event Processing (detect patterns across events)
EXAMPLES: "3 failures in 5 minutes from same service" → P1 alert
DEDUP: Suppress duplicate alerts (5-minute silence after first alert)
```
