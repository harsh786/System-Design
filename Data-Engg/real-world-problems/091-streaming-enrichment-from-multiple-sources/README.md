# Problem 91: Streaming Enrichment from Multiple Sources

### Problem 91: Streaming Enrichment from Multiple Sources
```
PATTERN: Temporal join (enrich stream with latest dimension data)
EXAMPLE: Order event + latest customer profile + latest product info
ARCH: Kafka (orders) + Kafka (customers CDC) → Flink temporal join → Enriched
WHY TEMPORAL: Customer info changes over time; use version valid at event time
```
