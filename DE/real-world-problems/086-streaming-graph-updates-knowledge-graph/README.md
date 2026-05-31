# Problem 86: Streaming Graph Updates (Knowledge Graph)

### Problem 86: Streaming Graph Updates (Knowledge Graph)
```
ARCH: Events → Kafka → Flink (entity extraction) → Neo4j / Neptune
CHALLENGE: Graph writes are expensive (index updates, relationship traversal)
OPTIMIZATION: Batch writes to graph (collect 1000 updates, apply together)
USE CASE: Fraud ring detection, recommendation graph, knowledge graph
```
