# Multi-Region & Multi-Tenant Data Platforms - Deep Dive

## Table of Contents
1. [Multi-Region Architecture Foundations](#1-multi-region-architecture-foundations)
2. [Data Replication Strategies](#2-data-replication-strategies)
3. [CRDTs and Conflict Resolution](#3-crdts-and-conflict-resolution)
4. [Multi-Tenant Data Architecture](#4-multi-tenant-data-architecture)
5. [SLI / SLO / SLA Framework](#5-sli--slo--sla-framework)
6. [FinOps & Cost Allocation](#6-finops--cost-allocation)
7. [Capacity Planning](#7-capacity-planning)
8. [Disaster Recovery](#8-disaster-recovery)
9. [Compliance & Data Residency](#9-compliance--data-residency)
10. [Data Mesh at Scale](#10-data-mesh-at-scale)
11. [Reference Architectures](#11-reference-architectures)
12. [Architecture Decision Records (ADRs)](#12-architecture-decision-records-adrs)

---

## 1. Multi-Region Architecture Foundations

### Why Multi-Region?

```
Primary drivers:
1. Latency — serve users from nearest region (p99 < 100ms)
2. Availability — survive full region failure (99.99%+ uptime)
3. Compliance — data residency requirements (GDPR, CCPA, etc.)
4. Blast radius — limit impact of deployments/failures

Cost of multi-region:
• 2-4x infrastructure cost (minimum)
• Significant engineering complexity
• Operational overhead (monitoring, runbooks, training)
• Data consistency challenges (CAP theorem trade-offs)
```

### Topology Patterns

```
┌─────────────────────────────────────────────────────────────────┐
│  Pattern 1: Active-Passive (Hot Standby)                         │
│                                                                   │
│  ┌──────────────┐         Async Replication         ┌─────────┐ │
│  │  us-east-1   │ ─────────────────────────────────▶│us-west-2│ │
│  │  (PRIMARY)   │                                    │(STANDBY)│ │
│  │              │                                    │          │ │
│  │  All writes  │                                    │ Reads OK │ │
│  │  All reads   │                                    │ Failover │ │
│  └──────────────┘                                    └─────────┘ │
│                                                                   │
│  RPO: seconds to minutes (replication lag)                       │
│  RTO: minutes (DNS failover + warm-up)                           │
│  Cost: ~1.5-2x (standby mostly idle)                            │
│  Complexity: Low-Medium                                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Pattern 2: Active-Active (Multi-Primary)                        │
│                                                                   │
│  ┌──────────────┐      Bi-directional Sync      ┌─────────────┐│
│  │  us-east-1   │◀────────────────────────────▶ │  eu-west-1   ││
│  │              │                                │              ││
│  │  Reads +     │                                │  Reads +     ││
│  │  Writes      │                                │  Writes      ││
│  └──────┬───────┘                                └──────┬───────┘│
│         │              ┌─────────────┐                  │        │
│         └─────────────▶│  ap-south-1 │◀─────────────────┘        │
│                        │             │                            │
│                        │ Reads +     │                            │
│                        │ Writes      │                            │
│                        └─────────────┘                            │
│                                                                   │
│  RPO: 0 (eventual consistency) or seconds (async)                │
│  RTO: 0 (no failover needed — all active)                        │
│  Cost: 3x+ (full infra in each region)                           │
│  Complexity: Very High (conflict resolution required)            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  Pattern 3: Follow-the-Sun (Partitioned Active-Active)           │
│                                                                   │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────┐       │
│  │  us-east-1   │    │  eu-west-1  │    │ ap-south-1   │       │
│  │              │    │             │    │              │       │
│  │ US customers │    │ EU customers│    │ APAC customers│       │
│  │ (primary)    │    │ (primary)   │    │ (primary)    │       │
│  └──────────────┘    └─────────────┘    └──────────────┘       │
│                                                                   │
│  Each region OWNS its partition of data (no conflicts)           │
│  Cross-region reads for global aggregation (async)               │
│  RPO: 0 for owned data, seconds for global view                 │
│  RTO: minutes (re-route affected partition)                      │
│  Cost: ~2-3x (but efficient — each region only owns subset)     │
│  Complexity: Medium-High                                         │
└─────────────────────────────────────────────────────────────────┘
```

### AWS Multi-Region Building Blocks

| Service | Multi-Region Feature | Notes |
|---------|---------------------|-------|
| Route 53 | Latency/failover routing | Health checks trigger failover |
| DynamoDB | Global Tables (active-active) | Last-writer-wins, sub-second replication |
| S3 | Cross-Region Replication (CRR) | Async, 15-min SLA |
| Aurora | Global Database (1 writer, 5 read regions) | < 1s replication lag |
| MSK | Cluster replication (MirrorMaker 2) | Topic-level, async |
| ElastiCache | Global Datastore (Redis) | < 1s cross-region |
| Secrets Manager | Multi-region secrets | Automatic replication |
| CloudFront | Global CDN | Edge caching |
| Global Accelerator | Anycast IP routing | TCP/UDP acceleration |

---

## 2. Data Replication Strategies

### Kafka Cross-Region Replication

```
┌────────────────────────────────────────────────────────────────┐
│              Kafka Multi-Region Patterns                         │
│                                                                  │
│  Pattern A: MirrorMaker 2 (Active-Passive)                      │
│  ┌──────────┐     MM2 (topic replication)     ┌──────────┐    │
│  │ Cluster A│ ─────────────────────────────▶  │ Cluster B│    │
│  │(us-east) │                                  │(us-west) │    │
│  └──────────┘                                  └──────────┘    │
│  • Topic: "orders" → replicated as "us-east.orders"           │
│  • Consumer offsets translated automatically                    │
│  • Failover: consumers switch to Cluster B                      │
│                                                                  │
│  Pattern B: Stretch Cluster (Synchronous)                       │
│  ┌──────────┐        Raft (ISR across AZs)    ┌──────────┐    │
│  │ Broker 1 │◀──────────────────────────────▶ │ Broker 2 │    │
│  │ (AZ-a)   │                                  │ (AZ-b)   │    │
│  └──────────┘                                  └──────────┘    │
│  • min.insync.replicas spans AZs (NOT regions — too slow)      │
│  • Use ONLY within single region across AZs                     │
│                                                                  │
│  Pattern C: Confluent Cluster Linking / Redpanda Remote Read   │
│  • Logical replication of topics (byte-for-byte mirror)         │
│  • Consumer offsets preserved (no re-keying)                    │
│  • Sub-second lag (better than MM2)                             │
└────────────────────────────────────────────────────────────────┘
```

### MirrorMaker 2 Configuration

```properties
# mm2.properties (production config)
clusters = us-east, us-west
us-east.bootstrap.servers = kafka-us-east:9092
us-west.bootstrap.servers = kafka-us-west:9092

# Replication flow
us-east->us-west.enabled = true
us-east->us-west.topics = orders, payments, events
us-east->us-west.topics.exclude = .*\.internal, __.*

# Sync consumer group offsets (for failover)
us-east->us-west.sync.group.offsets.enabled = true
us-east->us-west.sync.group.offsets.interval.seconds = 10

# Emit checkpoints (for offset translation)
us-east->us-west.emit.checkpoints.enabled = true
us-east->us-west.emit.checkpoints.interval.seconds = 30

# Replication factor for mirrored topics
replication.factor = 3

# Key configs for production
offset-syncs.topic.replication.factor = 3
heartbeats.topic.replication.factor = 3
checkpoints.topic.replication.factor = 3

# Tuning
tasks.max = 10
producer.batch.size = 524288
producer.linger.ms = 100
consumer.fetch.min.bytes = 1048576
```

### S3 Cross-Region Replication for Data Lakes

```json
{
  "Role": "arn:aws:iam::123456789:role/s3-crr-role",
  "Rules": [
    {
      "ID": "ReplicateGoldLayer",
      "Status": "Enabled",
      "Priority": 1,
      "Filter": {
        "Prefix": "gold/"
      },
      "Destination": {
        "Bucket": "arn:aws:s3:::lake-eu-west-1",
        "StorageClass": "STANDARD_IA",
        "ReplicationTime": {
          "Status": "Enabled",
          "Time": { "Minutes": 15 }
        },
        "Metrics": {
          "Status": "Enabled",
          "EventThreshold": { "Minutes": 15 }
        }
      },
      "DeleteMarkerReplication": { "Status": "Enabled" }
    }
  ]
}
```

### DynamoDB Global Tables

```python
import boto3

# Create global table (already exists in us-east-1)
dynamodb = boto3.client('dynamodb', region_name='us-east-1')

# Add replica in eu-west-1
dynamodb.update_table(
    TableName='orders',
    ReplicaUpdates=[
        {
            'Create': {
                'RegionName': 'eu-west-1',
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'customer-index',
                        'ProvisionedThroughputOverride': {
                            'ReadCapacityUnits': 100
                        }
                    }
                ]
            }
        }
    ]
)

# Conflict resolution: Last Writer Wins (LWW)
# DynamoDB uses item-level timestamps
# If two regions write same item simultaneously:
#   - Higher timestamp wins
#   - No application-level conflict handling needed
#   - BUT: "last" is wall-clock based (can be problematic)

# Best practices for Global Tables:
# 1. Design for eventual consistency (reads may be stale by ~1s)
# 2. Use conditional writes to prevent lost updates
# 3. Avoid hot keys (same item written from multiple regions)
# 4. Use region-prefixed IDs to avoid conflicts:
#    us-east-1: order_id = "use1_" + uuid
#    eu-west-1: order_id = "euw1_" + uuid
```

---

## 3. CRDTs and Conflict Resolution

### CRDT Fundamentals

```
CRDT = Conflict-free Replicated Data Type

Key insight: Design data structures where ALL concurrent operations
can be merged automatically WITHOUT conflicts.

Mathematical property: operations form a semilattice
  • Associative: merge(merge(a,b), c) = merge(a, merge(b,c))
  • Commutative: merge(a,b) = merge(b,a)
  • Idempotent: merge(a,a) = a

If your data type has these properties, replicas can sync in ANY order
and always converge to the same state. No coordination needed!
```

### Common CRDTs for Data Platforms

```
┌──────────────────────────────────────────────────────────────────┐
│  CRDT Type          │  Use Case in Data Platform                  │
├─────────────────────┼─────────────────────────────────────────────┤
│  G-Counter          │  Event counts, page views, metrics          │
│  (Grow-only)        │  Each region increments its own slot        │
│                     │  Total = sum of all slots                    │
├─────────────────────┼─────────────────────────────────────────────┤
│  PN-Counter         │  Stock levels, balances (inc + dec)         │
│  (Positive-Negative)│  Two G-Counters: one for adds, one for     │
│                     │  removes. Value = P - N                      │
├─────────────────────┼─────────────────────────────────────────────┤
│  LWW-Register       │  User profiles, config values               │
│  (Last-Writer-Wins) │  Attach timestamp to each write             │
│                     │  Highest timestamp wins (DynamoDB uses this) │
├─────────────────────┼─────────────────────────────────────────────┤
│  OR-Set             │  Tags, labels, set membership               │
│  (Observed-Remove)  │  Add/remove elements; concurrent add+remove │
│                     │  resolved as "add wins"                      │
├─────────────────────┼─────────────────────────────────────────────┤
│  MV-Register        │  Shopping cart, concurrent edits             │
│  (Multi-Value)      │  Keeps ALL concurrent values; app resolves  │
└─────────────────────┴─────────────────────────────────────────────┘
```

### G-Counter Example

```python
# G-Counter: each node maintains its own counter
# Total = sum of all node counters

class GCounter:
    def __init__(self, node_id, num_nodes):
        self.node_id = node_id
        self.counts = [0] * num_nodes  # one slot per node
    
    def increment(self, amount=1):
        """Only increment OWN slot"""
        self.counts[self.node_id] += amount
    
    def value(self):
        """Total is sum of all slots"""
        return sum(self.counts)
    
    def merge(self, other):
        """Take max of each slot (idempotent, commutative, associative)"""
        for i in range(len(self.counts)):
            self.counts[i] = max(self.counts[i], other.counts[i])

# Usage in multi-region event counting:
# Region us-east-1 (node 0): counter.increment() on each event
# Region eu-west-1 (node 1): counter.increment() on each event
# Periodically sync: region_a.merge(region_b) and vice versa
# Both converge to same total regardless of sync order
```

### Conflict Resolution Strategies

```
Strategy 1: Last-Writer-Wins (LWW)
  Pros: Simple, automatic, no app logic needed
  Cons: Can lose updates (last write blindly overwrites)
  Used by: DynamoDB Global Tables, Cassandra
  Best for: Idempotent writes, user profiles, preferences

Strategy 2: Application-Level Resolution
  Pros: Domain-specific merge logic, no data loss
  Cons: Complex to implement, must handle all edge cases
  Used by: Custom implementations
  Best for: Financial transactions, inventory

Strategy 3: CRDTs (Automatic Merge)
  Pros: Mathematically guaranteed convergence, no conflicts
  Cons: Limited data types, higher storage overhead
  Used by: Redis CRDB, Riak, custom systems
  Best for: Counters, sets, registers

Strategy 4: Region Ownership (Avoid Conflicts)
  Pros: No conflicts possible (each region owns its data)
  Cons: Cross-region reads may be stale
  Used by: Most practical systems (follow-the-sun)
  Best for: User data (user belongs to one region)

Strategy 5: Operational Transform / Event Sourcing
  Pros: Full history preserved, can replay and resolve
  Cons: Complex implementation, growing event log
  Used by: Google Docs, collaborative editing
  Best for: Collaborative systems, audit-heavy domains
```

---

## 4. Multi-Tenant Data Architecture

### Tenancy Models

```
┌──────────────────────────────────────────────────────────────────┐
│  Model 1: Shared Everything (Pool)                                │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Single Database / Single Schema / Single Table             │  │
│  │                                                              │  │
│  │  orders:                                                     │  │
│  │  | tenant_id | order_id | amount | ...                      │  │
│  │  | tenant_A  | 001      | 100    |                          │  │
│  │  | tenant_B  | 002      | 200    |                          │  │
│  │  | tenant_A  | 003      | 150    |                          │  │
│  │                                                              │  │
│  │  Isolation: Row-level (WHERE tenant_id = ?)                 │  │
│  │  Pros: Cheapest, easiest to manage, best resource util      │  │
│  │  Cons: Noisy neighbor, compliance risk, hard to customize   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Model 2: Shared Database, Separate Schema                        │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Database: analytics                                         │  │
│  │  ├── Schema: tenant_a                                       │  │
│  │  │   ├── orders                                             │  │
│  │  │   └── customers                                          │  │
│  │  ├── Schema: tenant_b                                       │  │
│  │  │   ├── orders                                             │  │
│  │  │   └── customers                                          │  │
│  │                                                              │  │
│  │  Isolation: Schema-level (SET search_path = 'tenant_a')     │  │
│  │  Pros: Better isolation, per-tenant DDL, easier compliance  │  │
│  │  Cons: Schema explosion, DDL drift between tenants          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Model 3: Separate Database per Tenant (Silo)                     │
│                                                                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                    │
│  │ DB:       │  │ DB:       │  │ DB:       │                    │
│  │ tenant_a  │  │ tenant_b  │  │ tenant_c  │                    │
│  │           │  │           │  │           │                    │
│  │ orders    │  │ orders    │  │ orders    │                    │
│  │ customers │  │ customers │  │ customers │                    │
│  └───────────┘  └───────────┘  └───────────┘                    │
│                                                                    │
│  Isolation: Full (separate compute + storage)                     │
│  Pros: Complete isolation, per-tenant scaling, compliance easy    │
│  Cons: Most expensive, operational overhead, cross-tenant hard   │
└──────────────────────────────────────────────────────────────────┘
```

### Multi-Tenant Data Lake (S3 + Iceberg)

```
s3://data-lake-production/
├── raw/
│   ├── tenant_id=acme/
│   │   ├── year=2024/month=01/
│   │   │   └── *.parquet
│   ├── tenant_id=globex/
│   │   └── ...
├── silver/
│   ├── tenant_id=acme/
│   │   └── orders/  (Iceberg table)
│   │       ├── metadata/
│   │       └── data/
│   ├── tenant_id=globex/
│   │   └── ...
├── gold/
│   └── ... (same pattern)

Access control (Lake Formation):
  • Role: tenant_acme_analyst
  • Permissions: SELECT on database=silver, table=orders
  • Row filter: tenant_id = 'acme'
  • Column mask: CASE WHEN role='admin' THEN ssn ELSE '***' END
```

### Tenant Isolation in Kafka

```
Strategy 1: Topic-per-tenant
  Topic: orders.tenant_a, orders.tenant_b
  Pros: Complete isolation, per-tenant retention/config
  Cons: Topic explosion (1000 tenants × 50 topics = 50K topics)
  Limit: Kafka handles ~100K topics per cluster (but perf degrades)

Strategy 2: Shared topic with tenant header
  Topic: orders (single topic, all tenants)
  Header: X-Tenant-ID: tenant_a
  Pros: Simple, efficient, fewer topics
  Cons: Noisy neighbor (one tenant's burst affects all)
  Mitigation: Per-tenant quotas (Kafka quota configs)

Strategy 3: Shared topic with partitioning by tenant
  Topic: orders (hash tenant_id to partition)
  Pros: Tenant data co-located in partition (efficient reads)
  Cons: Uneven distribution if tenants vary in size

Production recommendation:
  • Small tenants (< 1K events/sec): Shared topic + tenant header
  • Medium tenants: Shared topic + dedicated partitions
  • Large/enterprise tenants: Dedicated topics (or dedicated cluster)
```

```properties
# Kafka per-tenant quotas
# Limit tenant_a to 10 MB/s produce, 20 MB/s consume
kafka-configs.sh --alter --add-config \
  'producer_byte_rate=10485760,consumer_byte_rate=20971520' \
  --entity-type users --entity-name tenant_a
```

### Noisy Neighbor Prevention

```
┌──────────────────────────────────────────────────────────────────┐
│              Noisy Neighbor Mitigation Stack                       │
│                                                                    │
│  Layer 1: API Gateway / Rate Limiting                             │
│  ├── Per-tenant request rate limits                               │
│  ├── Per-tenant concurrent query limits                           │
│  └── Token bucket with burst allowance                            │
│                                                                    │
│  Layer 2: Query Engine Isolation                                  │
│  ├── Separate compute pools per tenant tier                       │
│  │   (e.g., Redshift WLM queues, Spark fair scheduler)           │
│  ├── Query timeout per tenant                                     │
│  └── Memory limits per query                                      │
│                                                                    │
│  Layer 3: Storage I/O Isolation                                   │
│  ├── S3 request rate limits per prefix (partition by tenant)     │
│  ├── EBS IOPS allocation per tenant workload                     │
│  └── Caching tiers (hot tenants get dedicated cache)             │
│                                                                    │
│  Layer 4: Network Isolation                                       │
│  ├── VPC per tenant (silo model)                                 │
│  ├── Security groups / NACLs                                      │
│  └── Bandwidth limits per tenant                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Redshift Multi-Tenant WLM

```sql
-- Create WLM queues for tenant tiers
-- In Redshift parameter group:
-- Queue 1: Enterprise tenants (priority)
-- Queue 2: Standard tenants
-- Queue 3: Free-tier tenants (background)

-- Enterprise: 60% memory, 10 concurrent queries, no timeout
-- Standard: 30% memory, 5 concurrent queries, 300s timeout
-- Free-tier: 10% memory, 2 concurrent queries, 60s timeout

-- Route queries by user group
CREATE GROUP enterprise_users;
CREATE GROUP standard_users;
CREATE GROUP free_users;

-- Assign tenant DB users to groups
ALTER GROUP enterprise_users ADD USER tenant_acme;
ALTER GROUP standard_users ADD USER tenant_smallco;

-- Query queue assignment (automatic based on user group)
-- Enterprise users → Queue 1
-- Standard users → Queue 2
-- Free users → Queue 3
```

---

## 5. SLI / SLO / SLA Framework

### Definitions

```
SLI (Service Level Indicator)
  = Measurable metric that indicates service health
  = "What we measure"
  Example: 99.2% of queries completed in < 500ms

SLO (Service Level Objective)
  = Target value for an SLI
  = "What we aim for" (internal promise)
  Example: 99.5% of queries must complete in < 500ms over 30 days

SLA (Service Level Agreement)
  = Legal contract with consequences for missing SLO
  = "What we promise externally" (with penalties)
  Example: 99.9% availability; breach = service credits

Golden rule: SLI ≥ SLO > SLA
  SLI tracks reality
  SLO is stricter than SLA (internal buffer)
  SLA is what you legally commit to
```

### Data Platform SLIs

```
┌──────────────────────────────────────────────────────────────────┐
│  Category          │  SLI                    │  Measurement       │
├────────────────────┼─────────────────────────┼────────────────────┤
│  Freshness         │  Data arrival latency   │  time(available)   │
│                    │                          │  - time(produced)  │
│                    │  Pipeline lag            │  Kafka consumer    │
│                    │                          │  lag (seconds)     │
├────────────────────┼─────────────────────────┼────────────────────┤
│  Completeness      │  Record delivery rate   │  records_delivered │
│                    │                          │  / records_produced│
│                    │  Schema conformance      │  valid_records /   │
│                    │                          │  total_records     │
├────────────────────┼─────────────────────────┼────────────────────┤
│  Correctness       │  Data quality score     │  passed_checks /   │
│                    │                          │  total_checks      │
│                    │  Duplicate rate          │  unique_records /  │
│                    │                          │  total_records     │
├────────────────────┼─────────────────────────┼────────────────────┤
│  Availability      │  Query success rate     │  successful_queries│
│                    │                          │  / total_queries   │
│                    │  Pipeline success rate   │  successful_runs / │
│                    │                          │  total_runs        │
├────────────────────┼─────────────────────────┼────────────────────┤
│  Performance       │  Query latency (p99)    │  99th percentile   │
│                    │                          │  response time     │
│                    │  Throughput              │  events/sec        │
│                    │                          │  processed         │
└────────────────────┴─────────────────────────┴────────────────────┘
```

### SLO Implementation

```yaml
# slo-definitions.yaml (machine-readable SLO spec)
slos:
  - name: data-freshness-gold-layer
    description: "Gold layer tables updated within SLO"
    sli:
      type: freshness
      measurement: "max(current_time - last_update_time) per table"
      source: prometheus
      query: |
        max_over_time(
          data_freshness_seconds{layer="gold"}[5m]
        )
    objective:
      target: 99.5  # percentage of time within threshold
      threshold: 900  # 15 minutes max staleness
      window: 30d  # rolling 30-day window
    alerting:
      burn_rate_short: 14.4  # 1h window (exhausts budget in 5h)
      burn_rate_long: 6.0    # 6h window (exhausts budget in 5 days)
    owner: data-platform-team
    tier: 1

  - name: query-latency-p99
    description: "Analytics query latency under SLO"
    sli:
      type: latency
      measurement: "p99 query duration"
      source: prometheus
      query: |
        histogram_quantile(0.99,
          rate(query_duration_seconds_bucket{service="analytics"}[5m])
        )
    objective:
      target: 99.0
      threshold: 5.0  # 5 seconds p99
      window: 30d
    alerting:
      burn_rate_short: 14.4
      burn_rate_long: 6.0
    owner: analytics-team
    tier: 2
```

### Error Budget

```
Error budget = 1 - SLO target (over the window)

Example: SLO = 99.5% freshness over 30 days
  Error budget = 0.5% of 30 days = 0.005 × 30 × 24 × 60 = 216 minutes
  You can be "out of SLO" for up to 216 minutes per month

Error budget policy:
  Budget > 50% remaining → normal development velocity
  Budget 25-50% remaining → reduce risky changes, increase testing
  Budget < 25% remaining → freeze non-critical deployments
  Budget exhausted → all hands on reliability, no new features

Burn rate alerting:
  Fast burn (14.4x): budget exhausted in ~5 hours → page immediately
  Slow burn (6x): budget exhausted in ~5 days → alert during business hours
  Very slow burn (3x): budget exhausted in ~10 days → ticket
```

---

## 6. FinOps & Cost Allocation

### Cost Attribution Model

```
┌──────────────────────────────────────────────────────────────────┐
│                Data Platform Cost Model                            │
│                                                                    │
│  Direct Costs (easy to attribute):                                │
│  ├── Compute (EMR, Redshift, Flink) → by job/query/tenant       │
│  ├── Storage (S3, EBS) → by prefix/tenant_id partition          │
│  └── Data transfer → by source/destination                       │
│                                                                    │
│  Shared Costs (need allocation strategy):                         │
│  ├── Kafka cluster → by topic (bytes produced/consumed)          │
│  ├── Metadata services → even split or by catalog size           │
│  ├── Monitoring stack → even split                                │
│  └── Platform team salaries → even split or by tickets           │
│                                                                    │
│  Allocation methods:                                              │
│  1. Direct measurement (preferred): actual resource usage         │
│  2. Proportional: share based on data volume or query count      │
│  3. Even split: divide equally among tenants/teams               │
│  4. Tiered: base cost + usage-based overage                      │
└──────────────────────────────────────────────────────────────────┘
```

### AWS Cost Tagging Strategy

```json
{
  "TaggingPolicy": {
    "required_tags": [
      {"key": "team", "values": ["data-eng", "analytics", "ml", "platform"]},
      {"key": "env", "values": ["prod", "staging", "dev"]},
      {"key": "tenant", "values": ["*"]},
      {"key": "pipeline", "values": ["*"]},
      {"key": "cost-center", "values": ["CC-100", "CC-200", "CC-300"]}
    ],
    "enforcement": "SCP denies resource creation without required tags"
  }
}
```

```python
# Cost allocation script (daily)
import boto3
from datetime import datetime, timedelta

ce = boto3.client('ce')

# Get cost by tenant tag
response = ce.get_cost_and_usage(
    TimePeriod={
        'Start': (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
        'End': datetime.now().strftime('%Y-%m-%d')
    },
    Granularity='DAILY',
    Metrics=['UnblendedCost'],
    GroupBy=[
        {'Type': 'TAG', 'Key': 'tenant'},
        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
    ],
    Filter={
        'Tags': {
            'Key': 'env',
            'Values': ['prod']
        }
    }
)

# Output: daily cost per tenant per service
# tenant=acme, S3: $45/day, EMR: $120/day, Redshift: $80/day
# tenant=globex, S3: $12/day, EMR: $30/day, Redshift: $20/day
```

### Cost Optimization Strategies

```
┌────────────────────────────────────────────────────────────────────┐
│  Strategy            │  Savings  │  Implementation                  │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  S3 Intelligent      │  20-40%   │  Lifecycle policy on all         │
│  Tiering             │           │  infrequently accessed data      │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Spot Instances      │  60-90%   │  EMR task nodes, Flink TMs,      │
│  (EMR/Flink)         │           │  non-critical batch jobs         │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Reserved Capacity   │  30-60%   │  Redshift RA3, MSK, stable       │
│                      │           │  baseline compute                 │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Right-sizing        │  20-50%   │  Downsize over-provisioned       │
│                      │           │  clusters (use CloudWatch)       │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Partition pruning   │  50-90%   │  Proper partitioning (date,      │
│  (query cost)        │           │  tenant) → scan less data        │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Columnar format     │  50-80%   │  Parquet/ORC instead of JSON/CSV │
│  + compression       │  (scan)   │  → less bytes scanned           │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  TTL / data          │  30-60%   │  Auto-delete raw data after      │
│  lifecycle           │  (storage)│  90 days, archive after 1 year  │
├──────────────────────┼───────────┼──────────────────────────────────┤
│  Query result cache  │  40-70%   │  Cache frequent queries (Cube,   │
│                      │  (compute)│  Redshift cache, Athena cache)  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 7. Capacity Planning

### Methodology

```
Step 1: Measure Current State
  • Data volume: GB ingested/day, growth rate
  • Query patterns: QPS, query types, latency distribution
  • Resource utilization: CPU, memory, disk, network
  • Peak vs average: understand burst patterns

Step 2: Project Growth
  • Business growth: new tenants, new data sources
  • Organic growth: existing sources increasing volume
  • Seasonal patterns: Black Friday, year-end, etc.
  • Plan for 18-24 months ahead

Step 3: Model Resource Needs
  • Compute: f(data_volume, query_complexity, concurrency)
  • Storage: f(data_volume, retention, replication_factor)
  • Network: f(data_volume, cross-region_replication, API_traffic)

Step 4: Build in Headroom
  • Target utilization: 60-70% (not 90%+)
  • Reserve 30-40% headroom for spikes
  • Auto-scaling for elastic workloads
```

### Kafka Capacity Model

```python
# Kafka cluster sizing calculator

class KafkaCapacityModel:
    def __init__(self):
        # Input parameters
        self.msg_rate_per_sec = 100_000  # messages/sec (peak)
        self.avg_msg_size_bytes = 1024   # 1 KB average
        self.replication_factor = 3
        self.retention_days = 7
        self.consumer_groups = 5         # number of consumer groups
        
    def compute(self):
        # Throughput
        ingress_mbps = (self.msg_rate_per_sec * self.avg_msg_size_bytes) / 1_000_000
        total_write_mbps = ingress_mbps * self.replication_factor
        total_read_mbps = ingress_mbps * self.consumer_groups
        
        # Storage
        daily_gb = (self.msg_rate_per_sec * self.avg_msg_size_bytes * 86400) / 1e9
        total_storage_gb = daily_gb * self.retention_days * self.replication_factor
        
        # Broker count (rule of thumb: 100 MB/s per broker)
        brokers_for_throughput = max(
            total_write_mbps / 100,
            total_read_mbps / 100
        )
        
        # Storage per broker
        storage_per_broker = total_storage_gb / max(brokers_for_throughput, 3)
        
        return {
            "ingress_mbps": ingress_mbps,
            "total_write_mbps": total_write_mbps,
            "total_read_mbps": total_read_mbps,
            "daily_data_gb": daily_gb,
            "total_storage_gb": total_storage_gb,
            "min_brokers": int(max(brokers_for_throughput, 3)),
            "storage_per_broker_gb": int(storage_per_broker),
            "recommended_instance": self._recommend_instance(ingress_mbps)
        }
    
    def _recommend_instance(self, ingress_mbps):
        if ingress_mbps < 50:
            return "kafka.m5.large (2 vCPU, 8 GB)"
        elif ingress_mbps < 200:
            return "kafka.m5.2xlarge (8 vCPU, 32 GB)"
        else:
            return "kafka.m5.4xlarge (16 vCPU, 64 GB)"

# Example: 100K msgs/sec × 1KB = 100 MB/s ingress
# With RF=3: 300 MB/s total writes → 3 brokers minimum
# Storage: 100 MB/s × 86400s × 7 days × 3 RF = ~181 TB
# Recommendation: 6 brokers × 30 TB each (kafka.m5.4xlarge + st1)
```

### Auto-Scaling Patterns

```yaml
# EMR Managed Scaling (for Spark batch jobs)
ManagedScalingPolicy:
  ComputeLimits:
    UnitType: InstanceFleetUnits
    MinimumCapacityUnits: 16    # baseline (always running)
    MaximumCapacityUnits: 256   # max scale-out
    MaximumOnDemandCapacityUnits: 32  # rest = Spot
    MaximumCoreCapacityUnits: 32      # core nodes (HDFS)

# Flink auto-scaling (reactive mode on K8s)
# flinkdeploy.yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: streaming-pipeline
spec:
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    # Reactive mode: Flink adjusts parallelism to available TMs
    scheduler-mode: reactive
  podTemplate:
    spec:
      containers:
        - name: flink-main-container
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
---
# HPA scales TaskManagers based on Kafka lag
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flink-tm-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: streaming-pipeline-taskmanager
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: External
      external:
        metric:
          name: kafka_consumer_lag
          selector:
            matchLabels:
              consumer_group: flink-pipeline
        target:
          type: AverageValue
          averageValue: "10000"  # scale up if lag > 10K per TM
```

---

## 8. Disaster Recovery

### DR Tiers

```
┌────────────────────────────────────────────────────────────────────┐
│  Tier  │  RPO        │  RTO         │  Strategy      │  Cost      │
├────────┼─────────────┼──────────────┼────────────────┼────────────┤
│  1     │  0 (zero    │  < 1 min     │  Active-Active │  4x+       │
│        │  data loss) │  (instant)   │  Multi-region  │            │
├────────┼─────────────┼──────────────┼────────────────┼────────────┤
│  2     │  < 5 min    │  < 15 min    │  Hot standby + │  2-3x      │
│        │             │              │  async repl    │            │
├────────┼─────────────┼──────────────┼────────────────┼────────────┤
│  3     │  < 1 hour   │  < 4 hours   │  Warm standby  │  1.5-2x    │
│        │             │              │  + periodic    │            │
│        │             │              │  backup        │            │
├────────┼─────────────┼──────────────┼────────────────┼────────────┤
│  4     │  < 24 hours │  < 24 hours  │  Cold backup   │  1.1-1.3x  │
│        │             │              │  + restore     │            │
└────────┴─────────────┴──────────────┴────────────────┴────────────┘
```

### Data Platform DR Runbook

```
┌──────────────────────────────────────────────────────────────────┐
│  Component       │  Primary        │  DR Strategy                 │
├──────────────────┼─────────────────┼──────────────────────────────┤
│  Kafka/MSK       │  us-east-1      │  MM2 to us-west-2 (RPO ~10s)│
│  S3 Data Lake    │  us-east-1      │  CRR to us-west-2 (RPO ~15m)│
│  Iceberg catalog │  Glue (regional)│  Nessie replication or       │
│                  │                  │  Glue catalog export/import  │
│  Redshift        │  us-east-1      │  Cross-region snapshot copy  │
│                  │                  │  (RPO = snapshot interval)   │
│  DynamoDB        │  us-east-1      │  Global Tables (RPO ~1s)     │
│  Airflow/MWAA    │  us-east-1      │  DAGs in Git → redeploy      │
│                  │                  │  (RTO = deploy time ~10min)  │
│  Flink state     │  S3 checkpoints │  CRR checkpoints to DR region│
│                  │                  │  Resume from last checkpoint │
└──────────────────┴─────────────────┴──────────────────────────────┘
```

### Failover Procedure

```
# Automated failover sequence (triggered by health check failure)

Phase 1: Detection (< 1 minute)
  • Route 53 health checks detect primary region failure
  • CloudWatch alarms fire (multi-signal: API, DB, Kafka)
  • PagerDuty alert sent to on-call

Phase 2: Decision (1-5 minutes)
  • Automated: if health check fails for > 60s, auto-failover
  • Manual: if ambiguous (partial failure), human decision
  • Check: verify it's not a monitoring false positive

Phase 3: DNS Failover (< 1 minute)
  • Route 53 failover record switches to DR region
  • CloudFront origin switches to DR endpoints
  • TTL: 60s (clients pick up change quickly)

Phase 4: Data Pipeline Failover (5-15 minutes)
  • Kafka consumers switch to DR cluster (using translated offsets)
  • Flink jobs restart from last S3 checkpoint in DR region
  • Airflow DAGs triggered in DR MWAA environment
  • Verify: data flowing through DR pipelines

Phase 5: Verification (5-10 minutes)
  • Run data quality checks on DR region data
  • Verify dashboard queries returning results
  • Confirm consumer lag is decreasing
  • Notify stakeholders: "Operating in DR mode"

Phase 6: Failback (hours to days — carefully!)
  • Ensure primary region fully recovered
  • Reverse-replicate data produced during DR period
  • Switch traffic back (with same DNS failover)
  • Post-incident review within 48 hours
```

### Chaos Engineering for DR

```python
# chaos-experiment.py — Validate DR readiness
# Run monthly in staging, quarterly in prod (with change window)

experiments = [
    {
        "name": "kafka_broker_failure",
        "action": "terminate 1 of 3 MSK brokers",
        "expected": "producers/consumers reconnect within 30s, no data loss",
        "rollback": "broker auto-recovers (managed service)"
    },
    {
        "name": "az_failure_simulation",
        "action": "block all traffic to one AZ via security groups",
        "expected": "services fail over to remaining AZs within 60s",
        "rollback": "remove security group rules"
    },
    {
        "name": "s3_prefix_throttle",
        "action": "generate 5000+ req/s to single S3 prefix",
        "expected": "503 SlowDown errors handled with exponential backoff",
        "rollback": "stop load generator"
    },
    {
        "name": "full_region_failover",
        "action": "simulate region failure via Route 53 health check override",
        "expected": "DR region serving traffic within RTO (15 min)",
        "rollback": "restore Route 53 health check"
    }
]
```

---

## 9. Compliance & Data Residency

### Data Classification

```
┌──────────────────────────────────────────────────────────────────┐
│  Classification    │  Examples           │  Handling Rules         │
├────────────────────┼─────────────────────┼─────────────────────────┤
│  Public            │  Product catalog,   │  No restrictions        │
│                    │  public APIs        │  Can replicate anywhere │
├────────────────────┼─────────────────────┼─────────────────────────┤
│  Internal          │  Aggregated metrics,│  Keep within org        │
│                    │  non-PII analytics  │  Encrypt at rest        │
├────────────────────┼─────────────────────┼─────────────────────────┤
│  Confidential      │  PII (name, email), │  Encrypt everywhere     │
│                    │  financial data     │  Access logging required │
│                    │                     │  Data residency applies  │
├────────────────────┼─────────────────────┼─────────────────────────┤
│  Restricted        │  SSN, health data,  │  Strongest controls     │
│                    │  payment cards      │  Column-level encryption │
│                    │                     │  Masking for most users  │
│                    │                     │  NEVER leave jurisdiction│
└────────────────────┴─────────────────────┴─────────────────────────┘
```

### GDPR Data Residency Implementation

```
Requirement: EU personal data must remain in EU region

Implementation:

1. Data routing at ingestion:
   ┌────────────┐         ┌─────────────────────────────────┐
   │ API Gateway│────────▶│ Lambda: classify & route         │
   │            │         │                                   │
   │            │         │ if user.region == 'EU':           │
   │            │         │   → kafka-eu-west-1              │
   │            │         │ else:                             │
   │            │         │   → kafka-us-east-1              │
   └────────────┘         └─────────────────────────────────┘

2. Storage isolation:
   s3://lake-eu-west-1/  ← EU data (bucket in eu-west-1)
   s3://lake-us-east-1/  ← US data (bucket in us-east-1)
   
   S3 bucket policy:
   {
     "Condition": {
       "StringNotEquals": {
         "aws:RequestedRegion": "eu-west-1"
       }
     },
     "Effect": "Deny"  ← Prevents cross-region access
   }

3. Cross-region analytics (aggregated only):
   EU region: compute PII-free aggregates locally
   Replicate ONLY aggregates (no PII) to global analytics region
   
4. Right to erasure (GDPR Article 17):
   • Maintain user_id → data_locations mapping
   • On deletion request:
     - Delete from transactional DB
     - Queue Kafka tombstone
     - Mark Iceberg rows for deletion (merge-on-read)
     - Compact/rewrite affected Parquet files
     - Purge from caches (Redis, Cube pre-aggs)
     - Audit log: deletion completed at timestamp
```

### Column-Level Encryption

```python
# AWS KMS + client-side encryption for sensitive columns
import boto3
from aws_encryption_sdk import (
    EncryptionSDKClient,
    StrictAwsKmsMasterKeyProvider,
)

kms_key_arn = "arn:aws:kms:eu-west-1:123456789:key/eu-pii-key"
provider = StrictAwsKmsMasterKeyProvider(key_ids=[kms_key_arn])
client = EncryptionSDKClient()

def encrypt_pii(value: str, context: dict) -> bytes:
    """Encrypt PII with encryption context for audit"""
    ciphertext, _ = client.encrypt(
        source=value.encode(),
        key_provider=provider,
        encryption_context={
            "tenant": context["tenant_id"],
            "field": context["field_name"],
            "classification": "restricted"
        }
    )
    return ciphertext

def decrypt_pii(ciphertext: bytes) -> str:
    """Decrypt — only principals with KMS Decrypt permission succeed"""
    plaintext, header = client.decrypt(
        source=ciphertext,
        key_provider=provider
    )
    return plaintext.decode()

# In Spark pipeline:
# df = df.withColumn("email_encrypted", encrypt_udf(col("email")))
# df = df.drop("email")  # never store plaintext PII
```

---

## 10. Data Mesh at Scale

### Domain Ownership Model

```
┌──────────────────────────────────────────────────────────────────┐
│                    Data Mesh Organization                          │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  Orders Domain   │  │  Payments Domain │  │  Users Domain │  │
│  │                  │  │                  │  │               │  │
│  │  Owner: Commerce │  │  Owner: Fintech  │  │  Owner: IAM   │  │
│  │  Team            │  │  Team            │  │  Team         │  │
│  │                  │  │                  │  │               │  │
│  │  Data Products:  │  │  Data Products:  │  │  Data Products│  │
│  │  • fct_orders    │  │  • fct_payments  │  │  • dim_users  │  │
│  │  • dim_products  │  │  • fct_refunds   │  │  • user_events│  │
│  │                  │  │                  │  │               │  │
│  │  SLO: 99.5%     │  │  SLO: 99.9%     │  │  SLO: 99.5%  │  │
│  │  freshness      │  │  (financial)     │  │  freshness    │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Self-Serve Data Platform                        │  │
│  │                                                              │  │
│  │  • Infra provisioning (Terraform modules)                   │  │
│  │  • Data product templates (cookiecutter)                    │  │
│  │  • Schema registry (centralized)                            │  │
│  │  • Discovery catalog (DataHub / OpenMetadata)               │  │
│  │  • Observability (built-in SLI tracking)                    │  │
│  │  • Access control (OPA / Lake Formation)                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Federated Governance                            │  │
│  │                                                              │  │
│  │  • Global policies (encryption, retention, PII handling)   │  │
│  │  • Domain-local policies (access, quality rules)           │  │
│  │  • Interoperability standards (Iceberg, Avro, naming)      │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Data Product Specification

```yaml
# data-product.yaml (standardized contract)
apiVersion: dataproduct/v1
kind: DataProduct
metadata:
  name: fct_orders
  domain: commerce
  owner: commerce-data-team
  tier: 1  # critical

spec:
  description: "Fact table of all completed orders"
  
  schema:
    format: iceberg
    location: s3://lake-prod/gold/commerce/fct_orders/
    catalog: glue
    columns:
      - name: order_id
        type: string
        description: "Unique order identifier"
        pii: false
      - name: customer_id
        type: string
        description: "Customer FK"
        pii: true
        classification: confidential
      - name: amount
        type: decimal(10,2)
        description: "Order total in USD"
      - name: order_date
        type: timestamp
        description: "Order creation time"
        partition_key: true
        granularity: day
  
  slo:
    freshness:
      target: 99.5%
      threshold: 15 minutes
    completeness:
      target: 99.9%
      description: "< 0.1% records dropped"
    availability:
      target: 99.5%
      description: "Queryable via Athena/Redshift"
  
  access:
    public: false
    consumers:
      - team: analytics
        level: read
      - team: ml-platform
        level: read
        columns_excluded: [customer_id]  # PII masked
  
  lineage:
    sources:
      - name: orders_cdc
        type: kafka_topic
        topic: commerce.public.orders
      - name: dim_products
        type: data_product
        domain: commerce
    
  quality:
    checks:
      - type: not_null
        columns: [order_id, amount, order_date]
      - type: unique
        columns: [order_id]
      - type: range
        column: amount
        min: 0
        max: 1000000
      - type: freshness
        column: order_date
        max_age: 15 minutes
```

---

## 11. Reference Architectures

### Global E-Commerce Data Platform

```
┌─────────────────────────────────────────────────────────────────────┐
│  GLOBAL E-COMMERCE DATA PLATFORM (Multi-Region, Multi-Tenant)       │
│                                                                       │
│  ┌─── US Region (us-east-1) ─────────────────────────────────────┐  │
│  │                                                                 │  │
│  │  ┌─────────┐    ┌──────────┐    ┌────────────────────────┐   │  │
│  │  │ App DB  │CDC▶│ MSK      │───▶│ Flink (Streaming ETL)  │   │  │
│  │  │ (Aurora)│    │(Kafka)   │    │                          │   │  │
│  │  └─────────┘    └────┬─────┘    │ • Dedup + enrich        │   │  │
│  │                      │          │ • Route by tenant/region │   │  │
│  │                      │MM2       │ • Real-time aggregates   │   │  │
│  │                      │          └───────────┬──────────────┘   │  │
│  │                      │                      │                   │  │
│  │                      ▼                      ▼                   │  │
│  │               ┌──────────┐    ┌──────────────────────────┐    │  │
│  │               │ DR copy  │    │ S3 Data Lake (Iceberg)    │    │  │
│  │               │(us-west) │    │                            │    │  │
│  │               └──────────┘    │ raw/ → silver/ → gold/    │    │  │
│  │                               └───────────┬──────────────┘    │  │
│  │                                           │                    │  │
│  │         ┌─────────────────────────────────┼─────────────┐     │  │
│  │         ▼                                 ▼             ▼     │  │
│  │  ┌────────────┐  ┌────────────────┐  ┌──────────────┐       │  │
│  │  │ Redshift   │  │ RisingWave     │  │ Feature Store│       │  │
│  │  │ (batch BI) │  │ (real-time MV) │  │ (Feast/SM)   │       │  │
│  │  └─────┬──────┘  └───────┬────────┘  └──────────────┘       │  │
│  │        │                  │                                    │  │
│  │        ▼                  ▼                                    │  │
│  │  ┌──────────────────────────────────┐                         │  │
│  │  │     Cube (Semantic Layer)         │                         │  │
│  │  │     + Superset (Dashboards)       │                         │  │
│  │  └──────────────────────────────────┘                         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─── EU Region (eu-west-1) ────────────────────────────────────┐  │
│  │  (Same architecture, EU data only — GDPR compliant)           │  │
│  │  Cross-region: only aggregated, non-PII metrics replicated    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─── Global Services ──────────────────────────────────────────┐  │
│  │  • DataHub (metadata catalog, cross-region discovery)         │  │
│  │  • Dagster (orchestration, cross-region DAGs)                 │  │
│  │  • Prometheus + Grafana (unified observability)               │  │
│  │  • OPA (policy engine, federated governance)                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Real-Time Analytics SaaS Platform

```
┌─────────────────────────────────────────────────────────────────────┐
│  MULTI-TENANT REAL-TIME ANALYTICS PLATFORM                           │
│                                                                       │
│  Tenant Isolation: Shared infra + logical isolation                  │
│  Tier Model: Free → Pro → Enterprise (dedicated resources)           │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Ingestion Layer                                                 ││
│  │                                                                   ││
│  │  ┌──────────┐     ┌──────────────────┐     ┌────────────────┐  ││
│  │  │ API GW + │────▶│ Redpanda         │────▶│ Flink          │  ││
│  │  │ Rate Limit│     │ (per-tenant      │     │ (tenant-aware  │  ││
│  │  │ (per-tenant)│   │  quotas)         │     │  routing)      │  ││
│  │  └──────────┘     └──────────────────┘     └───────┬────────┘  ││
│  │                                                     │            ││
│  └─────────────────────────────────────────────────────┼────────────┘│
│                                                         │             │
│  ┌──────────────────────────────────────────────────────┼───────────┐│
│  │  Storage Layer                                       │           ││
│  │                                                      ▼           ││
│  │  ┌──────────────────────────────────────────────────────┐       ││
│  │  │  S3 Data Lake                                         │       ││
│  │  │  s3://lake/tenant_id=<id>/table=<name>/part=<date>/  │       ││
│  │  └──────────────────────────────────────────────────────┘       ││
│  │                                                                   ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      ││
│  │  │  ClickHouse  │  │  DynamoDB    │  │  ElastiCache     │      ││
│  │  │  (analytics  │  │  (metadata,  │  │  (query cache,   │      ││
│  │  │   queries)   │  │   configs)   │  │   sessions)      │      ││
│  │  └──────────────┘  └──────────────┘  └──────────────────┘      ││
│  └───────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Serving Layer                                                   ││
│  │                                                                   ││
│  │  ┌──────────────────┐     ┌─────────────────────────────────┐  ││
│  │  │  Cube             │────▶│  Customer-facing dashboards      │  ││
│  │  │  (per-tenant      │     │  (embedded analytics via iframe) │  ││
│  │  │   pre-aggs)      │     └─────────────────────────────────┘  ││
│  │  └──────────────────┘                                            ││
│  └───────────────────────────────────────────────────────────────────┘│
│                                                                       │
│  Tenant tiers:                                                       │
│  Free:       shared ClickHouse, 1-day retention, 10 QPS limit       │
│  Pro:        shared ClickHouse, 90-day retention, 100 QPS limit     │
│  Enterprise: dedicated ClickHouse, unlimited retention, no limit    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 12. Architecture Decision Records (ADRs)

### ADR Template

```markdown
# ADR-XXX: [Decision Title]

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing and/or doing?

## Consequences
What becomes easier or more difficult because of this change?

## Alternatives Considered
What other options were evaluated? Why were they rejected?
```

### Example ADR: Multi-Region Strategy

```markdown
# ADR-007: Active-Passive Multi-Region with Follow-the-Sun Data Ownership

## Status
Accepted (2024-03-15)

## Context
- Growing EU customer base requires GDPR-compliant data residency
- Current single-region (us-east-1) has no DR capability
- Business requires < 15 min RTO for critical pipelines
- Budget constraint: cannot afford full active-active (4x cost)

## Decision
Adopt a **hybrid active-passive + follow-the-sun** architecture:
1. US data remains primary in us-east-1
2. EU data is primary in eu-west-1 (GDPR compliance)
3. Each region has hot standby in secondary region within same geography
4. Cross-region: only non-PII aggregates replicated (for global dashboards)

Implementation:
- Kafka: MM2 replication within geography (us-east → us-west, eu-west → eu-central)
- S3: CRR within geography + selective CRR of aggregates cross-geography
- Compute: Flink/Spark deployed in each primary region
- DR failover: automated Route 53 failover within geography

## Consequences
### Positive
- GDPR compliance achieved (EU data stays in EU)
- DR capability within geography (RPO < 5 min, RTO < 15 min)
- Cost: ~2.5x (not 4x of full active-active)

### Negative
- Global dashboards have eventual consistency (up to 15 min delay)
- Cross-region queries not possible (must pre-aggregate)
- Operational complexity: 4 clusters to manage (2 per geography)

## Alternatives Considered
1. **Full active-active (all regions)**: Rejected — 4x cost, CRDT complexity
2. **Single region + backup**: Rejected — doesn't solve GDPR
3. **AWS Outposts in EU**: Rejected — limited services, high cost
```

### Example ADR: Tenancy Model

```markdown
# ADR-012: Shared-Infrastructure Multi-Tenancy with Logical Isolation

## Status
Accepted (2024-06-01)

## Context
- SaaS platform serves 500+ tenants (growing 10x in 2 years)
- Top 5 tenants generate 60% of data volume
- Need to balance cost efficiency with isolation guarantees
- Enterprise customers require dedicated resources

## Decision
**Tiered multi-tenancy model:**

| Tier | Kafka | Storage | Compute | Isolation |
|------|-------|---------|---------|-----------|
| Free | Shared topic + header | Shared prefix | Shared pool | Row-level |
| Pro | Shared topic + partition | Tenant prefix | Shared pool + limits | Prefix + quota |
| Enterprise | Dedicated topic | Dedicated prefix | Dedicated cluster | Full |

Key implementation details:
- All tiers share same Flink cluster (with per-tenant resource quotas)
- Lake Formation provides column/row-level access control
- API Gateway enforces per-tenant rate limits
- Monitoring: per-tenant cost tracking via AWS tags

## Consequences
### Positive
- 10x tenant growth without 10x cost increase
- Enterprise customers get isolation they require
- Clear upgrade path (Free → Pro → Enterprise)

### Negative
- Complex quota management system needed
- Noisy neighbor risk for Free/Pro tiers
- Must maintain per-tier configuration (operational overhead)
- Enterprise tier requires dedicated IaC modules
```

---

## Summary: Key Principles for Multi-Region Multi-Tenant Platforms

```
1. Design for failure: every component will fail; plan recovery
2. Data ownership: assign each piece of data to ONE primary region/tenant
3. Avoid conflicts: partition data ownership > resolve conflicts
4. Cost awareness: tag everything, measure everything, allocate fairly
5. SLOs drive architecture: define SLOs first, then design to meet them
6. Compliance by design: data classification + residency from day 1
7. Self-serve platform: domain teams own their data products
8. Automate DR: untested DR is not DR; run chaos experiments monthly
9. Tiered isolation: match isolation level to tenant needs/spend
10. Observe everything: you can't manage what you can't measure
```
