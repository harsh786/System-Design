# Problem 119: Design an Event Sourcing & CQRS Platform

## Problem Statement

Design a platform that uses Event Sourcing as the primary persistence mechanism and
CQRS (Command Query Responsibility Segregation) to separate write and read models.
The system must support reliable event storage, projection building, and temporal queries.

## Key Challenges

1. **Event Store**: Append-only storage with strict ordering guarantees per aggregate,
   optimistic concurrency control, and efficient stream reads.
2. **Event Versioning/Schema Evolution**: Handle schema changes in events over time
   using upcasting, weak schema, or versioned deserializers.
3. **Projection/Read-Model Building**: Build and maintain multiple materialized views
   from event streams with at-least-once or exactly-once guarantees.
4. **Snapshotting for Long Aggregates**: Periodically snapshot aggregate state to avoid
   replaying thousands of events on every load.
5. **Exactly-Once Processing**: Ensure event handlers and projections process each
   event exactly once despite failures and retries.
6. **Saga/Process Manager Coordination**: Orchestrate long-running business processes
   across multiple aggregates with compensation logic.
7. **Replay and Temporal Queries**: Support full event replay for rebuilding projections
   and point-in-time queries for auditing and debugging.

## Scale Requirements

- 1M+ events per second ingestion rate
- Petabytes of event history retained indefinitely
- Hundreds of concurrent projections consuming event streams
- Sub-second read-model staleness for critical projections
- Support for thousands of distinct event types
- Event replay at 10x+ ingestion speed for rebuilds

## Expected Discussion Areas

- Event store implementation (purpose-built vs adapted databases)
- Subscription models (catch-up, persistent, competing consumers)
- Idempotency keys and deduplication strategies
- CQRS read-model technology selection per query pattern
- Event archival, compaction, and tiered storage
