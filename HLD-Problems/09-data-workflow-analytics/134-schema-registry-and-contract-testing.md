# Problem 134: Design Schema Registry & Contract Testing Platform

## Problem Statement

Design a centralized schema registry and contract testing platform that manages schema
evolution for event-driven architectures and APIs. The system ensures producers and
consumers remain compatible through automated compatibility checking, enforces governance
policies for schema changes, and integrates with streaming platforms (Kafka), REST APIs,
and gRPC services to prevent breaking changes from reaching production.

## Key Challenges

1. **Schema Storage**: Store versioned schemas in multiple formats (Avro, Protobuf,
   JSON Schema) with efficient retrieval, normalization, and deduplication using
   content-based fingerprinting.
2. **Compatibility Checking**: Implement backward, forward, full, and transitive
   compatibility modes with clear violation reporting and suggested fixes.
3. **Schema Evolution Policies**: Define and enforce organizational rules about what
   schema changes are permissible (required fields, type changes, enum additions).
4. **Producer-Consumer Contract Validation**: Allow consumers to publish their usage
   contracts (which fields they read) and validate that producer changes don't break
   any active consumer contract.
5. **Breaking Change Detection**: Automatically detect breaking changes in CI/CD
   pipelines before deployment, with diff visualization and impact analysis.
6. **Schema Governance Workflow**: Approval workflows for schema changes with owner
   notification, review process, and audit trail.
7. **Integration with Kafka/API/gRPC**: Seamlessly integrate with Kafka serializers,
   REST API validation middleware, and gRPC service definitions.
8. **Dead Letter Handling**: Route messages that fail deserialization to dead letter
   queues with schema mismatch diagnostics and replay capability.

## Scale Requirements

- 100,000+ registered schemas with millions of versions
- 1M+ messages/sec validated against schemas in real-time
- Schema retrieval latency <5ms (p99)
- Compatibility check latency <100ms
- Integration with 10,000+ Kafka topics
- Support for 1,000+ producer/consumer teams
- Zero-downtime schema registry deployments

## Expected Discussion Areas

- Schema normalization and canonical form computation
- Compatibility algorithm implementation details
- Consumer-driven contract testing workflow
- Schema caching at serializer/deserializer level
- Handling schema references and compositions
- Migration strategies for incompatible changes
- Schema registry HA and disaster recovery
