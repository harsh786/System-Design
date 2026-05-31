# Problem 6: Log Analytics Platform (ELK at Scale)

### Problem 6: Log Analytics Platform (ELK at Scale)
```
SCALE: 10 TB/day of logs from 10,000 microservices
ARCH: Filebeat → Kafka → Flink (enrichment) → Elasticsearch + S3
WHY: ES for search (<3s), S3 for long-term compliance
SCALABILITY: ES 100 nodes, hot-warm-cold node types
```
