# Amazon DynamoDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Model & Key Design](#data-model--key-design)
3. [Consistency & Transactions](#consistency--transactions)
4. [Capacity & Scaling](#capacity--scaling)
5. [Secondary Indexes (GSI/LSI)](#secondary-indexes-gsilsi)
6. [DynamoDB Streams & CDC](#dynamodb-streams--cdc)
7. [Advanced Patterns](#advanced-patterns)
8. [Staff Architect Interview Questions](#staff-architect-interview-questions)
9. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### DynamoDB Internals
```
┌───────────────────────────────────────────────────────┐
│              DynamoDB Architecture                      │
│                                                         │
│  ┌────────────────────────────────┐                    │
│  │      Request Router            │ ← All API calls    │
│  │  (Authentication, Routing)     │                    │
│  └─────────────┬──────────────────┘                    │
│                │                                        │
│  ┌─────────────┴──────────────────┐                    │
│  │      Storage Nodes             │                    │
│  │  (B-Tree per partition)        │                    │
│  │                                │                    │
│  │  Partition 1: [PK range A-M]   │                    │
│  │  ├── Leader replica            │                    │
│  │  ├── Follower replica          │                    │
│  │  └── Follower replica          │                    │
│  │                                │                    │
│  │  Partition 2: [PK range N-Z]   │                    │
│  │  ├── Leader replica            │                    │
│  │  ├── Follower replica          │                    │
│  │  └── Follower replica          │                    │
│  └────────────────────────────────┘                    │
│                                                         │
│  - Partitions: Hash-based distribution                 │
│  - Each partition: 10GB data, 3000 RCU, 1000 WCU      │
│  - Paxos-based replication (3 replicas per partition)  │
│  - Automatic splitting when limits exceeded            │
└───────────────────────────────────────────────────────┘
```

### Key Properties
```
- Fully managed (no servers to provision)
- Single-digit millisecond latency at any scale
- Automatic partitioning and rebalancing
- Built-in replication (3 AZs)
- Consistent performance regardless of table size
- Horizontal scaling (no practical upper limit)
- Pay-per-request or provisioned capacity
```

---

## Data Model & Key Design

### Primary Key Options
```
Option 1: Simple Primary Key (Partition Key only)
┌───────────────────────────────┐
│ Table: Users                   │
│ PK: user_id (partition key)    │
│                                │
│ user_id=123: {name: "Alice"}   │
│ user_id=456: {name: "Bob"}     │
└───────────────────────────────┘
- Use for: Unique items accessed by single key
- Distribution: Each item on different partition (ideally)

Option 2: Composite Primary Key (Partition Key + Sort Key)
┌────────────────────────────────────────────────┐
│ Table: UserOrders                               │
│ PK: user_id (partition key) + order_id (sort)   │
│                                                  │
│ Partition user_id=123:                           │
│   order_id=001: {amount: 99.99, date: "..."}    │
│   order_id=002: {amount: 149.50, date: "..."}   │
│   order_id=003: {amount: 29.99, date: "..."}    │
│                                                  │
│ Partition user_id=456:                           │
│   order_id=001: {amount: 200.00, date: "..."}   │
└────────────────────────────────────────────────┘
- Sort key enables range queries within partition
- Sorted: Begins_with, Between, >, <, >=, <=
```

### Single Table Design Pattern
```
Instead of multiple tables, use ONE table with overloaded keys:

┌──────────────────────────────────────────────────────────────┐
│ Table: Application                                            │
│ PK: pk (partition key) + sk (sort key)                       │
├─────────────────┬───────────────────┬────────────────────────┤
│ pk              │ sk                │ Attributes             │
├─────────────────┼───────────────────┼────────────────────────┤
│ USER#123        │ PROFILE           │ name, email, age       │
│ USER#123        │ ORDER#001         │ total, status, date    │
│ USER#123        │ ORDER#002         │ total, status, date    │
│ USER#123        │ ADDRESS#HOME      │ street, city, zip      │
│ ORDER#001       │ ITEM#A            │ product, qty, price    │
│ ORDER#001       │ ITEM#B            │ product, qty, price    │
│ PRODUCT#WIDGET  │ PRODUCT#WIDGET    │ name, price, category  │
│ PRODUCT#WIDGET  │ REVIEW#001        │ rating, text, user     │
└─────────────────┴───────────────────┴────────────────────────┘

Access patterns served:
- Get user profile: pk=USER#123, sk=PROFILE
- Get user's orders: pk=USER#123, sk begins_with("ORDER#")
- Get order items: pk=ORDER#001, sk begins_with("ITEM#")
- Get product reviews: pk=PRODUCT#WIDGET, sk begins_with("REVIEW#")
```

### Partition Key Design (Avoiding Hot Partitions)
```
Bad partition keys:
- date (all writes to today's partition)
- status (low cardinality: "active"/"inactive")
- country (uneven distribution)

Good partition keys:
- user_id (high cardinality, even distribution)
- order_id (unique per item)
- device_id + date (compound for time-series)

Write sharding for hot partitions:
- Append random suffix: "PRODUCT#WIDGET#3" (0-9 suffix)
- Read requires scatter-gather across all suffixes
- Only use for extremely hot keys (>1000 WCU per item)

Adaptive capacity (automatic since 2019):
- DynamoDB automatically redistributes capacity
- Isolates hot items to dedicated partitions
- "Burst capacity" absorbed from underutilized partitions
```

---

## Consistency & Transactions

### Read Consistency
```
Eventually Consistent Read (default):
- May not reflect recent writes
- 0.5 RCU per 4KB (half the cost)
- Reads from any of 3 replicas

Strongly Consistent Read:
- Reflects all successful writes
- 1 RCU per 4KB
- Reads from leader replica

Transactional Read:
- 2 RCU per 4KB (2x strongly consistent)
- Part of TransactWriteItems/TransactGetItems
```

### DynamoDB Transactions
```python
# TransactWriteItems (up to 100 items, 4MB)
client.transact_write_items(
    TransactItems=[
        {
            'Put': {
                'TableName': 'Orders',
                'Item': {'pk': 'ORDER#789', 'sk': 'METADATA', 'total': 99.99},
                'ConditionExpression': 'attribute_not_exists(pk)'
            }
        },
        {
            'Update': {
                'TableName': 'Accounts',
                'Key': {'pk': 'ACCOUNT#123', 'sk': 'BALANCE'},
                'UpdateExpression': 'SET balance = balance - :amount',
                'ConditionExpression': 'balance >= :amount',
                'ExpressionAttributeValues': {':amount': 99.99}
            }
        }
    ]
)

# Properties:
# - All-or-nothing (ACID across items/tables)
# - Serializable isolation
# - Optimistic concurrency (condition checks)
# - Max 100 items per transaction
# - 4MB total size limit
# - 2x capacity consumption
# - Cannot target same item twice in one transaction
```

---

## Capacity & Scaling

### Capacity Modes
```
On-Demand (pay-per-request):
- No capacity planning
- Pay per read/write request
- Auto-scales instantly (up to 40K RCU/WCU, soft limit)
- Best for: Unpredictable workloads, new tables, development
- Cost: ~6x more expensive at steady-state high volume

Provisioned:
- Set RCU/WCU (with auto-scaling)
- Reserved capacity available (1-year commit: 60% savings)
- Auto-scaling: Target utilization (e.g., 70%)
- Best for: Predictable workloads, cost optimization
- Burst capacity: Consume unused capacity from other partitions

Capacity calculations:
- 1 RCU = 1 strongly consistent read/sec for items up to 4KB
- 1 WCU = 1 write/sec for items up to 1KB
- Transactional: 2x cost
- Eventually consistent: 0.5x read cost
```

### DAX (DynamoDB Accelerator)
```
In-memory cache layer:
┌─────────┐     ┌─────────┐     ┌───────────┐
│  App    │────→│  DAX    │────→│ DynamoDB  │
│         │     │ Cluster │     │           │
│         │     │ (cache) │     │           │
└─────────┘     └─────────┘     └───────────┘

- Microsecond read latency (vs millisecond from DynamoDB)
- Write-through cache (writes go to DynamoDB, cached on read)
- Item cache + Query cache
- Same API as DynamoDB (drop-in replacement)
- Multi-AZ deployment
- Good for: Read-heavy, latency-sensitive workloads
- Not for: Write-heavy, strongly consistent reads (DAX is eventually consistent)
```

---

## Secondary Indexes (GSI/LSI)

### Global Secondary Index (GSI)
```
- Completely separate partition structure
- Different partition key and/or sort key
- Eventually consistent only (async replication from base table)
- Can be created/deleted anytime
- Separate provisioned capacity (own RCU/WCU)
- Max 20 GSIs per table
- Supports sparse indexes (only items with attribute are indexed)

Example:
Base table: pk=user_id, sk=order_id
GSI: pk=status, sk=created_at
→ Enables: "Get all orders with status=pending sorted by date"

Projection options:
- KEYS_ONLY: Only keys projected (smallest, cheapest)
- INCLUDE: Keys + specified attributes
- ALL: All attributes projected (largest, most flexible)
```

### Local Secondary Index (LSI)
```
- Same partition key as base table, different sort key
- Shares partition with base table
- Supports strongly consistent reads
- Must be created at table creation time (cannot add later)
- 10GB per partition limit (LSI + base table data)
- Max 5 LSIs per table

Example:
Base table: pk=user_id, sk=order_id
LSI: pk=user_id, sk=order_date
→ Enables: "Get user's orders sorted by date" (vs by order_id)
```

---

## DynamoDB Streams & CDC

### Streams Architecture
```
┌───────────┐     ┌───────────────┐     ┌────────────┐
│ DynamoDB  │────→│  DynamoDB     │────→│  Lambda    │
│ Table     │     │  Streams      │     │  Trigger   │
│           │     │  (24h window) │     │            │
└───────────┘     └───────────────┘     └────────────┘

Stream record content (configurable):
- KEYS_ONLY: Only primary key
- NEW_IMAGE: Item after modification
- OLD_IMAGE: Item before modification
- NEW_AND_OLD_IMAGES: Both before and after

Use cases:
- Event-driven processing (Lambda triggers)
- Cross-region replication (Global Tables)
- Materialized views / aggregations
- Audit logging
- Search index sync (to OpenSearch)
- Cache invalidation
```

---

## Advanced Patterns

### Time-Series with DynamoDB
```
Table: SensorData
pk: SENSOR#<sensor_id>#<date>   (partition per sensor per day)
sk: <timestamp>                  (millisecond precision sort key)

Why date in partition key:
- Prevents unbounded partition growth
- Enables efficient TTL (old partitions expire)
- Queries within a day are single-partition (fast)

Cross-day query:
- Query multiple partitions (parallel)
- Or use GSI with different time granularity

TTL:
- Set ttl attribute on each item (epoch seconds)
- DynamoDB deletes expired items automatically (within 48 hours)
- Free deletion (no WCU consumed)
- Stream records generated for deleted items
```

### Adjacency List Pattern (Graph-like)
```
Model relationships in single table:

pk              sk                data
USER#alice      USER#alice        {name: "Alice", ...}
USER#alice      FOLLOWS#bob       {since: "2024-01-01"}
USER#alice      FOLLOWS#carol     {since: "2024-02-15"}
USER#bob        USER#bob          {name: "Bob", ...}
USER#bob        FOLLOWER#alice    {since: "2024-01-01"}

GSI (inverted index):
GSI-pk: sk, GSI-sk: pk
→ Query: Who does Alice follow? pk=USER#alice, sk begins_with("FOLLOWS#")
→ Query: Who follows Bob? GSI-pk=FOLLOWER#bob (using inverted GSI)
```

### Optimistic Locking with Version
```python
# Write with condition (prevents lost updates):
table.update_item(
    Key={'pk': 'ITEM#123', 'sk': 'DATA'},
    UpdateExpression='SET price = :new_price, version = :new_version',
    ConditionExpression='version = :current_version',
    ExpressionAttributeValues={
        ':new_price': 29.99,
        ':new_version': 6,
        ':current_version': 5
    }
)
# Fails with ConditionalCheckFailedException if version changed
# Application retries with fresh read
```

---

## Staff Architect Interview Questions

**Q1: How does DynamoDB achieve single-digit millisecond latency at any scale?**
**A:**
- Hash-based partitioning: Key → Partition → Direct node access (no scanning)
- Request router maintains partition metadata (no leader election latency)
- Each partition independently sized (10GB, 3K RCU, 1K WCU)
- Auto-splitting on overload (seamless)
- SSD storage with in-memory metadata
- Paxos for synchronous replication (within single region)
- No complex query planning (limited query model by design)

**Q2: When would you NOT use DynamoDB?**
**A:**
- Complex ad-hoc queries (multi-table JOINs, arbitrary filtering)
- Analytics/aggregations (use Redshift/Athena instead)
- Small datasets with complex queries (PostgreSQL simpler)
- Full-text search (use OpenSearch)
- Graph traversals (use Neptune/Neo4j)
- Item size >400KB (document databases better)
- Need immediate consistency on secondary indexes (GSI is eventually consistent)
- Relational data with many access patterns (constant denormalization burden)

**Q3: Explain the hot partition problem and adaptive capacity.**
**A:**
- Hot partition: One partition receives disproportionate traffic (e.g., viral post)
- Old behavior: Throttled at partition limit (3K RCU / 1K WCU)
- Adaptive capacity (current): DynamoDB automatically isolates hot items to dedicated partitions, borrows unused capacity from cold partitions
- Instant adaptive capacity: Applied within 1-2 minutes of detecting hotspot
- Burst: Short bursts absorbed by partition-level burst budget (300s worth of unused capacity)
- Still limited: Single partition cannot exceed 3K RCU / 1K WCU sustained indefinitely
- Solution for extreme hot keys: Application-level sharding (random suffix)

---

## Scenario-Based Questions

### Scenario 1: Multi-Tenant SaaS with DynamoDB

**Design:**
```
Single table design with tenant isolation:

pk                      sk                  Attributes
TENANT#acme             METADATA            plan, limits, created_at
TENANT#acme             USER#u001           name, email, role
TENANT#acme             USER#u002           name, email, role
TENANT#acme             PROJECT#p001        name, status, created_at
TENANT#acme|PROJECT#p001  TASK#t001         title, assignee, status
TENANT#acme|PROJECT#p001  TASK#t002         title, assignee, status

Access patterns:
1. Get tenant metadata: pk=TENANT#acme, sk=METADATA
2. List tenant users: pk=TENANT#acme, sk begins_with("USER#")
3. List project tasks: pk=TENANT#acme|PROJECT#p001, sk begins_with("TASK#")
4. Get tasks by status: GSI with pk=TENANT#acme, sk=STATUS#active#<date>

Isolation:
- IAM policies restrict access to pk prefix per tenant
- Fine-grained access control (LeadingKeys condition)
- Each tenant's data naturally separated by partition key prefix

Scaling:
- Each tenant occupies dedicated partitions (at scale)
- Large tenants: Adaptive capacity handles hot tenants
- Enterprise tenants: Consider dedicated tables for complete isolation
```

### Scenario 2: Real-Time Gaming Leaderboard

```
Table: Leaderboard
pk: GAME#<game_id>#SEASON#<season_id>
sk: SCORE#<zero-padded-inverted-score>#USER#<user_id>

Zero-padded inverted score for descending order:
Score 9999 → sk = SCORE#0001#USER#alice  (9999 inverted = 10000-9999=0001)
Score 8500 → sk = SCORE#1500#USER#bob
Score 7200 → sk = SCORE#2800#USER#carol

Queries:
- Top 100: Query pk=GAME#123#SEASON#1, ScanIndexForward=true, Limit=100
- User rank: Difficult! (DynamoDB doesn't support COUNT efficiently)

Solution for rank:
- Approximate: Use a GSI with coarse buckets
- Exact: Maintain rank in a separate counter table
- Or: Use ElastiCache (Redis ZSET) alongside DynamoDB for real-time ranking

Update score:
1. Delete old score entry
2. Insert new score entry (new sk value)
3. Use TransactWriteItems for atomicity
```

