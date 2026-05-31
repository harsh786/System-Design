# Problem 71: Multi-Hop Streaming Pipeline

### Problem 71: Multi-Hop Streaming Pipeline
```
ARCH: Source → Bronze stream → Silver stream → Gold stream → Serving
EACH HOP: Kafka topic → Flink job → next Kafka topic
ADVANTAGE: Each stage independently scalable, restartable
DISADVANTAGE: More Kafka topics, more operational overhead
TOTAL LATENCY: Sum of all hops (typically 5-30 seconds end-to-end)
```
