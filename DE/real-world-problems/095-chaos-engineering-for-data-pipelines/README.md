# Problem 95: Chaos Engineering for Data Pipelines

### Problem 95: Chaos Engineering for Data Pipelines
```
EXPERIMENTS:
  • Kill Kafka broker during peak load
  • Inject malformed data (schema violations)
  • Simulate network partition between Flink and Kafka
  • Inject clock skew (watermark issues)
  • Simulate slow sink (backpressure test)
FRAMEWORK: Custom + Chaos Monkey principles
GOAL: Verify resilience before production incidents
```
