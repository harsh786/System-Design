# Event-Driven Architecture, Kafka, and Streaming

_Split from `../world_class_pro_architect_master_roadmap.md`. The original source file is intentionally untouched._

---

# 11. Event-Driven Architecture Roadmap

## Core Concepts

- Event.
- Command.
- Query.
- Topic.
- Queue.
- Stream.
- Partition.
- Offset.
- Consumer group.
- Ordering.
- Replay.
- Retention.
- Compaction.
- Schema registry.
- Dead-letter queue.
- Retry topic.
- Idempotent consumer.
- Exactly-once processing limitations.

## Kafka Deep Dive

### Learn

- Brokers.
- Topics.
- Partitions.
- Replication factor.
- Leader and follower replicas.
- ISR.
- Producer acknowledgements.
- Idempotent producer.
- Transactions.
- Consumer groups.
- Offset commits.
- Rebalancing.
- Partition key choice.
- Consumer lag.
- Retention.
- Compaction.
- Kafka Connect.
- Kafka Streams.
- Schema Registry.

### Design Rules

- Choose partition key based on ordering and load distribution.
- Do not require global ordering unless absolutely necessary.
- Treat consumers as at-least-once by default.
- Make consumers idempotent.
- Use DLQs with runbooks.
- Version events carefully.
- Include trace IDs and correlation IDs.
- Monitor lag and processing errors.

## Event Schema Template

```json
{
  "eventId": "uuid",
  "eventType": "OrderCreated",
  "eventVersion": 1,
  "occurredAt": "timestamp",
  "producer": "order-service",
  "correlationId": "trace-or-business-id",
  "tenantId": "tenant-id",
  "payload": {}
}
```

---



### Kafka Architect Depth

- Topic design: business event boundaries, partition count, retention, compaction.
- Partition key: ordering requirement vs load distribution.
- Producer: idempotence, acks, retries, batching, compression, linger, transactions.
- Consumer: groups, rebalancing, offset commit strategy, lag, idempotency.
- Delivery model: at-least-once by default; exactly-once requires constraints and careful sinks.
- Schema Registry: compatibility modes, schema evolution, field defaults.
- Kafka Connect: source/sink connectors, task scaling, offset storage, DLQs.
- MirrorMaker/Cluster Linking concepts for cross-region replication.
- Operations: broker sizing, ISR, under-replicated partitions, controller, disk, network, quotas.


