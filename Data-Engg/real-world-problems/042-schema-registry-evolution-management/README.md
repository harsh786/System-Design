# Problem 42: Schema Registry & Evolution Management

### Problem 42: Schema Registry & Evolution Management
```
ARCH: Confluent Schema Registry + compatibility modes
MODES: BACKWARD (new reader, old data) / FORWARD (old reader, new data)
ENFORCEMENT: Kafka rejects messages failing schema validation
MIGRATION: Dual-write during schema transition period
```
