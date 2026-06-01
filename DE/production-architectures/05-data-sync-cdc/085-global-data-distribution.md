# Global Data Distribution Architecture (Multi-region Writes)

## Problem Statement

Global applications serving users across continents need sub-100ms response times, which is physically impossible with a single-region database (cross-Atlantic latency alone is 80-120ms). Active-active multi-region writes are required, but they introduce the hardest problem in distributed systems: concurrent writes to the same data from different regions. At billion-scale with 99.99% availability requirements, we need conflict-free replication, causal consistency guarantees, intelligent geo-routing, and graceful handling of network partitions—all while keeping operational complexity manageable.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Global DNS + Routing"
        DNS[Route53 / CloudFlare<br/>Geo-routing]
        GLB[Global Load Balancer<br/>Latency-based]
    end

    subgraph "US-East Region"
        APP_US[Application Fleet<br/>US-East]
        DB_US[(CockroachDB / Spanner<br/>Regional Node)]
        CACHE_US[Redis<br/>Regional Cache]
        KAFKA_US[Kafka<br/>Regional Cluster]
    end

    subgraph "EU-West Region"
        APP_EU[Application Fleet<br/>EU-West]
        DB_EU[(CockroachDB / Spanner<br/>Regional Node)]
        CACHE_EU[Redis<br/>Regional Cache]
        KAFKA_EU[Kafka<br/>Regional Cluster]
    end

    subgraph "AP-Southeast Region"
        APP_AP[Application Fleet<br/>AP-Southeast]
        DB_AP[(CockroachDB / Spanner<br/>Regional Node)]
        CACHE_AP[Redis<br/>Regional Cache]
        KAFKA_AP[Kafka<br/>Regional Cluster]
    end

    subgraph "Global Replication"
        CRDT[CRDT Resolution<br/>Layer]
        CAUSAL[Causal Consistency<br/>Engine]
        CONFLICT[Conflict Resolution<br/>Service]
        MM2_1[Kafka MirrorMaker<br/>US <-> EU]
        MM2_2[Kafka MirrorMaker<br/>EU <-> AP]
        MM2_3[Kafka MirrorMaker<br/>US <-> AP]
    end

    subgraph "Consistency Layer"
        HLC[Hybrid Logical<br/>Clocks]
        QUORUM[Quorum Reads<br/>(when needed)]
        LINEARIZE[Linearizable Reads<br/>(critical path)]
    end

    DNS --> GLB
    GLB --> APP_US
    GLB --> APP_EU
    GLB --> APP_AP

    APP_US --> DB_US
    APP_US --> CACHE_US
    APP_US --> KAFKA_US

    APP_EU --> DB_EU
    APP_EU --> CACHE_EU
    APP_EU --> KAFKA_EU

    APP_AP --> DB_AP
    APP_AP --> CACHE_AP
    APP_AP --> KAFKA_AP

    DB_US <--> CRDT
    DB_EU <--> CRDT
    DB_AP <--> CRDT

    CRDT --> CAUSAL
    CAUSAL --> HLC

    KAFKA_US <--> MM2_1 <--> KAFKA_EU
    KAFKA_EU <--> MM2_2 <--> KAFKA_AP
    KAFKA_US <--> MM2_3 <--> KAFKA_AP

    CONFLICT --> QUORUM
    CONFLICT --> LINEARIZE
```

## Component Breakdown

### CRDTs (Conflict-free Replicated Data Types)

```python
"""
CRDTs guarantee convergence without coordination.
All replicas reach the same state regardless of operation order.
"""

class GCounter:
    """Grow-only counter - counts always converge (e.g., page views)"""
    def __init__(self, node_id: str, num_nodes: int):
        self.node_id = node_id
        self.counts = [0] * num_nodes
    
    def increment(self):
        self.counts[self._node_index()] += 1
    
    def value(self) -> int:
        return sum(self.counts)
    
    def merge(self, other: 'GCounter'):
        for i in range(len(self.counts)):
            self.counts[i] = max(self.counts[i], other.counts[i])


class PNCounter:
    """Positive-Negative counter (e.g., inventory, likes)"""
    def __init__(self, node_id: str, num_nodes: int):
        self.positive = GCounter(node_id, num_nodes)
        self.negative = GCounter(node_id, num_nodes)
    
    def increment(self): self.positive.increment()
    def decrement(self): self.negative.increment()
    def value(self) -> int: return self.positive.value() - self.negative.value()
    
    def merge(self, other: 'PNCounter'):
        self.positive.merge(other.positive)
        self.negative.merge(other.negative)


class LWWMap:
    """Last-Writer-Wins Map (e.g., user profile fields)"""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.entries = {}  # key -> (value, timestamp, node_id)
    
    def set(self, key: str, value, timestamp: int):
        existing = self.entries.get(key)
        if existing is None or timestamp > existing[1] or \
           (timestamp == existing[1] and self.node_id > existing[2]):
            self.entries[key] = (value, timestamp, self.node_id)
    
    def get(self, key: str):
        entry = self.entries.get(key)
        return entry[0] if entry else None
    
    def merge(self, other: 'LWWMap'):
        for key, (value, ts, node) in other.entries.items():
            self.set(key, value, ts)


class ORSet:
    """Observed-Remove Set - add/remove without conflicts (e.g., shopping cart)"""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.adds = {}    # element -> set of (unique_tag, timestamp)
        self.removes = {} # element -> set of unique_tags
    
    def add(self, element):
        tag = f"{self.node_id}:{uuid.uuid4()}"
        self.adds.setdefault(element, set()).add((tag, time.time()))
    
    def remove(self, element):
        if element in self.adds:
            # Only remove tags we've seen
            for tag, _ in self.adds[element]:
                self.removes.setdefault(element, set()).add(tag)
    
    def contains(self, element) -> bool:
        if element not in self.adds:
            return False
        active_tags = {tag for tag, _ in self.adds[element]}
        removed_tags = self.removes.get(element, set())
        return bool(active_tags - removed_tags)
    
    def merge(self, other: 'ORSet'):
        for elem, tags in other.adds.items():
            self.adds.setdefault(elem, set()).update(tags)
        for elem, tags in other.removes.items():
            self.removes.setdefault(elem, set()).update(tags)
```

### Hybrid Logical Clocks (HLC)

```python
class HybridLogicalClock:
    """
    Combines physical time with logical ordering.
    Provides causal ordering without perfectly synchronized clocks.
    Used by CockroachDB, MongoDB, etc.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.physical = 0  # Wall clock (milliseconds)
        self.logical = 0   # Logical counter
    
    def now(self) -> tuple:
        """Generate new timestamp for local event"""
        wall = self._wall_clock_ms()
        
        if wall > self.physical:
            self.physical = wall
            self.logical = 0
        else:
            self.logical += 1
        
        return (self.physical, self.logical, self.node_id)
    
    def receive(self, remote_physical: int, remote_logical: int):
        """Update clock on receiving remote message"""
        wall = self._wall_clock_ms()
        
        if wall > self.physical and wall > remote_physical:
            self.physical = wall
            self.logical = 0
        elif remote_physical > self.physical:
            self.physical = remote_physical
            self.logical = remote_logical + 1
        elif self.physical == remote_physical:
            self.logical = max(self.logical, remote_logical) + 1
        else:
            self.logical += 1
        
        return (self.physical, self.logical, self.node_id)
    
    @staticmethod
    def compare(ts1: tuple, ts2: tuple) -> int:
        """Compare two HLC timestamps: -1, 0, or 1"""
        if ts1[0] != ts2[0]:
            return -1 if ts1[0] < ts2[0] else 1
        if ts1[1] != ts2[1]:
            return -1 if ts1[1] < ts2[1] else 1
        return 0  # Concurrent (or same)
```

### Causal Consistency Implementation

```python
class CausalConsistencyManager:
    """
    Ensures causal ordering: if operation A causally precedes B,
    all replicas see A before B. Concurrent operations may be in any order.
    
    Implementation: Each write carries a vector clock.
    Reads wait until all causal dependencies are satisfied.
    """
    
    def __init__(self, region: str, num_regions: int):
        self.region = region
        self.local_clock = [0] * num_regions
        self.pending_writes = []  # Writes waiting for causal deps
    
    def write(self, data: dict, client_clock: list) -> dict:
        """
        Accept write only if all causal dependencies are met locally.
        """
        # Update local clock
        self.local_clock[self._region_index()] += 1
        
        # Merge client's causal context
        for i, c in enumerate(client_clock):
            self.local_clock[i] = max(self.local_clock[i], c)
        
        # Attach clock to write for replication
        write_record = {
            'data': data,
            'vector_clock': self.local_clock.copy(),
            'origin_region': self.region,
            'hlc_timestamp': self.hlc.now()
        }
        
        return write_record
    
    def receive_replicated_write(self, write_record: dict):
        """
        Apply replicated write only when causal dependencies are satisfied.
        """
        remote_clock = write_record['vector_clock']
        
        # Check if all causal dependencies are met
        if self._causal_deps_satisfied(remote_clock):
            self._apply_write(write_record)
            self._process_pending()
        else:
            # Queue until dependencies arrive
            self.pending_writes.append(write_record)
    
    def _causal_deps_satisfied(self, remote_clock: list) -> bool:
        """All entries except sender's must be <= our local clock"""
        sender_idx = self._region_index_for(remote_clock)
        for i, c in enumerate(remote_clock):
            if i == sender_idx:
                continue  # Skip sender's own counter
            if c > self.local_clock[i]:
                return False  # We haven't seen a dependency yet
        return True
```

### Geo-Routing Strategy

```python
class GeoRouter:
    """
    Routes requests to optimal region based on:
    1. User location (latency)
    2. Data locality (where the entity lives)
    3. Consistency requirements
    """
    
    REGION_MAP = {
        'NA': 'us-east-1',
        'EU': 'eu-west-1',
        'AP': 'ap-southeast-1',
    }
    
    def route_request(self, request) -> str:
        # Determine optimal region
        user_region = self._detect_user_region(request.client_ip)
        
        if request.consistency == 'strong':
            # Must go to leader region for this entity
            entity_leader = self._get_entity_leader(request.entity_id)
            return entity_leader
        
        if request.type == 'read':
            # Reads can go to nearest region (eventual/causal consistency)
            return self.REGION_MAP[user_region]
        
        if request.type == 'write':
            # Writes to local region (async replication)
            # Unless entity has regional affinity
            entity_home = self._get_entity_home_region(request.entity_id)
            if entity_home:
                return entity_home
            return self.REGION_MAP[user_region]
    
    def _get_entity_home_region(self, entity_id: str) -> str:
        """
        Some entities have a "home" region to minimize conflicts:
        - User profiles: where user registered
        - Orders: where order was placed
        - Shared resources: designated primary region
        """
        # Lookup in routing table
        return self.routing_table.get(entity_id)
```

### Data Partitioning for Global Distribution

```
Strategy 1: Geo-Partitioned Data
┌─────────────────────────────────────────────┐
│ US users → US-East region (primary)         │
│ EU users → EU-West region (primary)         │
│ AP users → AP-Southeast region (primary)    │
│                                             │
│ Each region has READ replicas of all data   │
│ WRITES only to home region (no conflicts)   │
└─────────────────────────────────────────────┘

Strategy 2: Sharded by Entity (Any Region Writes)
┌─────────────────────────────────────────────┐
│ All regions can write any entity            │
│ CRDTs handle conflicts automatically        │
│ Suitable for: counters, sets, LWW fields    │
│ NOT suitable for: financial transactions    │
└─────────────────────────────────────────────┘

Strategy 3: Hybrid
┌─────────────────────────────────────────────┐
│ Critical data: Geo-partitioned (no conflict)│
│ User profile: LWW Register (CRDT)          │
│ Inventory: PN-Counter (CRDT)               │
│ Shopping cart: OR-Set (CRDT)               │
│ Orders: Routed to single region            │
└─────────────────────────────────────────────┘
```

## Data Flow

```
Write Flow (Active-Active):
1. User in EU makes request
2. DNS routes to EU-West application
3. App writes to local EU database node
4. HLC timestamp assigned
5. Write acknowledged to user (low latency)
6. Async replication to US-East and AP-Southeast
7. Remote regions apply write (respecting causal order)
8. Global convergence within replication lag window

Read Flow (Causal Consistency):
1. User reads from local region
2. Check: does local replica have user's causal context?
3. If yes: serve immediately (fast path)
4. If no: wait briefly for replication, or forward to leader

Read Flow (Strong Consistency - rare):
1. Must read from leader (or quorum)
2. Cross-region latency added (~100-200ms)
3. Only used for: financial balances, inventory counts
```

## Scaling Strategies

### Database Technology Choices

| Technology | Consistency | Multi-region | Write Latency |
|-----------|-------------|--------------|---------------|
| CockroachDB | Serializable | Built-in | ~50ms (regional), ~200ms (global) |
| Google Spanner | External consistency | Built-in | ~10ms (TrueTime) |
| Yugabyte | Configurable | Built-in | ~10ms (regional) |
| Cassandra | Tunable (eventual default) | Built-in | ~5ms (local quorum) |
| DynamoDB Global Tables | Eventually consistent | Managed | ~20ms (local) |
| Custom (PostgreSQL + CRDTs) | Application-level | Custom | ~5ms (local) |

### Replication Topology
```
3 Regions: Full mesh (each replicates to other 2)
- Replication lag: 80-150ms (cross-Atlantic)
- Replication lag: 150-250ms (US to Asia)

5+ Regions: Hub-and-spoke or hierarchical
- Primary hubs: US, EU, AP
- Secondary: regions replicate from nearest hub
- Reduces cross-region connections from N² to N
```

## Failure Handling

| Failure | Impact | Resolution |
|---------|--------|------------|
| Single region down | 1/3 users affected | DNS failover to next-nearest region |
| Network partition (US-EU) | Regions diverge | Continue accepting writes, reconcile on heal |
| Clock skew > threshold | Ordering issues | HLC handles moderate skew; alert if extreme |
| Conflict storm | Excessive merges | Rate limit + investigate root cause |
| Replication lag spike | Stale reads possible | Alert, consider routing writes to healthy regions |
| Split-brain (all links down) | Full divergence | Longest partition wins? Or manual intervention |

### Partition Tolerance Strategy
```python
class PartitionHandler:
    """
    During network partition:
    - Continue accepting reads AND writes locally (AP choice)
    - Queue writes for replication when partition heals
    - Use CRDTs to auto-resolve conflicts
    - For non-CRDT data: buffer writes, apply LWW on heal
    """
    
    def on_partition_detected(self, disconnected_regions: list):
        # Switch to local-only mode for disconnected regions
        self.replication_state = 'partitioned'
        
        # Increase local write buffer
        # Alert operations team
        # Start accumulating conflict metrics
    
    def on_partition_healed(self, reconnected_regions: list):
        # Exchange all buffered writes
        # CRDTs merge automatically
        # Non-CRDT conflicts logged for review
        # Verify convergence
        self.replication_state = 'healthy'
```

## Cost Optimization

| Component | Monthly Cost (3 regions) | Notes |
|-----------|--------------------------|-------|
| CockroachDB (3 regions × 3 nodes) | ~$15,000 | Or Spanner: $18,000 |
| Cross-region transfer | ~$5,000 | Replication bandwidth |
| Kafka (3 regional clusters + MM2) | ~$14,000 | Event replication |
| Redis (3 regional clusters) | ~$5,400 | Regional caching |
| Global DNS + load balancer | ~$500 | Route53 + CloudFront |
| Application fleet (3 regions) | ~$12,000 | Auto-scaling per region |
| **Total** | **~$52,000/month** | Active-active, 3 regions |

### Cost Reduction Strategies
```
1. Reduce regions: 2 active + 1 warm saves 30%
2. Geo-partition data: most data only in home region
3. Cache aggressively: reduce cross-region DB reads
4. Compress replication: LZ4 for cross-region traffic
5. Right-size: not all services need global distribution
6. Use managed: Spanner/DynamoDB Global Tables vs self-managed
```

## Real-World Companies

| Company | Approach | Scale |
|---------|----------|-------|
| **Google** | Spanner (TrueTime, external consistency) | Global, billions of rows |
| **CockroachDB** | Serializable global transactions | Multi-region SQL |
| **Netflix** | Active-active Cassandra (eventual) | 3+ regions |
| **Uber** | Custom (Schemaless + CRDTs) | Global ride matching |
| **Slack** | Regional with selective replication | Multi-region messages |
| **Discord** | Cassandra + ScyllaDB (multi-region) | Global messaging |
| **Figma** | CRDTs for collaborative editing | Real-time global |
| **Apple iCloud** | Custom replication (FoundationDB) | Global user data |
| **Cloudflare** | Workers KV (eventually consistent) | 200+ PoPs globally |
