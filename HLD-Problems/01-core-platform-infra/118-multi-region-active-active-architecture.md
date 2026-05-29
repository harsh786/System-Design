# Problem 118: Design Multi-Region Active-Active Architecture

## Problem Statement

Design a multi-region active-active system where all regions serve read and write
traffic simultaneously. The architecture must handle data consistency, conflict
resolution, and seamless failover while minimizing user-perceived latency.

## Key Challenges

1. **Data Replication (Sync vs Async)**: Choose replication strategies per data type—
   synchronous for critical data, asynchronous for eventual consistency tolerant data.
2. **Conflict Resolution**: Handle concurrent writes to the same data across regions
   using CRDTs, Last-Writer-Wins (LWW), or application-level merge logic.
3. **Request Routing**: Route users to optimal regions based on latency, geography,
   load, and data locality considerations.
4. **Failover and Disaster Recovery**: Automatically detect region failures and redirect
   traffic with minimal disruption and data loss.
5. **Split-Brain Handling**: Detect and recover from network partitions where regions
   operate independently with diverging state.
6. **Consistency Models Across Regions**: Support tunable consistency—strong within
   region, eventual across regions—with clear guarantees per operation.
7. **Session Affinity with Region Awareness**: Maintain session state accessible across
   regions while preferring local reads for performance.

## Scale Requirements

- 5+ regions globally distributed
- RPO (Recovery Point Objective): near-zero for critical data
- RTO (Recovery Time Objective): <30 seconds
- Millions of concurrent users across all regions
- Cross-region replication lag <500ms for async paths
- Support for data residency and sovereignty requirements

## Expected Discussion Areas

- Global load balancing and DNS-based routing (Anycast, GeoDNS)
- Conflict-free replicated data types (CRDTs) vs operational transforms
- Consensus protocols for cross-region coordination
- Regional data ownership vs shared-nothing architecture
- Observability and consistency verification across regions
