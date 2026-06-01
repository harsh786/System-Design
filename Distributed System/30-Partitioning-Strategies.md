# Partitioning (Sharding) Strategies

## 1. Problem Statement

A single node has finite capacity along three axes:

```
┌─────────────────────────────────────────────────────────────┐
│                    SINGLE NODE LIMITS                         │
├─────────────────────────────────────────────────────────────┤
│  Storage:    Disk capacity (e.g., 16 TB max)                │
│  Throughput: CPU/IO saturation (e.g., 100K ops/sec)         │
│  Memory:     Working set exceeds RAM → thrashing            │
│  Network:    Bandwidth saturation on single NIC             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              SOLUTION: Split data across N nodes
              Each node holds 1/N of the dataset
              Each node handles 1/N of the traffic (ideally)
```

**Partitioning** is the act of splitting a dataset into disjoint subsets (partitions), each assigned to a different node. The goal is to achieve:

- **Scalability** — Add nodes to handle more data/traffic
- **Performance** — Parallelize reads/writes across nodes
- **Manageability** — Smaller units for backup, restore, migration

The fundamental challenge: **choose a partitioning scheme that distributes load evenly while preserving useful access patterns (range queries, locality).**

---

## 2. Terminology Clarification

Different systems use different terminology for the same concept:

```
┌────────────────────┬──────────────────────┬────────────────────┐
│   System           │   Term for "split"   │   Term for "unit"  │
├────────────────────┼──────────────────────┼────────────────────┤
│ Kafka              │ Partitioning         │ Partition           │
│ Cassandra          │ Partitioning         │ Partition (vnode)   │
│ MongoDB            │ Sharding             │ Shard (chunk)       │
│ MySQL/Vitess       │ Sharding             │ Shard               │
│ HBase              │ Splitting            │ Region              │
│ Elasticsearch      │ Sharding             │ Shard               │
│ CockroachDB        │ Range partitioning   │ Range               │
│ DynamoDB           │ Partitioning         │ Partition           │
│ PostgreSQL/Citus   │ Sharding             │ Shard               │
│ Bigtable           │ Splitting            │ Tablet              │
└────────────────────┴──────────────────────┴────────────────────┘
```

Throughout this document: **Partition = the unit of data distribution.** All terms above are synonyms.

A partition is:
- The smallest unit of **placement** (assigned to a node)
- The smallest unit of **replication** (replicated as a whole)
- The smallest unit of **rebalancing** (moved between nodes)

---

## 3. Partitioning Strategies

### 3a. Hash Partitioning

**Mechanism:**
```
partition_id = hash(key) mod N
```

A deterministic hash function maps each key to a partition. Keys with similar values are scattered across different partitions.

```
         Keys                  hash(key) mod 4              Partitions
    ┌──────────┐                                        ┌──────────────┐
    │ user_001 │───── hash("user_001") = 7 mod 4 = 3 ──▶│ Partition 3  │
    │ user_002 │───── hash("user_002") = 2 mod 4 = 2 ──▶│ Partition 2  │
    │ user_003 │───── hash("user_003") = 9 mod 4 = 1 ──▶│ Partition 1  │
    │ user_004 │───── hash("user_004") = 4 mod 4 = 0 ──▶│ Partition 0  │
    │ user_005 │───── hash("user_005") = 6 mod 4 = 2 ──▶│ Partition 2  │
    │ user_006 │───── hash("user_006") = 3 mod 4 = 3 ──▶│ Partition 3  │
    └──────────┘                                        └──────────────┘

    Result: Even distribution regardless of key lexicographic order
            user_001 and user_002 are NOT on adjacent partitions
```

**Properties:**
| Aspect | Rating |
|--------|--------|
| Distribution uniformity | Excellent (with good hash function) |
| Range query support | None (adjacent keys scattered) |
| Hot spot avoidance | Good (unless many keys hash to same value) |
| Implementation complexity | Low |
| Rebalancing on resize | Catastrophic with naive mod N (all keys move) |

**Hash Functions Used in Practice:**
- **Murmur3** — Cassandra, Kafka (fast, good distribution, non-cryptographic)
- **MD5** — MongoDB (legacy), some custom systems
- **xxHash** — Modern high-performance systems
- **FNV-1a** — Lightweight, decent distribution
- **CityHash/FarmHash** — Google systems

**Critical Problem — Naive Modulo Resize:**

```
Before: hash(key) mod 4          After: hash(key) mod 5
┌─────┬───────────────┐          ┌─────┬───────────────┐
│ P0  │ keys: A,E,I   │          │ P0  │ keys: F,K     │  ← different!
│ P1  │ keys: B,F,J   │          │ P1  │ keys: A,G     │  ← different!
│ P2  │ keys: C,G,K   │          │ P2  │ keys: B,H,L   │  ← different!
│ P3  │ keys: D,H,L   │          │ P3  │ keys: C,I     │  ← different!
└─────┴───────────────┘          │ P4  │ keys: D,E,J   │  ← new
                                  └─────┴───────────────┘
                    ~80% of keys must move!
```

**Solution: Consistent Hashing**

Map both keys and nodes onto a hash ring. Each key is assigned to the first node clockwise from its position. Adding/removing a node only affects keys in the adjacent segment.

```
                        Node A
                       ╱      ╲
                   ···           ···
                 ·                   ·
               ·    keys here → A      ·
             ·                           ·
            ·                             ·
     Node D ·                             · Node B
            ·                             ·
             ·                           ·
               ·    keys here → C      ·
                 ·                   ·
                   ···           ···
                       ╲      ╱
                        Node C

    Adding Node E between A and B:
    Only keys between A and E move from B to E
    All other keys stay put (~1/N keys move)
```

With **virtual nodes (vnodes)**: each physical node is assigned multiple positions on the ring (e.g., 256 vnodes per node), improving uniformity.

---

### 3b. Range Partitioning

**Mechanism:**

The key space is divided into contiguous, non-overlapping ranges. Each partition owns one range.

```
    Key Space: [0 ────────────────────────────────────────── ∞)

    ┌──────────────┬──────────────┬──────────────┬──────────────┐
    │  Partition 0 │  Partition 1 │  Partition 2 │  Partition 3 │
    │  [A - F)     │  [F - M)     │  [M - T)     │  [T - Z]     │
    │              │              │              │              │
    │  alice       │  frank       │  mike        │  tony        │
    │  bob         │  george      │  nancy       │  ursula      │
    │  charlie     │  harry       │  oscar       │  victor      │
    │  david       │  irene       │  peter       │  william     │
    │  emily       │  kate        │  rachel      │  xavier      │
    │              │  liam        │  steve       │  zara        │
    └──────────────┴──────────────┴──────────────┴──────────────┘

    Range query "all users M-P":  → only Partition 2 (single partition!)
    Point query "frank":          → only Partition 1
```

**Properties:**
| Aspect | Rating |
|--------|--------|
| Distribution uniformity | Poor without careful boundary selection |
| Range query support | Excellent (contiguous keys on same partition) |
| Hot spot risk | High (skewed distributions, time-series writes) |
| Implementation complexity | Medium (boundary management) |
| Rebalancing | Split/merge individual ranges |

**Auto-Splitting (HBase Regions Model):**

```
    Initial state: One region holds all data
    ┌──────────────────────────────────────────────┐
    │              Region 1: [A - Z]               │  size = 10 GB
    │              threshold = 10 GB               │
    └──────────────────────────────────────────────┘
                         │ split!
                         ▼
    ┌──────────────────────┬───────────────────────┐
    │  Region 1: [A - M)   │  Region 2: [M - Z]   │
    │  size = 5 GB         │  size = 5 GB          │
    └──────────────────────┴───────────────────────┘
                                    │ Region 2 grows...
                                    ▼
    ┌──────────────────────┬────────────┬──────────┐
    │  Region 1: [A - M)   │ R2: [M-T) │ R3: [T-Z]│
    │  5 GB                │  5 GB      │  5 GB    │
    └──────────────────────┴────────────┴──────────┘

    Regions assigned to RegionServers (nodes)
    Hot region can be moved to less-loaded server
```

**Time-Series Hot Spot Problem:**

```
    Key: timestamp (2024-01-01, 2024-01-02, ...)
    
    All writes go to the LATEST partition (right edge):
    
    ┌──────────┬──────────┬──────────┬══════════════╗
    │  Jan     │  Feb     │  Mar     ║  Apr (NOW)   ║
    │  idle    │  idle    │  idle    ║  ALL WRITES  ║ ← HOT!
    │  0 ops/s │  0 ops/s │  0 ops/s ║  100K ops/s  ║
    └──────────┴──────────┴──────────╚══════════════╝
    
    Mitigation: Prefix key with hash of another dimension
    Key = hash(sensor_id) + timestamp
    → spreads current-time writes across multiple partitions
```

---

### 3c. Compound/Composite Partitioning

**Mechanism:**

Use two (or more) key components:
1. **Partition key** — hashed to determine which partition
2. **Clustering key** — sorted within the partition for range access

```
    Table: user_posts
    Partition key: user_id (hashed)
    Clustering key: timestamp (sorted within partition)

    ┌─────────────────────────────────────────────────────────────┐
    │                    Logical View                               │
    │  (user_id, timestamp, content)                               │
    │  (alice,   2024-01-01, "Hello")                              │
    │  (alice,   2024-01-02, "World")                              │
    │  (bob,     2024-01-01, "Hi")                                 │
    │  (bob,     2024-01-03, "There")                              │
    └─────────────────────────────────────────────────────────────┘
                              │
                  hash(user_id) mod N
                              ▼
    ┌──────────────────────────────┬───────────────────────────────┐
    │        Partition 0           │         Partition 1            │
    │   hash("alice") mod 2 = 0   │   hash("bob") mod 2 = 1       │
    │                              │                                │
    │  alice | 2024-01-01 | Hello  │  bob | 2024-01-01 | Hi        │
    │  alice | 2024-01-02 | World  │  bob | 2024-01-03 | There     │
    │     ↑ sorted by timestamp    │     ↑ sorted by timestamp     │
    └──────────────────────────────┴───────────────────────────────┘

    Query: "All posts by alice in January 2024"
    → hash("alice") → Partition 0 → range scan on timestamp
    → Single partition, efficient range query!
    
    Query: "All posts by all users on 2024-01-01"
    → Must scatter-gather across ALL partitions (no partition key filter)
```

**Cassandra PRIMARY KEY Syntax:**
```sql
CREATE TABLE user_posts (
    user_id    TEXT,
    timestamp  TIMESTAMP,
    content    TEXT,
    PRIMARY KEY ((user_id), timestamp)  
    --          ^^^^^^^^^ partition key (hashed)
    --                     ^^^^^^^^^ clustering key (sorted)
) WITH CLUSTERING ORDER BY (timestamp DESC);
```

**Multi-Level Composite Keys:**
```sql
PRIMARY KEY ((tenant_id, user_id), event_date, event_id)
--           ^^^^^^^^^^^^^^^^^^^^^^ partition key (hashed together)
--                                  ^^^^^^^^^^^^^^^^^^ clustering (sorted)
```

This gives:
- Even distribution across tenants+users
- Efficient range scans within a user's events by date
- Unique identification by event_id within a date

---

### 3d. Directory-Based Partitioning

**Mechanism:**

A centralized lookup service maps each key (or key range) to its partition. Maximum flexibility — any key can be placed anywhere.

```
    ┌─────────┐         ┌─────────────────────────┐
    │ Client  │────────▶│   Directory Service      │
    │         │◀────────│   (Lookup Table)          │
    └─────────┘         │                           │
        │               │  key_range → partition     │
        │               │  "A-C"     → Partition 1   │
        │               │  "D-F"     → Partition 3   │
        │               │  "G-I"     → Partition 2   │
        │               │  "J-L"     → Partition 1   │ ← non-contiguous!
        │               │  ...                       │
        │               └─────────────────────────┘
        │                          │
        │       ┌──────────────────┼──────────────────┐
        ▼       ▼                  ▼                  ▼
    ┌────────┐ ┌────────┐    ┌────────┐         ┌────────┐
    │ Part 1 │ │ Part 2 │    │ Part 3 │         │ Part 4 │
    │ A-C,J-L│ │ G-I    │    │ D-F    │         │ M-Z    │
    └────────┘ └────────┘    └────────┘         └────────┘
```

**Trade-offs:**
| Advantage | Disadvantage |
|-----------|-------------|
| Arbitrary placement logic | Directory is SPOF |
| Easy rebalancing (update directory) | Extra network hop for every operation |
| Supports complex constraints | Directory must be highly available |
| Can encode business logic | Caching directory adds staleness risk |

**Use Cases:**
- Systems with regulatory constraints (certain data must be on certain nodes)
- Multi-tier storage (hot data on SSD nodes, cold on HDD)
- Apache HDFS NameNode (maps blocks to DataNodes)
- Apache Helix (generic cluster management with pluggable placement)

---

### 3e. Geographic Partitioning

**Mechanism:**

Data is partitioned based on the geographic region of the data subject or the user accessing it.

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                        Global System                             │
    └─────────────────────────────────────────────────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
    ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │   US-East        │ │   EU-West        │ │   APAC           │
    │   Region         │ │   Region         │ │   Region         │
    │                  │ │                  │ │                  │
    │  US user data    │ │  EU user data    │ │  APAC user data  │
    │  US regulations  │ │  GDPR compliant  │ │  Local laws      │
    │  Low latency US  │ │  Low latency EU  │ │  Low latency AP  │
    └──────────────────┘ └──────────────────┘ └──────────────────┘
    
    Partition key includes region:
      user_region:user_id → determines placement
    
    Cross-region queries require federation layer
```

**Drivers:**
- **Regulatory** — GDPR requires EU citizen data stays in EU; China's data localization laws
- **Latency** — Data physically close to users (CDN principle applied to databases)
- **Sovereignty** — Government data must remain within national borders
- **Disaster isolation** — Regional failure doesn't affect other regions

**Implementation Patterns:**
- CockroachDB: `PARTITION BY LIST` with zone constraints pinning to specific regions
- Spanner: Placement policies per database/table
- Cosmos DB: Multi-region writes with conflict resolution
- Vitess: Cell-based routing (cells map to datacenters)

---

## 4. Hot Spot Problem

Even with hash partitioning, hot spots emerge when a single key receives disproportionate traffic.

```
    Normal Distribution:              Hot Spot Scenario:
    
    Partition │████████│ 25%          Partition │██│ 5%
    Partition │████████│ 25%          Partition │██│ 5%
    Partition │████████│ 25%          Partition │██│ 5%
    Partition │████████│ 25%          Partition │██████████████████████████│ 85%
                                                              ↑
                                               Celebrity post goes viral
                                               All reads hit this partition
```

**Root Causes:**
1. **Celebrity problem** — Justin Bieber tweets, millions read from one partition
2. **Viral content** — Single item gets disproportionate access
3. **Time-based keys** — All current writes to latest partition
4. **Enumeration skew** — status="active" is 90% of rows

**Mitigation Strategies:**

```
    Strategy 1: Random Suffix (Write Spreading)
    ─────────────────────────────────────────────
    Original key: "celebrity_123"  → always same partition
    
    Modified:     "celebrity_123_" + random(0..9)
                  → "celebrity_123_0" → Partition A
                  → "celebrity_123_3" → Partition D
                  → "celebrity_123_7" → Partition H
    
    Write: append random suffix → spreads across 10 partitions
    Read:  must query ALL 10 suffixes and merge results
    
    ┌────────────┐  write("celeb_123_3")  ┌────────────┐
    │   Writer   │───────────────────────▶│ Partition D │
    └────────────┘                        └────────────┘
    
    ┌────────────┐  read("celeb_123_*")   ┌────────────┐
    │   Reader   │───────────────────────▶│ Partition A │ celeb_123_0
    │            │───────────────────────▶│ Partition B │ celeb_123_1
    │            │───────────────────────▶│ Partition C │ celeb_123_2
    │   (merge)  │───────────────────────▶│   ...       │ ...
    └────────────┘                        └────────────┘
    
    Trade-off: Write O(1), Read O(K) where K = suffix cardinality
```

```
    Strategy 2: Split Hot Partition
    ─────────────────────────────────
    Monitor partition sizes/traffic
    When partition exceeds threshold → split into sub-partitions
    
    Before:                          After:
    ┌────────────────────────┐      ┌────────────┬───────────┐
    │    Partition 3 (HOT)   │      │  Part 3a   │  Part 3b  │
    │    100K ops/sec        │  ──▶ │  50K ops/s │  50K ops/s│
    │    [M - Z]             │      │  [M - R]   │  [S - Z]  │
    └────────────────────────┘      └────────────┴───────────┘
```

```
    Strategy 3: Application-Level Sharding (Twitter's Approach)
    ──────────────────────────────────────────────────────────
    Celebrity timelines handled differently from normal users:
    
    Normal user (fan-out on write):
      Tweet → write to all follower timelines (small fan-out)
    
    Celebrity (fan-out on read):
      Tweet → write to celebrity's own timeline only
      Reader → merge celebrity tweets at read time
    
    ┌──────────────┐     tweet     ┌─────────────────────────┐
    │  Normal User │──────────────▶│ Write to 500 follower   │
    │  (500 fol.)  │               │ timelines (fan-out write)│
    └──────────────┘               └─────────────────────────┘
    
    ┌──────────────┐     tweet     ┌─────────────────────────┐
    │  Celebrity   │──────────────▶│ Write to OWN timeline   │
    │  (50M fol.)  │               │ only (no fan-out)       │
    └──────────────┘               └─────────────────────────┘
    
    ┌──────────────┐     read      ┌─────────────────────────┐
    │  Reader      │──────────────▶│ Fetch own timeline       │
    │              │               │ + merge celebrity feeds  │
    │              │               │ at query time            │
    └──────────────┘               └─────────────────────────┘
```

---

## 5. Rebalancing Strategies

When nodes are added/removed, partitions must be redistributed. The key constraint: **minimize data movement** while achieving balance.

### 5a. Fixed Number of Partitions

Create many more partitions than nodes upfront. Assign multiple partitions per node. When nodes change, move whole partitions.

```
    Initial: 12 partitions, 3 nodes
    
    Node 1:  [P0] [P1] [P2] [P3]
    Node 2:  [P4] [P5] [P6] [P7]
    Node 3:  [P8] [P9] [P10][P11]
    
    Add Node 4 → steal some partitions from each:
    
    Node 1:  [P0] [P1] [P2]
    Node 2:  [P4] [P5] [P6]
    Node 3:  [P8] [P9] [P10]
    Node 4:  [P3] [P7] [P11]       ← took 1 from each
    
    Only 3/12 = 25% of data moved (optimal: 1/4 = 25%)
```

**Trade-offs:**
- Must choose partition count at creation time
- Too few → can't balance well, too many → overhead
- Partition size grows with data (fixed count, growing dataset)
- Used by: Elasticsearch, Riak, early Cassandra, Redis Cluster (16384 slots)

### 5b. Dynamic Partitioning (Split/Merge)

Partitions split when too large, merge when too small. Number of partitions adapts to data size.

```
    Data grows → partitions split:
    
    Time 0:   [──────── P0 ────────]                    1 partition
              size = 1 GB
    
    Time 1:   [──── P0 ────][──── P1 ────]              2 partitions
              each ~5 GB     (split at 10 GB)
    
    Time 2:   [─P0─][─P1─][─P2─][─P3─]                 4 partitions
              each ~5 GB
    
    Data shrinks → partitions merge:
    
    Time 3:   [─P0─][─── P1+P2 ───][─P3─]              3 partitions
              (P1 and P2 merged when both < 1 GB)
```

**Properties:**
- Number of partitions proportional to data size
- Empty database starts with one partition (pre-splitting helps)
- Used by: HBase, CockroachDB, TiKV, DynamoDB

### 5c. Proportional to Nodes

Fixed number of partitions **per node**. Adding a node creates new partitions by splitting existing ones.

```
    Rule: 4 partitions per node
    
    3 nodes → 12 partitions
    4 nodes → 16 partitions (new node splits 4 existing partitions)
    5 nodes → 20 partitions
    
    Add node 4:
    Before:  Node1[P0,P1,P2,P3]  Node2[P4,P5,P6,P7]  Node3[P8,P9,P10,P11]
    
    Node 4 randomly picks 4 partitions to split:
    After:   Node1[P0,P1,P2,P3a]     (P3 split → keeps P3a)
             Node2[P4,P5,P6a,P7]     (P6 split → keeps P6a)
             Node3[P8,P9a,P10,P11]   (P9 split → keeps P9a)
             Node4[P3b,P6b,P9b,P12]  (gets split halves + new)
```

Used by: Cassandra (with vnodes).

### Comparison:

```
┌─────────────────────┬──────────────┬──────────────┬──────────────────┐
│                     │   Fixed      │   Dynamic    │   Proportional   │
│                     │   Count      │   Split/Merge│   to Nodes       │
├─────────────────────┼──────────────┼──────────────┼──────────────────┤
│ Partition count     │ Constant     │ Grows w/data │ Grows w/nodes    │
│ Partition size      │ Grows w/data │ Bounded      │ Bounded          │
│ Config needed       │ Choose N     │ Split thresh │ Per-node count   │
│ Empty DB overhead   │ All N exist  │ Starts at 1  │ Few partitions   │
│ Rebalance trigger   │ Node change  │ Size thresh  │ Node change      │
│ Data moved          │ Whole parts  │ Half parts   │ Half parts       │
│ Example systems     │ ES, Redis    │ HBase, CRDB  │ Cassandra        │
└─────────────────────┴──────────────┴──────────────┴──────────────────┘
```

**Why Rebalancing Must Not Move All Data:**

```
    BAD (naive hash mod N):
    ┌─────────────────────────────────────────────────────┐
    │  Adding 1 node to 10-node cluster                    │
    │  hash(key) mod 10 → hash(key) mod 11                │
    │  ~91% of keys change partition assignment            │
    │  Network saturated for hours, degraded performance   │
    └─────────────────────────────────────────────────────┘
    
    GOOD (partition-based rebalancing):
    ┌─────────────────────────────────────────────────────┐
    │  Adding 1 node to 10-node cluster (100 partitions)   │
    │  Move ~10 partitions to new node                     │
    │  ~10% of data moves                                  │
    │  Gradual, throttled, background operation            │
    └─────────────────────────────────────────────────────┘
```

---

## 6. Secondary Indexes with Partitioning

Primary key determines partition placement. But queries often use non-primary-key attributes (e.g., "find all orders with status=shipped"). Two approaches:

### 6a. Local Index (Document-Partitioned)

Each partition maintains its own secondary index covering only its local data.

```
    ┌─────────────────────────────────────────────────────────────────┐
    │                     Query: color = "red"                         │
    │              Must scatter to ALL partitions                       │
    └────────┬──────────────────┬──────────────────┬──────────────────┘
             │                  │                  │
             ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  Partition 0  │   │  Partition 1  │   │  Partition 2  │
    │              │   │              │   │              │
    │  Data:       │   │  Data:       │   │  Data:       │
    │  car:1 red   │   │  car:4 blue  │   │  car:7 red   │
    │  car:2 blue  │   │  car:5 red   │   │  car:8 green │
    │  car:3 red   │   │  car:6 green │   │  car:9 red   │
    │              │   │              │   │              │
    │  Local Index:│   │  Local Index:│   │  Local Index:│
    │  red → {1,3} │   │  red → {5}   │   │  red → {7,9} │
    │  blue → {2}  │   │  blue → {4}  │   │  green → {8} │
    └──────────────┘   └──────────────┘   └──────────────┘
             │                  │                  │
             └────────┬─────────┴──────────┬──────┘
                      ▼                    ▼
              Coordinator merges: red → {1,3,5,7,9}
    
    Write: O(1) — update local index only
    Read:  O(N) — scatter-gather to all N partitions (EXPENSIVE)
```

**Used by:** MongoDB, Cassandra, Elasticsearch (each shard has complete local Lucene index), DynamoDB (GSI is actually global, but LSI is local)

### 6b. Global Index (Term-Partitioned)

The index itself is partitioned — by the indexed term. Each index partition covers all data partitions but only for a subset of terms.

```
    ┌─────────────────────────────────────────────────────────────────┐
    │            Query: color = "red"                                   │
    │            Route to index partition for "red" → Index Part 1      │
    └──────────────────────────────┬──────────────────────────────────┘
                                   │ (single partition lookup)
                                   ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │  INDEX PARTITIONS (partitioned by term)                           │
    │                                                                   │
    │  Index Partition 0 (terms a-g):    Index Partition 1 (terms h-z): │
    │    blue → {2, 4}                     red → {1, 3, 5, 7, 9}       │
    │    green → {6, 8}                    silver → {10}               │
    └──────────────────────────────────────────────────────────────────┘
              ▲           ▲                     ▲           ▲
              │           │                     │           │
    ┌─────────┴──┐ ┌─────┴──────┐    ┌────────┴───┐ ┌────┴───────┐
    │ Data Part 0│ │ Data Part 1 │    │ Data Part 0│ │ Data Part 1 │
    │ car:1 red  │ │ car:4 blue  │    │ car:1 red  │ │ car:5 red   │
    │ car:2 blue │ │ car:5 red   │    │ car:3 red  │ │             │
    └────────────┘ └─────────────┘    └────────────┘ └─────────────┘
    
    Write: O(K) — must update K index partitions (one per indexed term value)
    Read:  O(1) — go to single index partition for the searched term
```

**Used by:** DynamoDB (Global Secondary Index), Google Cloud Spanner (interleaved indexes are local, non-interleaved are global)

### Comparison:

```
┌─────────────────────┬────────────────────────┬────────────────────────┐
│                     │  Local (Document)       │  Global (Term)         │
├─────────────────────┼────────────────────────┼────────────────────────┤
│ Write latency       │  Fast (local update)   │  Slow (cross-partition)│
│ Write consistency   │  Immediate             │  Often async (stale)   │
│ Read latency        │  Slow (scatter-gather) │  Fast (single lookup)  │
│ Read completeness   │  Immediate             │  May miss recent writes│
│ Best for            │  Write-heavy           │  Read-heavy            │
│ Complexity          │  Simple                │  Complex (distributed) │
└─────────────────────┴────────────────────────┴────────────────────────┘
```

---

## 7. Cross-Partition Queries

When a query cannot be routed to a single partition, the system must execute a **scatter-gather** pattern.

```
    Client Query: "SELECT * FROM orders WHERE status='pending' AND amount > 100"
    (No partition key specified → must check all partitions)
    
    ┌──────────┐
    │  Client  │
    └────┬─────┘
         │ query
         ▼
    ┌──────────────┐
    │  Coordinator │─── fans out query to all partitions
    │  (Router)    │
    └──┬───┬───┬───┘
       │   │   │
       ▼   ▼   ▼         Parallel execution
    ┌────┐┌────┐┌────┐
    │ P0 ││ P1 ││ P2 │   Each partition filters locally
    └─┬──┘└─┬──┘└─┬──┘
      │     │     │
      ▼     ▼     ▼       Partial results stream back
    ┌──────────────┐
    │  Coordinator │─── merges, sorts, limits, returns
    └──────┬───────┘
           │
           ▼
    ┌──────────┐
    │  Client  │  ← final result
    └──────────┘
```

**Costs of Scatter-Gather:**
- Latency = max(partition latencies) — slowest partition dominates
- Network amplification — N messages sent for one query
- Resource consumption — all partitions do work, even if they have no matches
- Tail latency amplification — P99 at N partitions ≈ P99^N probability of hitting slow path

**When to Denormalize vs. Cross-Partition Join:**

| Approach | When to Use |
|----------|------------|
| Denormalize (copy data) | Read-heavy, tolerance for staleness, simple access patterns |
| Scatter-gather | Infrequent queries, small cluster, acceptable latency |
| Materialized view | Known query patterns, can maintain async |
| Change partition key | If queries always filter by a specific field, make it the partition key |
| Dual-write / CQRS | Separate read model partitioned for query needs |

---

## 8. Real-World Implementations

### Apache Cassandra
- **Strategy:** Consistent hashing with Murmur3, vnodes (default 256 per node)
- **Partition key:** Hashed, determines token ring position
- **Clustering key:** Sorted within partition, enables range scans
- **Rebalancing:** Streaming vnodes to new nodes; can use tokens for manual placement
- **Hot spots:** Design partition key to avoid unbounded growth; use bucketing patterns
- **Max partition size:** Recommended < 100 MB, hard limits around ~2 billion cells

### MongoDB
- **Strategies:** Hashed sharding (even distribution) OR range sharding (range queries)
- **Shard key:** Immutable once chosen, 512-byte max
- **Chunks:** 64 MB default; auto-split when exceeded
- **Balancer:** Background process moves chunks between shards for balance
- **Limitations:** Multi-shard transactions (4.2+), scatter-gather for non-shard-key queries
- **Zones:** Tag-aware sharding for geo-placement

### Amazon DynamoDB
- **Strategy:** Hash partitioning with consistent hashing internally
- **Partition key:** Hash determines partition; optional sort key for range within
- **Adaptive capacity:** Automatically redistributes capacity from cool to hot partitions
- **Burst capacity:** Unused capacity saved for 5 minutes of burst
- **On-demand mode:** No capacity planning; auto-scales partitions
- **GSI:** Global secondary indexes (eventually consistent, separate partition space)

### Apache Kafka
- **Strategy:** Hash of message key mod partition_count
- **Null key:** Round-robin (pre-2.4) or sticky partitioning (2.4+, batch to one partition)
- **Partition count:** Fixed at topic creation (can only increase, not decrease)
- **Ordering:** Guaranteed only within a partition
- **Consumer groups:** Each partition assigned to exactly one consumer in group
- **Rebalancing:** Partition reassignment tool; follower catches up then becomes leader

### Apache HBase
- **Strategy:** Range partitioning with lexicographic key ordering
- **Regions:** Contiguous key ranges; auto-split at configurable threshold (default 10 GB)
- **RegionServer:** Each server hosts multiple regions
- **Hot-spotting mitigation:** Salting (prefix with hash), reversing key, hashing
- **Pre-splitting:** Create initial region boundaries for known key distributions
- **Compactions:** Merge small HFiles within a region

### Elasticsearch
- **Strategy:** Hash routing: `shard = hash(routing) % number_of_primary_shards`
- **Default routing:** Document `_id`; custom routing for co-locating related docs
- **Shard count:** Fixed at index creation (cannot change without reindex)
- **Over-sharding:** Recommended < 20 shards per GB heap, < 50 GB per shard
- **Index lifecycle:** Time-based indices (daily/weekly) with rollover
- **Shrink/Split API:** Create new index with fewer/more shards from existing

### CockroachDB
- **Strategy:** Range partitioning on primary key (lexicographic byte ordering)
- **Ranges:** Default 512 MB; auto-split when exceeded, auto-merge when small
- **Leaseholder:** One replica handles all reads for a range (locality optimization)
- **Zone configs:** Pin ranges to specific regions/nodes
- **Geo-partitioning:** `PARTITION BY LIST` on region column, zone constraints per partition
- **Rebalancing:** Automatic, considers storage, QPS, and locality

### Vitess (YouTube)
- **Strategy:** Application-defined sharding function (configurable: hash, range, custom)
- **VSchema:** Declarative mapping of tables to sharding strategy
- **Vindexes:** Virtual indexes that map column values to keyspace IDs
- **Resharding:** Online, transparent resharding with cut-over
- **Sequence tables:** Cross-shard auto-increment IDs
- **Scatter-gather:** VTGate routes and merges multi-shard queries

### PostgreSQL (Citus)
- **Distributed tables:** Hash-partitioned across worker nodes
- **Reference tables:** Small tables replicated to all nodes (for joins)
- **Co-location:** Tables with same distribution column placed together for local joins
- **Shard count:** Default 32; configurable at table creation
- **Rebalancing:** `rebalance_table_shards()` background operation
- **Query pushdown:** Coordinator pushes filters/joins to workers when possible

---

## 9. Partition Design Patterns

### Entity-Group Partitioning
Partition all related entities together so that operations on a logical group are local.

```
    Partition by: customer_id
    
    ┌─────────────────────────────────────────┐
    │         Partition: customer_42           │
    │                                          │
    │  customers(42, "Alice", ...)            │
    │  orders(1001, 42, "2024-01-01", ...)    │
    │  orders(1002, 42, "2024-01-15", ...)    │
    │  order_items(1001, "widget", 3)         │
    │  order_items(1002, "gadget", 1)         │
    │  payments(1001, "paid", ...)            │
    │                                          │
    │  → Single-partition transaction for      │
    │    "place order for customer 42"         │
    └─────────────────────────────────────────┘
```

Benefits: Single-partition transactions (fast, no 2PC), strong consistency within group, natural data locality.

### Time-Based Partitioning
```
    logs_2024_01  │  logs_2024_02  │  logs_2024_03  │  logs_2024_04
    ──────────────┼────────────────┼────────────────┼──────────────
    (cold, HDD)   │  (cold, HDD)   │  (warm, SSD)   │  (hot, SSD)
    (compressed)  │  (compressed)  │  (normal)      │  (normal)
    (read-only)   │  (read-only)   │  (read-mostly) │  (read-write)
```

Benefits: Easy TTL (drop old partition), tiered storage, writes concentrated on latest partition.

### Tenant-Based Partitioning (Multi-Tenancy)
```
    Small tenants: Co-located (shared partitions)
    ┌──────────────────────────────────┐
    │  Partition X (shared)            │
    │  tenant_a: 100 rows             │
    │  tenant_b: 50 rows              │
    │  tenant_c: 200 rows             │
    └──────────────────────────────────┘
    
    Large tenants: Dedicated partitions (isolation)
    ┌──────────────────────────────────┐
    │  Partition Y (dedicated)         │
    │  tenant_enterprise: 10M rows    │
    │  (own partition = guaranteed     │
    │   resources, no noisy neighbor)  │
    └──────────────────────────────────┘
```

### Hierarchical Partitioning
```
    Level 1: Region (geographic)
    Level 2: Tenant (business isolation)
    Level 3: Entity type (access pattern)
    
    Key: /us-east/tenant-42/orders/1001
         ───────  ─────────  ──────  ────
         region   tenant     type    id
    
    Routing: region → datacenter → tenant partition → local storage
```

---

## 10. Common Pitfalls

### 1. Wrong Partition Key
```
    MISTAKE: Partition by order_id for an e-commerce system
    
    Queries needed:
    - "All orders for customer X"     → scatter-gather (BAD)
    - "All orders in last hour"       → scatter-gather (BAD)
    - "Order 12345 details"           → single partition (good, but rare)
    
    BETTER: Partition by customer_id
    - "All orders for customer X"     → single partition (GOOD)
    - "Order 12345 details"           → need customer→order index, but worth it
```

### 2. Too Few Partitions
- Can't parallelize beyond partition count
- Hot partitions can't be split (in fixed-count systems)
- Adding nodes doesn't help if fewer partitions than nodes
- Rule of thumb: partitions >= 10x expected max node count

### 3. Too Many Partitions
- Per-partition overhead (metadata, file handles, memory)
- Elasticsearch: each shard is a Lucene index (~20 MB overhead minimum)
- Kafka: too many partitions increases leader election time
- More partitions = more scatter-gather overhead
- Rule of thumb: partition size 1-10 GB for most systems

### 4. Not Planning for Rebalancing
- Fixed shard key with no migration strategy
- Choosing a partition count that can't be changed (Elasticsearch, Kafka)
- Not testing rebalancing under production load
- No capacity headroom during rebalance (data temporarily doubled on receiving node)

### 5. Unbounded Partition Growth
```
    Key: user_id (fine for most users)
    
    But: Power user with 100M records in one partition
    → Partition exceeds node capacity
    → Can't split without changing partition key
    
    Prevention: Monitor partition sizes, add bucketing
    Key: (user_id, bucket_number) where bucket = sequence / 1M
```

### 6. Cross-Partition Transactions Everywhere
- If every operation spans partitions, you've chosen wrong boundaries
- 2PC/Saga for every write = massive latency and failure surface
- Redesign: change partition key or denormalize

---

## 11. Architect's Guide

### Choosing a Partition Key

**Decision Framework:**

```
    ┌─────────────────────────────────────────────────────────────┐
    │            PARTITION KEY SELECTION FLOWCHART                  │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │  1. What is the most common query filter?                 │
    │     (The field in WHERE clause of 80%+ queries)           │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │  2. Does it have high cardinality?                        │
    │     YES → good candidate                                  │
    │     NO  → combine with another field                      │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │  3. Is it uniformly distributed?                          │
    │     YES → can use range or hash                           │
    │     NO  → must use hash (or accept skew)                  │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │  4. Do queries need range scans on this field?            │
    │     YES → range partition (or composite with clustering)  │
    │     NO  → hash partition                                  │
    └──────────────────────────┬───────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────┐
    │  5. Can any single key value grow unbounded?              │
    │     YES → add bucketing/time-window to key                │
    │     NO  → proceed                                         │
    └──────────────────────────────────────────────────────────┘
```

### Estimating Partition Count

```
    Target partition size: S (e.g., 5 GB)
    Total data size now: D
    Growth rate: G per year
    Planning horizon: Y years
    
    Future data size: D_future = D + (G × Y)
    
    Minimum partitions: D_future / S
    
    Example:
      D = 500 GB now
      G = 200 GB/year
      Y = 3 years
      S = 5 GB target
      
      D_future = 500 + 600 = 1100 GB
      Min partitions = 1100 / 5 = 220
      
      With headroom (2x): 440 partitions
      Round to power of 2: 512 partitions
```

### Planning for Growth

| Growth Phase | Strategy |
|-------------|----------|
| Startup (< 100 GB) | Single node or minimal partitions; over-partition slightly |
| Growth (100 GB - 10 TB) | Fixed partitions with auto-rebalance; monitor skew |
| Scale (10 TB+) | Dynamic partitioning; dedicated teams for shard management |
| Hyperscale (PB+) | Hierarchical partitioning; regional deployments; custom routing |

### Cross-Partition Operation Handling

**Decision Matrix:**

| Scenario | Recommended Approach |
|----------|---------------------|
| < 5% queries cross-partition | Accept scatter-gather cost |
| Frequent joins across partitions | Co-locate via same partition key or reference tables |
| Aggregation across all data | Maintain pre-computed materialized views |
| Transaction across partitions | Use Saga pattern; accept eventual consistency |
| Reporting/analytics | Separate OLAP system (data warehouse/lake) |

### Summary: Strategy Selection Guide

```
┌───────────────────────┬─────────────────────────────────────────────────────┐
│  If you need...       │  Use...                                             │
├───────────────────────┼─────────────────────────────────────────────────────┤
│  Even distribution    │  Hash partitioning                                  │
│  Range queries        │  Range partitioning                                 │
│  Both                 │  Composite (hash partition + sort clustering)        │
│  Regulatory placement │  Geographic partitioning                            │
│  Complex rules        │  Directory-based partitioning                       │
│  Time-series data     │  Time-based + hash prefix to avoid hot partition    │
│  Multi-tenant         │  Tenant-based (small shared, large dedicated)       │
│  Graph/relationship   │  Entity-group partitioning                          │
└───────────────────────┴─────────────────────────────────────────────────────┘
```

---

## References

- Kleppmann, M. *Designing Data-Intensive Applications*, Chapter 6: Partitioning
- Cassandra Documentation: Data Modeling and Partition Keys
- MongoDB Manual: Sharding
- DynamoDB Developer Guide: Partition Key Design
- HBase Reference: Region Splitting
- Kafka Documentation: Partitioner Interface
- CockroachDB Docs: Architecture — Distribution Layer
- Vitess Documentation: Sharding
