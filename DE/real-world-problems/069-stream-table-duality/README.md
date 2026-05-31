# Problem 69: Stream-Table Duality

### Problem 69: Stream-Table Duality
```
CONCEPT: A stream and a table are two views of the same data
TABLE → STREAM: CDC captures changes as a stream
STREAM → TABLE: Aggregate stream into latest state (materialized view)
KAFKA LOG COMPACTION: Turns topic into a table (keeps latest value per key)
APPLICATION: Kafka Streams KTable, Flink dynamic tables
```
