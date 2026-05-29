# MongoDB - Staff Architect Complete Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Storage Engine (WiredTiger)](#storage-engine-wiredtiger)
3. [Document Model & Schema Design](#document-model--schema-design)
4. [Indexing Strategies](#indexing-strategies)
5. [Transactions & Consistency](#transactions--consistency)
6. [Replication (Replica Sets)](#replication-replica-sets)
7. [Sharding Architecture](#sharding-architecture)
8. [Aggregation Framework](#aggregation-framework)
9. [Performance Optimization](#performance-optimization)
10. [Change Streams & Real-Time](#change-streams--real-time)
11. [Security Architecture](#security-architecture)
12. [Staff Architect Interview Questions](#staff-architect-interview-questions)
13. [Scenario-Based Questions](#scenario-based-questions)

---

## Architecture Overview

### MongoDB Architecture
```
┌─────────────────────────────────────────────────────┐
│                    mongos (Router)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │Query Router │  │Auth/Security│  │Aggregation │  │
│  └─────────────┘  └─────────────┘  └────────────┘  │
└──────────────────────────┬──────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Config Server RS │ │   Shard 1 (RS)   │ │   Shard 2 (RS)   │
│ (Metadata)       │ │ P ← S ← S       │ │ P ← S ← S       │
└──────────────────┘ └──────────────────┘ └──────────────────┘

RS = Replica Set (Primary + Secondaries + optional Arbiter)
```

### Key Architectural Decisions
- **Document-oriented** storage (BSON - Binary JSON)
- **Schemaless** (flexible schema per collection)
- **Replica Sets** for high availability (automatic failover)
- **Horizontal scaling** via sharding (native)
- **WiredTiger** storage engine (since 3.2)
- **Distributed transactions** (since 4.0 for RS, 4.2 for sharded)
- **Tunable consistency** (read/write concerns)

### BSON Format
```
BSON (Binary JSON):
- Binary serialization of JSON-like documents
- Supports additional types: Date, Binary, ObjectId, Decimal128, Regex
- Max document size: 16MB
- Ordered key-value pairs
- Length-prefixed (efficient traversal)

ObjectId (12 bytes):
┌──────────┬───────────┬─────────┬──────────┐
│ Timestamp│ Random    │Process  │ Counter  │
│ (4 bytes)│ (5 bytes) │ID(3 bytes)│(3 bytes)│
└──────────┴───────────┴─────────┴──────────┘
- Roughly sortable by creation time
- Unique without coordination (no centralized sequence)
```

---

## Storage Engine (WiredTiger)

### WiredTiger Architecture
```
┌──────────────────────────────────────────────┐
│               WiredTiger Engine                │
├──────────────────────────────────────────────┤
│ Cache (wiredTigerCacheSizeGB)                 │
│ ├── Internal pages (B-Tree nodes)            │
│ ├── Leaf pages (data)                        │
│ └── Overflow pages (large values)            │
├──────────────────────────────────────────────┤
│ Journal (WAL equivalent)                      │
│ ├── journal/WiredTigerLog.000000000X         │
│ └── Checkpoints every 60s or 2GB journal     │
├──────────────────────────────────────────────┤
│ Data Files                                    │
│ ├── collection-X-Y.wt (collection data)      │
│ ├── index-X-Y.wt (index data)               │
│ └── WiredTiger.wt (metadata)                 │
└──────────────────────────────────────────────┘
```

### WiredTiger MVCC
```
- Document-level concurrency control
- Optimistic concurrency: no locks for reads
- Write conflicts: WriteConflict exception → automatic retry
- Snapshot isolation per operation (or per transaction in multi-doc txns)
- Uses timestamps for point-in-time reads

Write path:
1. Acquire intent lock on collection
2. Find document in B-Tree
3. Create new version in update chain
4. Write to journal (group commit every 50ms or j:true)
5. Return acknowledgment

Checkpoint:
- Every 60 seconds (or 2GB journal written)
- Creates consistent snapshot of all data
- Old checkpoints cleaned up after new ones complete
```

### Compression
```
Block Compression options:
- snappy (default): Fast, moderate compression (3-5x)
- zlib: Better ratio, slower (5-7x)
- zstd: Best balance of speed and ratio (4-8x) (MongoDB 4.2+)
- none: No compression

Prefix Compression:
- For indexes: Common prefixes stored once
- Significant savings for string indexes

Configuration per collection:
db.createCollection("events", {
    storageEngine: {
        wiredTiger: {
            configString: "block_compressor=zstd"
        }
    }
});
```

---

## Document Model & Schema Design

### Schema Design Patterns

#### 1. Embedding (Denormalization)
```javascript
// Embed when: 1:1 or 1:Few relationship, always accessed together
{
    _id: ObjectId("..."),
    name: "John Doe",
    email: "john@example.com",
    address: {  // Embedded subdocument
        street: "123 Main St",
        city: "NYC",
        zip: "10001"
    },
    orders: [  // Embedded array (bounded)
        { id: 1, total: 99.99, date: ISODate("2024-01-15") },
        { id: 2, total: 149.99, date: ISODate("2024-02-20") }
    ]
}
// Pros: Single read, atomic updates, no JOINs
// Cons: 16MB document limit, unbounded arrays = problems
```

#### 2. Referencing (Normalization)
```javascript
// Reference when: 1:Many (unbounded), many:many, or independently accessed
// User document
{ _id: ObjectId("user1"), name: "John Doe", email: "john@example.com" }

// Order documents (reference back to user)
{ _id: ObjectId("order1"), user_id: ObjectId("user1"), total: 99.99 }
{ _id: ObjectId("order2"), user_id: ObjectId("user1"), total: 149.99 }

// Lookup (JOIN equivalent):
db.users.aggregate([
    { $lookup: { from: "orders", localField: "_id", foreignField: "user_id", as: "orders" } }
]);
```

#### 3. Subset Pattern
```javascript
// Store most-accessed subset embedded, full data referenced
{
    _id: ObjectId("product1"),
    name: "Widget",
    price: 29.99,
    recent_reviews: [  // Only last 10 reviews embedded
        { user: "Alice", rating: 5, text: "Great!", date: ISODate("2024-03-01") }
    ],
    review_count: 1523
}
// Full reviews in separate collection
{ _id: ObjectId("review1"), product_id: ObjectId("product1"), ... }
```

#### 4. Bucket Pattern (Time-Series)
```javascript
// Group measurements into time buckets
{
    sensor_id: "temp_001",
    bucket_start: ISODate("2024-01-15T10:00:00Z"),
    bucket_end: ISODate("2024-01-15T11:00:00Z"),
    measurements: [
        { ts: ISODate("2024-01-15T10:00:05Z"), value: 22.5 },
        { ts: ISODate("2024-01-15T10:00:10Z"), value: 22.6 },
        // ... up to 200 measurements per bucket
    ],
    count: 720,
    sum: 16200.0,
    min: 21.5,
    max: 23.5
}
// Benefits: Fewer documents, pre-computed aggregates, better I/O
```

#### 5. Polymorphic Pattern
```javascript
// Single collection, different "shapes"
{ type: "blog_post", title: "...", body: "...", tags: [...] }
{ type: "video", title: "...", url: "...", duration: 120 }
{ type: "image", title: "...", url: "...", width: 1920, height: 1080 }
// Query by type, common indexes on shared fields
```

#### 6. Outlier Pattern
```javascript
// Handle documents that exceed normal size
{
    _id: "popular_post_123",
    title: "Viral Post",
    comments_count: 50000,
    has_overflow: true,  // Flag indicating overflow
    comments: [ /* first 100 comments */ ]
}
// Overflow collection:
{ post_id: "popular_post_123", page: 1, comments: [ /* next 100 */ ] }
```

#### 7. Computed Pattern
```javascript
// Pre-compute expensive calculations
{
    _id: "product_123",
    name: "Widget",
    daily_stats: {
        "2024-01-15": { views: 1500, purchases: 45, revenue: 1342.50 },
        "2024-01-16": { views: 1200, purchases: 38, revenue: 1140.00 }
    },
    total_revenue: 2482.50,  // Pre-computed
    avg_daily_revenue: 1241.25  // Pre-computed
}
```

### Anti-Patterns
```
1. Unbounded arrays: Never embed arrays that grow indefinitely
   → Use bucketing or references

2. Massive documents: Approaching 16MB limit
   → Break into smaller documents

3. Unnecessary normalization: Over-referencing simple data
   → Embed if always accessed together

4. $lookup-heavy queries: Treating MongoDB like RDBMS
   → Redesign schema for access patterns

5. No schema validation: Completely schemaless = data quality issues
   → Use JSON Schema validation

6. Storing large binary in documents:
   → Use GridFS for files > 16MB
```

---

## Indexing Strategies

### Index Types
```javascript
// Single Field
db.users.createIndex({ email: 1 });  // Ascending
db.users.createIndex({ score: -1 }); // Descending

// Compound Index
db.orders.createIndex({ user_id: 1, created_at: -1 });
// ESR Rule: Equality → Sort → Range
db.orders.createIndex({ status: 1, created_at: -1, total: 1 });

// Multikey Index (arrays)
db.posts.createIndex({ tags: 1 });
// One index entry per array element
// Limitation: At most one array field per compound index

// Text Index
db.articles.createIndex({ title: "text", body: "text" },
    { weights: { title: 10, body: 1 }, default_language: "english" });
db.articles.find({ $text: { $search: "mongodb scaling" } });

// Geospatial (2dsphere)
db.places.createIndex({ location: "2dsphere" });
db.places.find({
    location: { $near: { $geometry: { type: "Point", coordinates: [-73.97, 40.77] },
                         $maxDistance: 1000 } }
});

// Hashed Index (for hash-based sharding)
db.users.createIndex({ user_id: "hashed" });

// Wildcard Index (MongoDB 4.2+)
db.events.createIndex({ "metadata.$**": 1 });
// Indexes all fields under metadata subdocument
// Good for: Arbitrary/unknown field queries

// Partial Index
db.orders.createIndex(
    { status: 1, created_at: -1 },
    { partialFilterExpression: { status: "active" } }
);

// Sparse Index
db.users.createIndex({ phone: 1 }, { sparse: true });
// Only indexes documents that have the field

// TTL Index (auto-expire documents)
db.sessions.createIndex({ lastAccess: 1 }, { expireAfterSeconds: 3600 });

// Unique Index
db.users.createIndex({ email: 1 }, { unique: true });

// Hidden Index (MongoDB 4.4+)
db.users.hideIndex("idx_old");  // Optimizer ignores, still maintained
```

### Index Intersection
```javascript
// MongoDB can combine results from multiple indexes
db.orders.createIndex({ user_id: 1 });
db.orders.createIndex({ status: 1 });

db.orders.find({ user_id: 123, status: "active" });
// May use index intersection of both indexes
// But: Compound index is usually more efficient
```

### Covered Queries
```javascript
// Query answered entirely from index (no document access)
db.orders.createIndex({ user_id: 1, total: 1, status: 1 });

db.orders.find(
    { user_id: 123 },
    { _id: 0, total: 1, status: 1 }  // Projection matches index
);
// "totalDocsExamined": 0 in explain output
```

### ESR Rule (Equality-Sort-Range)
```javascript
// Optimal compound index ordering:
// 1. Equality conditions first (exact match)
// 2. Sort fields next
// 3. Range conditions last

// Query: Find active orders for user, sorted by date, total > $100
db.orders.find({ user_id: 123, status: "active", total: { $gt: 100 } })
         .sort({ created_at: -1 });

// Optimal index:
db.orders.createIndex({ user_id: 1, status: 1, created_at: -1, total: 1 });
//                      ^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^   ^^^^^^^^^
//                      Equality                 Sort           Range
```

---

## Transactions & Consistency

### Write Concern
```javascript
// w: Number of nodes that must acknowledge write
db.collection.insertOne(doc, {
    writeConcern: {
        w: "majority",  // Majority of replica set members
        j: true,        // Written to journal
        wtimeout: 5000  // Timeout in ms
    }
});

// Levels:
// w: 0 = Fire and forget (no acknowledgment)
// w: 1 = Primary acknowledged (default)
// w: "majority" = Majority of voting members
// w: N = Specific number of members
// j: true = Written to journal on disk
```

### Read Concern
```javascript
// What data the read returns
db.collection.find().readConcern("majority");

// Levels:
// "local" = Latest data on queried member (may roll back)
// "available" = Like local, but for sharded (may return orphan docs)
// "majority" = Data acknowledged by majority (won't roll back)
// "linearizable" = Majority + confirms no stale primary
// "snapshot" = Majority at a specific point in time (for transactions)
```

### Read Preference
```javascript
// Which member to read from
db.collection.find().readPref("secondaryPreferred");

// Modes:
// "primary" = Only primary (default, strongest consistency)
// "primaryPreferred" = Primary, fallback to secondary
// "secondary" = Only secondaries
// "secondaryPreferred" = Secondaries, fallback to primary
// "nearest" = Lowest network latency

// With tag sets (data locality):
{ readPreference: "secondary", readPreferenceTags: [{ "dc": "east" }] }
```

### Multi-Document Transactions (4.0+)
```javascript
const session = client.startSession();
session.startTransaction({
    readConcern: { level: "snapshot" },
    writeConcern: { w: "majority" },
    readPreference: "primary"
});

try {
    const accounts = session.getDatabase("bank").collection("accounts");
    
    // Debit
    await accounts.updateOne(
        { _id: "account_A" },
        { $inc: { balance: -100 } },
        { session }
    );
    
    // Credit
    await accounts.updateOne(
        { _id: "account_B" },
        { $inc: { balance: 100 } },
        { session }
    );
    
    await session.commitTransaction();
} catch (error) {
    await session.abortTransaction();
    throw error;
} finally {
    session.endSession();
}

// Limitations:
// - 60 second max duration (configurable)
// - 16MB max oplog entry per transaction
// - Performance overhead (~10-30%)
// - Cross-shard transactions add latency (2PC)
// - Cannot create/drop collections inside transaction
```

### Causal Consistency
```javascript
// Ensures operations are causally ordered
const session = client.startSession({ causalConsistency: true });
const collection = session.getDatabase("test").collection("items");

// Write on primary
await collection.insertOne({ item: "abc" }, { session });

// Read on secondary sees the write (guaranteed)
await collection.find({}, { session }).readPref("secondary").toArray();
// Without causal consistency, secondary read might not see the insert
```

---

## Replication (Replica Sets)

### Replica Set Architecture
```
┌───────────────────────────────────────────────┐
│              Replica Set "rs0"                  │
│                                                │
│  ┌─────────────┐  Election Protocol (Raft)     │
│  │   PRIMARY   │────────────────────────────┐  │
│  │  (Read/Write)│                           │  │
│  └──────┬──────┘                            │  │
│         │ Oplog replication                  │  │
│    ┌────┴────┐                              │  │
│    ▼         ▼                              │  │
│ ┌──────┐ ┌──────┐ ┌──────┐                 │  │
│ │ SEC1 │ │ SEC2 │ │ SEC3 │ (Voting members) │  │
│ │(Read)│ │(Read)│ │(Read)│                   │  │
│ └──────┘ └──────┘ └──────┘                   │  │
│                                                │
│  Optional members:                             │
│  - Arbiter (votes only, no data)              │
│  - Hidden (not in read preference)            │
│  - Delayed (point-in-time recovery)           │
│  - Non-voting (data redundancy only)          │
└───────────────────────────────────────────────┘
```

### Oplog (Operations Log)
```javascript
// Oplog is a capped collection on primary: local.oplog.rs
// Each operation is idempotent (can replay safely)

// Oplog entry example:
{
    ts: Timestamp(1706000000, 1),     // Timestamp + ordinal
    t: NumberLong(1),                 // Term (election epoch)
    h: NumberLong("..."),             // Hash
    v: 2,
    op: "u",                          // Operation: i(insert), u(update), d(delete), c(command), n(noop)
    ns: "mydb.users",                // Namespace
    o2: { _id: ObjectId("...") },    // Query criteria (for updates)
    o: { $set: { name: "New Name" } } // Operation document
}

// Oplog sizing:
// Default: 5% of free disk space (min 990MB, max 50GB)
// Should hold: At least 24-72 hours of operations (for maintenance windows)
// Check: rs.printReplicationInfo()
```

### Election Process
```
Trigger conditions:
- Primary becomes unreachable (heartbeat timeout: 10s)
- Primary steps down (rs.stepDown())
- Member with higher priority becomes available

Election protocol (Raft-based):
1. Eligible secondary calls election
2. Candidate votes for itself, requests votes from others
3. Members vote based on:
   - Priority (higher = preferred)
   - Oplog freshness (must be most recent)
   - Network connectivity
4. Majority vote wins → New primary
5. Typical failover time: 2-12 seconds

Configuration:
rs.conf():
{
    members: [
        { _id: 0, host: "mongo1:27017", priority: 2 },  // Preferred primary
        { _id: 1, host: "mongo2:27017", priority: 1 },
        { _id: 2, host: "mongo3:27017", priority: 1 },
    ],
    settings: {
        electionTimeoutMillis: 10000,
        heartbeatTimeoutSecs: 10
    }
}
```

### Initial Sync & Resync
```
Initial Sync process:
1. Choose sync source (nearest member with fresh oplog)
2. Clone all databases and collections
3. Build all indexes
4. Apply oplog entries received during cloning
5. Transition to steady-state replication

Resync triggers:
- New member added to replica set
- Member's oplog fell behind (gap in oplog)
- Data corruption detected

Performance impact:
- Initial sync can take hours for large datasets
- Network bandwidth: 100MB/s+ for TB-scale data
- Target node CPU/disk intensive during index builds
```

---

## Sharding Architecture

### Sharding Components
```
┌────────────────────────────────────────────────────┐
│                    Application                       │
└────────────────────────┬───────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
     ┌──────────────┐     ┌──────────────┐
     │   mongos 1   │     │   mongos 2   │  (Stateless routers)
     └──────┬───────┘     └──────┬───────┘
            │                     │
            └──────────┬──────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Config Server │ │  Shard 1     │ │  Shard 2     │
│ Replica Set  │ │  (RS)        │ │  (RS)        │
│              │ │ [P][S][S]    │ │ [P][S][S]    │
│ - Metadata   │ │              │ │              │
│ - Chunk map  │ │ chunks:      │ │ chunks:      │
│ - Shard info │ │ [A-M]        │ │ [N-Z]        │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Shard Key Selection
```javascript
// CRITICAL DECISION: Cannot change shard key easily (resharding added in 5.0)

// Hashed Shard Key:
sh.shardCollection("mydb.events", { user_id: "hashed" });
// + Even distribution
// + Prevents hot spots
// - No range queries on shard key
// - All range queries become scatter-gather

// Ranged Shard Key:
sh.shardCollection("mydb.events", { timestamp: 1 });
// + Range queries efficient (targeted)
// - Monotonically increasing = all writes to last shard (hot shard!)
// Solution: Compound key { location: 1, timestamp: 1 }

// Compound Shard Key:
sh.shardCollection("mydb.orders", { customer_id: 1, order_date: 1 });
// + Targeted queries when customer_id known
// + Range queries within customer work
// - Customer with many orders = jumbo chunks

// Zone Sharding (data locality):
sh.addShardTag("shard_us_east", "US");
sh.addShardTag("shard_eu_west", "EU");
sh.addTagRange("mydb.users", 
    { region: "US", _id: MinKey }, 
    { region: "US", _id: MaxKey }, "US");
```

### Shard Key Properties (Ideal)
```
1. High Cardinality: Many distinct values (avoid few values that create jumbo chunks)
2. Even Distribution: Values spread across range (avoid hotspots)
3. Query Isolation: Queries include shard key (targeted, not scatter-gather)
4. Non-Monotonic: Avoid timestamps/ObjectIds alone (hot shard)
5. Immutable: Shard key values shouldn't change (updateable since 4.2 but expensive)

Bad shard keys:
- { status: 1 } → Low cardinality (3-5 values)
- { _id: 1 } → Monotonic (ObjectId is time-ordered)
- { country: 1 } → Uneven distribution

Good shard keys:
- { tenant_id: "hashed" } → Even distribution for multi-tenant
- { user_id: 1, created_at: 1 } → Compound, good cardinality
- { region: 1, user_id: 1 } → Zone-aware with cardinality
```

### Chunk Management
```
Chunk: Contiguous range of shard key values
Default size: 128MB (configurable: 1MB - 1024MB)

Chunk splitting:
- Triggered when chunk exceeds max size
- Mongos tracks chunk sizes
- Split point: median of chunk range
- Metadata-only operation (no data movement)

Balancer:
- Background process on config server primary
- Moves chunks between shards to equalize chunk count
- Runs during balancer window (configurable)
- Rate limited: max 1 concurrent migration per shard (configurable)

Jumbo chunks:
- Chunks that cannot be split (all docs have same shard key value)
- Cannot be moved by balancer
- Solution: Increase shard key cardinality, use compound key

Chunk migration process:
1. Balancer identifies imbalance (threshold: 2-8 chunks difference)
2. Source shard clones chunk data to destination
3. Source shard forwards ongoing writes
4. Commit: Update config server metadata
5. Clean up: Delete migrated data from source (after range deletion delay)
```

### Resharding (MongoDB 5.0+)
```javascript
// Change shard key without downtime
db.adminCommand({
    reshardCollection: "mydb.orders",
    key: { customer_id: 1, order_date: 1 }  // New shard key
});

// Process:
// 1. Creates temporary resharding collection
// 2. Clones existing data with new sharding
// 3. Applies oplog changes during cloning
// 4. Switches to new collection atomically
// Duration: Hours to days depending on data size
```

---

## Aggregation Framework

### Pipeline Stages
```javascript
db.orders.aggregate([
    // Stage 1: Filter (uses indexes, push early)
    { $match: { status: "completed", created_at: { $gte: ISODate("2024-01-01") } } },
    
    // Stage 2: Add computed fields
    { $addFields: { 
        total_with_tax: { $multiply: ["$total", 1.08] },
        year: { $year: "$created_at" }
    } },
    
    // Stage 3: Unwind arrays
    { $unwind: "$items" },
    
    // Stage 4: Group and aggregate
    { $group: {
        _id: { customer: "$customer_id", year: "$year" },
        total_spent: { $sum: "$total" },
        order_count: { $sum: 1 },
        avg_order: { $avg: "$total" },
        items: { $push: "$items.name" }
    } },
    
    // Stage 5: Lookup (LEFT JOIN)
    { $lookup: {
        from: "customers",
        localField: "_id.customer",
        foreignField: "_id",
        as: "customer_info"
    } },
    
    // Stage 6: Sort
    { $sort: { total_spent: -1 } },
    
    // Stage 7: Limit
    { $limit: 100 },
    
    // Stage 8: Project (reshape output)
    { $project: {
        customer_name: { $arrayElemAt: ["$customer_info.name", 0] },
        total_spent: 1,
        order_count: 1,
        avg_order: { $round: ["$avg_order", 2] }
    } }
]);
```

### Pipeline Optimization
```javascript
// MongoDB automatically optimizes pipelines:
// 1. $match + $match → merged into single $match
// 2. $match before $lookup → pushed before $lookup
// 3. $project + $match → $match pushed before $project (if possible)
// 4. $sort + $limit → combined (TopN sort, limits memory)
// 5. $addFields + $match → $match pushed if independent fields

// Sharded collection optimization:
// $match on shard key → targeted to specific shards
// Without shard key in $match → scatter-gather (all shards)

// Memory limit: 100MB per stage (use allowDiskUse: true for larger)
db.orders.aggregate([...], { allowDiskUse: true });
```

### Materialized Views
```javascript
// $merge: Write results to another collection (upsert)
db.orders.aggregate([
    { $group: { _id: "$customer_id", total: { $sum: "$amount" } } },
    { $merge: { 
        into: "customer_totals",
        whenMatched: "replace",
        whenNotMatched: "insert"
    } }
]);

// $out: Replace entire collection (atomic)
db.orders.aggregate([
    { $group: { _id: "$product_id", count: { $sum: 1 } } },
    { $out: "product_counts" }  // Replaces collection atomically
]);
```

---

## Performance Optimization

### Query Optimization
```javascript
// explain() output analysis
db.orders.find({ user_id: 123 }).explain("executionStats");

// Key metrics:
// - queryPlanner.winningPlan.stage: IXSCAN (good), COLLSCAN (bad)
// - executionStats.nReturned vs totalDocsExamined (ratio should be ~1:1)
// - executionStats.executionTimeMillis
// - executionStats.totalKeysExamined

// Profiler (slow query log)
db.setProfilingLevel(1, { slowms: 100 });  // Log queries > 100ms
db.system.profile.find().sort({ ts: -1 }).limit(10);
```

### Connection Pooling
```javascript
// MongoDB driver connection pool settings
const client = new MongoClient(uri, {
    maxPoolSize: 100,        // Max connections per pool
    minPoolSize: 10,         // Min connections maintained
    maxIdleTimeMS: 30000,    // Close idle connections after 30s
    waitQueueTimeoutMS: 5000, // Timeout waiting for connection
    serverSelectionTimeoutMS: 5000,
    connectTimeoutMS: 10000,
    socketTimeoutMS: 45000
});

// Connection pool per mongos (in sharded cluster)
// Each application server maintains pool to each mongos
```

### Memory & Storage Optimization
```javascript
// WiredTiger cache sizing (default: 50% of RAM - 1GB)
// storage.wiredTiger.engineConfig.cacheSizeGB

// Compact collections (reclaim space, rebuild indexes)
db.runCommand({ compact: "collection_name" });

// Check collection stats
db.collection.stats();
// storageSize: Actual disk usage
// size: Logical data size (uncompressed)
// totalIndexSize: All indexes combined

// Index memory:
db.collection.totalIndexSize();  // Should fit in RAM for best performance
```

---

## Change Streams & Real-Time

### Change Streams
```javascript
// Watch for changes in real-time (backed by oplog)
const pipeline = [
    { $match: { 
        operationType: { $in: ["insert", "update", "replace"] },
        "fullDocument.status": "active"
    } }
];

const changeStream = db.collection("orders").watch(pipeline, {
    fullDocument: "updateLookup",  // Include full document on updates
    fullDocumentBeforeChange: "whenAvailable",  // MongoDB 6.0+
    resumeAfter: resumeToken,  // Resume from specific point
    startAtOperationTime: Timestamp(...)  // Start from specific time
});

changeStream.on("change", (event) => {
    console.log(event.operationType, event.fullDocument);
    // Save event._id as resume token for fault tolerance
});

// Use cases:
// - Real-time notifications
// - Cache invalidation
// - Event-driven microservices
// - ETL/CDC to data warehouse
// - Audit logging
```

---

## Staff Architect Interview Questions

### Architecture & Design

**Q1: When would you choose MongoDB over PostgreSQL, and vice versa?**
**A:**
Choose MongoDB when:
- Rapidly evolving schema (startups, prototyping)
- Document-centric access patterns (always read/write full entity)
- Hierarchical/nested data (product catalogs, CMS)
- Horizontal scale-out is primary requirement
- Geographically distributed deployments
- Real-time analytics with aggregation framework

Choose PostgreSQL when:
- Complex relationships and JOINs required
- ACID transactions across multiple entities (financial)
- Strict schema with complex constraints
- Advanced SQL (window functions, CTEs, recursive queries)
- Rich indexing (GiST, GIN, BRIN)
- PostGIS for advanced geospatial

**Q2: How does MongoDB handle distributed transactions across shards?**
**A:** MongoDB uses Two-Phase Commit (2PC) with a coordinator:
1. Client starts transaction via mongos
2. Mongos acts as transaction coordinator
3. Each participating shard prepares (writes to oplog, takes locks)
4. Coordinator sends commit/abort decision
5. Each shard commits/aborts locally
- Recovery: If coordinator fails, recovery process completes in-doubt transactions
- Performance: 2x-3x slower than single-shard transactions due to coordination
- Best practice: Design schema to minimize cross-shard transactions

**Q3: Explain the oplog and its implications for operational management.**
**A:** The oplog (local.oplog.rs) is a capped collection recording all write operations:
- **Idempotent entries**: Each entry can be safely replayed
- **Size matters**: Must hold enough operations for maintenance windows, initial syncs
- **Monitoring**: If secondary falls behind beyond oplog window, full resync needed
- **Performance impact**: Every write generates oplog entry → 2x write amplification minimum
- **Change streams**: Built on oplog tailing → affected by oplog size
- **Considerations**: Large transactions create large oplog entries (16MB limit per entry)

**Q4: How would you design a global multi-region MongoDB deployment?**
**A:**
```
Architecture options:

Option 1: Single sharded cluster spanning regions
- Mongos in each region
- Zone sharding by region (data locality)
- Cross-region replication for HA
- Latency: Low for local reads, high for cross-region writes

Option 2: Separate clusters with sync
- Independent clusters per region
- Application-level or Realm sync
- Eventually consistent between regions
- Latency: Low for all local operations

Option 3: Global cluster with zone sharding
zones: [
  { region: "US", shards: ["shard-us-1", "shard-us-2"] },
  { region: "EU", shards: ["shard-eu-1", "shard-eu-2"] }
]
- Route user data to nearest zone
- Global collections replicated everywhere
- Per-user data stays in region (compliance)
```

**Q5: What are the consistency guarantees with different readConcern/writeConcern combinations?**
**A:**
| Write Concern | Read Concern | Guarantee |
|---------------|-------------|-----------|
| w:1 | local | Fastest, may see rollback data |
| w:majority | local | Durable writes, may read stale |
| w:majority | majority | Durable, no rollback reads |
| w:majority | linearizable | Strongest, real-time consistency |
| w:majority | snapshot | Transaction-level consistency |

For read-your-writes consistency:
- Same session with causal consistency enabled
- Or w:majority + readConcern:majority on same member

---

## Scenario-Based Questions

### Scenario 1: Schema Design for E-Commerce

**Requirements:** Product catalog with variants, reviews, inventory across warehouses.

```javascript
// Product (core data + variants embedded)
{
    _id: ObjectId("..."),
    sku: "WIDGET-001",
    name: "Premium Widget",
    description: "...",
    category_path: ["Electronics", "Gadgets", "Widgets"],
    
    // Embedded: bounded, always accessed with product
    variants: [
        { 
            sku: "WIDGET-001-RED-S",
            color: "red", size: "S",
            price: { amount: 2999, currency: "USD" },
            images: ["url1", "url2"]
        },
        { 
            sku: "WIDGET-001-BLUE-M",
            color: "blue", size: "M",
            price: { amount: 3499, currency: "USD" },
            images: ["url3"]
        }
    ],
    
    // Computed/cached for fast reads
    price_range: { min: 2999, max: 3499 },
    avg_rating: 4.5,
    review_count: 1234,
    
    // Facets for search
    attributes: {
        brand: "WidgetCorp",
        material: "aluminum",
        weight_g: 250
    }
}

// Inventory (separate collection - high write frequency)
{
    _id: ObjectId("..."),
    sku: "WIDGET-001-RED-S",
    warehouse_id: "WH-NYC",
    quantity: 150,
    reserved: 12,
    available: 138,
    last_updated: ISODate("...")
}

// Reviews (separate - unbounded, independently queried)
{
    _id: ObjectId("..."),
    product_id: ObjectId("..."),
    user_id: ObjectId("..."),
    rating: 5,
    title: "Great product",
    text: "...",
    helpful_votes: 42,
    verified_purchase: true,
    created_at: ISODate("...")
}

// Indexes:
db.products.createIndex({ "category_path": 1 });
db.products.createIndex({ "variants.sku": 1 });
db.products.createIndex({ "attributes.$**": 1 });  // Wildcard for faceted search
db.inventory.createIndex({ sku: 1, warehouse_id: 1 }, { unique: true });
db.reviews.createIndex({ product_id: 1, created_at: -1 });
db.reviews.createIndex({ product_id: 1, rating: 1 });
```

### Scenario 2: Handling 100K Writes/Second

**Problem:** IoT platform ingesting 100K sensor readings per second.

**Architecture:**
```
Sensors → Message Queue (Kafka) → Batch Writer → MongoDB Sharded Cluster

Cluster design:
- 4 shards × 3 members = 12 mongod instances
- Shard key: { device_id: "hashed" }
- Time-series collection (MongoDB 5.0+):

db.createCollection("sensor_data", {
    timeseries: {
        timeField: "timestamp",
        metaField: "device_id",
        granularity: "seconds"
    },
    expireAfterSeconds: 604800  // 7 days TTL
});

// Time-series collections optimize:
// - Columnar compression within buckets
// - Automatic bucketing by time
// - Efficient range queries on time

Batch writer pattern:
- Accumulate 1000 readings in memory
- Use insertMany with ordered: false (continue on error)
- Write concern: w:1 for high throughput (acceptable loss for IoT)
- Retry failed batches

Estimated capacity:
- Each shard handles ~30K inserts/sec
- 4 shards = 120K inserts/sec with headroom
- 100K readings × 200 bytes avg × 86400 sec = ~1.7TB/day raw
- With compression: ~400GB/day
```

### Scenario 3: Migration from RDBMS to MongoDB

**Problem:** Legacy Oracle system with 200 tables, complex joins. Migrate to MongoDB.

**Approach:**
```
Phase 1: Analysis
- Map access patterns (which tables are always joined?)
- Identify aggregate boundaries (DDD aggregates)
- Categorize relationships: 1:1, 1:few, 1:many, many:many

Phase 2: Schema Design
- 1:1 → Embed
- 1:Few (bounded) → Embed
- 1:Many (unbounded) → Reference (child references parent)
- Many:Many → Array of references (one or both sides)

Phase 3: Dual-write migration
- Write to both Oracle and MongoDB
- Backfill MongoDB from Oracle (batched)
- Validate data consistency

Phase 4: Read migration
- Shadow reads: Compare MongoDB vs Oracle results
- Gradual traffic shift with feature flags

Phase 5: Write migration
- Switch writes to MongoDB
- Keep Oracle as backup/audit for transition period

Anti-patterns to avoid:
- Don't replicate relational schema in MongoDB (1 table ≠ 1 collection)
- Don't normalize everything (embed for access patterns)
- Don't ignore document size limits (16MB)
- Don't skip indexing (MongoDB without indexes = full collection scans)
```

### Scenario 4: Handling Jumbo Chunks in Production

**Problem:** Sharded cluster with jumbo chunks causing balancer failures.

**Diagnosis:**
```javascript
// Find jumbo chunks
use config;
db.chunks.find({ jumbo: true });

// Check chunk distribution
db.chunks.aggregate([
    { $group: { _id: "$shard", count: { $sum: 1 } } },
    { $sort: { count: -1 } }
]);

// Common causes:
// 1. Low cardinality shard key (e.g., { country: 1 })
// 2. Monotonically increasing shard key causing all inserts to one chunk
// 3. Hot shard key value (one user with millions of records)
```

**Solutions:**
```javascript
// Solution 1: Refine shard key (MongoDB 4.4+)
db.adminCommand({
    refineCollectionShardKey: "mydb.orders",
    key: { customer_id: 1, order_date: 1 }  // Add suffix field
});

// Solution 2: Reshard collection (MongoDB 5.0+)
db.adminCommand({
    reshardCollection: "mydb.orders",
    key: { customer_id: "hashed" }  // Better distribution
});

// Solution 3: Manual split (if chunk is splittable)
db.adminCommand({
    split: "mydb.orders",
    find: { customer_id: "whale_customer" }  // Split at this point
});

// Solution 4: Clear jumbo flag (if chunk was incorrectly marked)
db.adminCommand({
    clearJumboFlag: "mydb.orders",
    find: { customer_id: "whale_customer" }
});

// Prevention:
// - Use compound shard keys with high cardinality suffix
// - Monitor chunk distribution regularly
// - Set appropriate chunk size (smaller = more granular balancing)
```

---

## MongoDB at Scale - Production Checklist

```
1. Replica Set sizing: Odd number of voting members (3, 5, 7)
2. WiredTiger cache: 50% RAM for dedicated server
3. Storage: SSD/NVMe mandatory for production
4. Network: Low latency between replica set members (<2ms)
5. Connection pooling: Size based on concurrent operations
6. Index coverage: No COLLSCAN in production queries
7. Schema validation: Enforce shape for critical collections
8. Monitoring: Atlas/Ops Manager, or Prometheus + Grafana
9. Backup: Atlas backup, mongodump, or filesystem snapshots
10. Sharding: Plan early, shard key is permanent (mostly)
11. Oplog size: Minimum 24h retention
12. Journaling: Always on (don't disable for "performance")
13. Read/Write concern: Tune per operation criticality
14. TTL indexes: Auto-cleanup for temporary data
15. Change streams: Use resume tokens for fault tolerance
```

