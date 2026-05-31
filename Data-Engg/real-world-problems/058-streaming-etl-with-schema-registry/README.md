# Problem 58: Streaming ETL with Schema Registry

### Problem 58: Streaming ETL with Schema Registry
```
ARCH: Producer → Schema Registry → Kafka → Consumer (validates schema)
FORMAT: Avro (schema embedded) or Protobuf (external definition)
EVOLUTION: Backward compatible changes only (add field OK, remove NO)
VALIDATION: Kafka rejects messages that don't match registered schema
```
