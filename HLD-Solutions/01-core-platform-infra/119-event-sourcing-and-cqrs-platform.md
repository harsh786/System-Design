# Event Sourcing & CQRS Platform

## 1. Functional Requirements

### Core Features
- **Event Store**: Append-only, immutable log of all domain events
- **Event Ordering**: Strict ordering per aggregate, global ordering across streams
- **Projection Builder**: Build and maintain materialized read models from events
- **Snapshotting**: Periodic aggregate state snapshots for fast reconstitution
- **Event Replay**: Replay all or partial events to rebuild state or create new projections
- **Subscriptions**: Real-time notifications on new events (push and pull)
- **Schema Registry**: Event versioning, evolution, and backward/forward compatibility
- **Saga Orchestrator**: Long-running processes as event-driven state machines

### User Stories
1. Application writes domain event → event store persists with ordering guarantees
2. Projection builder consumes events → builds read-optimized view in <100ms
3. New feature needs historical data → replay all events to build new projection
4. Aggregate loaded → hydrate from latest snapshot + subsequent events
5. Long-running order fulfillment → saga coordinates across multiple services
6. Event schema evolves → old events upcasted transparently to new version

---

## 2. Non-Functional Requirements

| Metric | Target |
|--------|--------|
| Availability | 99.99% |
| Write Latency | <5ms p99 (event append) |
| Projection Lag | <100ms p99 (event to materialized view) |
| Throughput | 1M events/sec sustained write |
| Storage | Petabytes of event history |
| Event Replay Speed | 500K events/sec per consumer |
| Ordering Guarantee | Strict per aggregate, causal across streams |
| Durability | Zero event loss (replicated, fsync'd) |
| Snapshot Frequency | Every 100 events or 1 minute |

---

## 3. Capacity Estimation

### Event Volume
```
Events per second: 1,000,000
Average event size: 500 bytes (header) + 1KB (payload) = 1.5KB
Daily events: 1M × 86,400 = 86.4 billion
Daily storage: 86.4B × 1.5KB = ~130TB/day raw

With compression (3:1): ~43TB/day
With replication (3x): ~130TB/day total disk
Annual: ~47PB (before compaction/archival)

Streams (aggregates): 100M active
Events per stream (avg): 1000 over lifetime
Snapshots: 100M aggregates × 5KB avg = 500GB snapshot store
```

### Read Model (Projections)
```
Active projections: 50 different read models
Events consumed: 50 × 1M/sec = 50M event reads/sec (fan-out)
Projection databases: Various (Postgres, Elasticsearch, Redis)
Projection rebuild time: 86.4B events / 500K/sec = ~48 hours full rebuild
```

### Infrastructure
```
Event Store Cluster:
  - 100 nodes × 32 cores × 128GB RAM × 10TB NVMe
  - Partitioned by aggregate_id hash
  - 3x replication per partition

Projection Workers:
  - 200 workers × 16 cores × 64GB RAM
  - Stateless, horizontally scalable

Saga Orchestrator:
  - 20 nodes × 16 cores × 64GB RAM
  - State stored in event store itself

Schema Registry:
  - 3 nodes (small, metadata only)
  - <1GB total storage
```

---

## 4. Data Modeling

### Event Schema
```protobuf
message StoredEvent {
  // Identity
  string event_id = 1;           // UUID, globally unique
  string stream_id = 2;          // Aggregate ID (e.g., "order-12345")
  string stream_type = 3;        // Aggregate type (e.g., "Order")
  uint64 stream_position = 4;    // Position within stream (0-indexed)
  uint64 global_position = 5;    // Global ordering sequence
  
  // Metadata
  string event_type = 6;         // e.g., "OrderPlaced", "ItemAdded"
  uint32 schema_version = 7;     // Schema version for this event type
  int64 timestamp = 8;           // HLC timestamp
  string correlation_id = 9;     // Trace correlation
  string causation_id = 10;      // Which event caused this one
  map<string, string> metadata = 11;  // Custom headers
  
  // Payload
  bytes data = 12;               // Serialized event payload (JSON/Protobuf/Avro)
  string content_type = 13;      // "application/json", "application/protobuf"
}

// Example domain events
message OrderPlaced {
  string order_id = 1;
  string customer_id = 2;
  repeated OrderItem items = 3;
  Money total_amount = 4;
  Address shipping_address = 5;
  google.protobuf.Timestamp placed_at = 6;
}

message OrderItemAdded {
  string order_id = 1;
  string product_id = 2;
  uint32 quantity = 3;
  Money unit_price = 4;
}

message OrderShipped {
  string order_id = 1;
  string tracking_number = 2;
  string carrier = 3;
  google.protobuf.Timestamp shipped_at = 4;
}

message OrderCancelled {
  string order_id = 1;
  string reason = 2;
  string cancelled_by = 3;
  google.protobuf.Timestamp cancelled_at = 4;
}
```

### Snapshot Schema
```protobuf
message Snapshot {
  string stream_id = 1;
  string stream_type = 2;
  uint64 stream_position = 3;     // Position snapshot was taken at
  bytes state = 4;                 // Serialized aggregate state
  int64 timestamp = 5;
  string schema_version = 6;
}
```

### Projection Checkpoint Schema
```sql
CREATE TABLE projection_checkpoints (
    projection_name     VARCHAR(255) PRIMARY KEY,
    last_global_position BIGINT NOT NULL,
    last_processed_at    TIMESTAMP WITH TIME ZONE,
    status              VARCHAR(20),  -- running, paused, rebuilding, error
    error_message       TEXT,
    events_processed    BIGINT DEFAULT 0,
    lag_ms              INT,          -- current lag behind head
    created_at          TIMESTAMP WITH TIME ZONE,
    updated_at          TIMESTAMP WITH TIME ZONE
);

CREATE TABLE projection_dead_letters (
    id                  BIGSERIAL PRIMARY KEY,
    projection_name     VARCHAR(255),
    event_id            UUID,
    global_position     BIGINT,
    error_message       TEXT,
    retry_count         INT DEFAULT 0,
    max_retries         INT DEFAULT 5,
    next_retry_at       TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE
);
```

### Saga State Schema
```sql
CREATE TABLE saga_instances (
    saga_id             UUID PRIMARY KEY,
    saga_type           VARCHAR(255) NOT NULL,
    current_state       VARCHAR(100) NOT NULL,
    data                JSONB NOT NULL,           -- saga accumulated data
    started_at          TIMESTAMP WITH TIME ZONE,
    last_transition_at  TIMESTAMP WITH TIME ZONE,
    timeout_at          TIMESTAMP WITH TIME ZONE, -- deadline for completion
    version             BIGINT DEFAULT 0,         -- optimistic concurrency
    status              VARCHAR(20),              -- active, completed, compensating, failed
    
    -- Events that triggered transitions
    pending_commands    JSONB DEFAULT '[]',       -- commands to dispatch
    completed_steps     JSONB DEFAULT '[]',
    compensation_log    JSONB DEFAULT '[]'        -- for rollback
);

CREATE INDEX idx_saga_timeout ON saga_instances(timeout_at) 
    WHERE status = 'active';
CREATE INDEX idx_saga_type_state ON saga_instances(saga_type, current_state);
```

### Schema Registry Tables
```sql
CREATE TABLE event_schemas (
    event_type          VARCHAR(255),
    schema_version      INT,
    schema_definition   JSONB NOT NULL,    -- JSON Schema / Avro / Protobuf descriptor
    compatibility_mode  VARCHAR(20),       -- backward, forward, full, none
    created_at          TIMESTAMP WITH TIME ZONE,
    deprecated_at       TIMESTAMP WITH TIME ZONE,
    
    PRIMARY KEY (event_type, schema_version)
);

CREATE TABLE schema_upcasters (
    event_type          VARCHAR(255),
    from_version        INT,
    to_version          INT,
    upcaster_code       TEXT,             -- transformation logic (JavaScript/JSON path)
    is_reversible       BOOLEAN DEFAULT FALSE,
    
    PRIMARY KEY (event_type, from_version, to_version)
);
```

---

## 5. High-Level Design (HLD)

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WRITE SIDE (Command)                            │
│                                                                             │
│  ┌─────────────┐    ┌─────────────────┐    ┌───────────────────────────┐   │
│  │  Command    │    │  Aggregate      │    │      EVENT STORE          │   │
│  │  Handler    │───▶│  Root           │───▶│                           │   │
│  │             │    │  (Domain Logic) │    │  ┌─────────────────────┐  │   │
│  │ - Validate  │    │  - Load state   │    │  │ Partition 0         │  │   │
│  │ - Route     │    │  - Apply event  │    │  │ [e1][e2][e3]...     │  │   │
│  │             │    │  - Check rules  │    │  ├─────────────────────┤  │   │
│  └─────────────┘    └─────────────────┘    │  │ Partition 1         │  │   │
│                                            │  │ [e1][e2][e3]...     │  │   │
│                                            │  ├─────────────────────┤  │   │
│                                            │  │ Partition N         │  │   │
│                                            │  │ [e1][e2]...         │  │   │
│                                            │  └─────────────────────┘  │   │
│                                            │                           │   │
│                                            │  Global Position Index    │   │
│                                            │  Snapshot Store           │   │
│                                            └──────────┬────────────────┘   │
└───────────────────────────────────────────────────────┼────────────────────┘
                                                        │
                    ┌───────────────────────────────────┼──────────────────┐
                    │          EVENT BUS / SUBSCRIPTIONS │                  │
                    │                                    ▼                  │
                    │  ┌──────────────────────────────────────────────┐    │
                    │  │  Subscription Manager                        │    │
                    │  │  - Catch-up subscriptions (from position X)  │    │
                    │  │  - Live subscriptions (real-time push)       │    │
                    │  │  - Persistent subscriptions (with ACK)       │    │
                    │  └───────┬──────────────┬──────────────┬───────┘    │
                    └──────────┼──────────────┼──────────────┼────────────┘
                               │              │              │
┌──────────────────────────────┼──────────────┼──────────────┼────────────────┐
│                    READ SIDE │(Query / CQRS)│              │                │
│                              ▼              ▼              ▼                │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │  Projection A   │  │ Projection B│  │ Projection C│  │ Saga Engine  │ │
│  │  (Order List)   │  │ (Analytics) │  │ (Search)    │  │              │ │
│  │       │         │  │      │      │  │      │      │  │  State       │ │
│  │       ▼         │  │      ▼      │  │      ▼      │  │  Machine     │ │
│  │  ┌─────────┐   │  │ ┌────────┐  │  │ ┌────────┐  │  │  Engine      │ │
│  │  │Postgres │   │  │ │ClickHse│  │  │ │Elastic │  │  │       │      │ │
│  │  │(SQL)    │   │  │ │(OLAP)  │  │  │ │Search  │  │  │       ▼      │ │
│  │  └─────────┘   │  │ └────────┘  │  │ └────────┘  │  │  Commands    │ │
│  └─────────────────┘  └─────────────┘  └─────────────┘  └──────────────┘ │
│                                                                            │
│  ┌───────────────────────────────────────────────────────┐                │
│  │                    QUERY API                           │                │
│  │  GET /orders?customer=X → Projection A (Postgres)     │                │
│  │  GET /analytics/revenue → Projection B (ClickHouse)   │                │
│  │  GET /search?q=widget   → Projection C (Elastic)      │                │
│  └───────────────────────────────────────────────────────┘                │
└────────────────────────────────────────────────────────────────────────────┘
```

### Event Store Internal Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    EVENT STORE CLUSTER                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              WRITE-AHEAD LOG (per partition)         │   │
│  │                                                     │   │
│  │  Partition = hash(stream_id) % num_partitions       │   │
│  │                                                     │   │
│  │  ┌─────┬─────┬─────┬─────┬─────┬─────┬───────┐   │   │
│  │  │ e1  │ e2  │ e3  │ e4  │ e5  │ e6  │  ...  │   │   │
│  │  │s:A  │s:B  │s:A  │s:C  │s:A  │s:B  │       │   │   │
│  │  │p:0  │p:0  │p:1  │p:0  │p:2  │p:1  │       │   │   │
│  │  │g:1  │g:2  │g:3  │g:4  │g:5  │g:6  │       │   │   │
│  │  └─────┴─────┴─────┴─────┴─────┴─────┴───────┘   │   │
│  │  s = stream_id, p = stream_position, g = global    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌───────────────────────┐  ┌───────────────────────────┐  │
│  │  STREAM INDEX         │  │  GLOBAL POSITION INDEX    │  │
│  │                       │  │                           │  │
│  │  stream_A → [0,2,4]  │  │  1 → partition:0, off:0  │  │
│  │  stream_B → [1,5]    │  │  2 → partition:0, off:1  │  │
│  │  stream_C → [3]      │  │  3 → partition:0, off:2  │  │
│  │                       │  │  ...                      │  │
│  │  (B-tree / LSM)      │  │  (monotonic sequence)     │  │
│  └───────────────────────┘  └───────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  REPLICATION (Raft per partition group)               │  │
│  │                                                       │  │
│  │  Partition 0: Leader=Node1, Followers=[Node2, Node3]  │  │
│  │  Partition 1: Leader=Node2, Followers=[Node3, Node1]  │  │
│  │  Partition 2: Leader=Node3, Followers=[Node1, Node2]  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Low-Level Design (LLD) - APIs

### Event Store API
```protobuf
service EventStore {
  // Write events (append to stream)
  rpc AppendToStream(AppendRequest) returns (AppendResponse);
  
  // Read events from a stream
  rpc ReadStream(ReadStreamRequest) returns (stream StoredEvent);
  
  // Read all events (global ordering)
  rpc ReadAll(ReadAllRequest) returns (stream StoredEvent);
  
  // Subscribe to events (real-time)
  rpc Subscribe(SubscribeRequest) returns (stream StoredEvent);
  
  // Snapshot operations
  rpc SaveSnapshot(Snapshot) returns (SaveSnapshotResponse);
  rpc LoadSnapshot(LoadSnapshotRequest) returns (Snapshot);
}

message AppendRequest {
  string stream_id = 1;
  string stream_type = 2;
  repeated NewEvent events = 3;
  
  // Optimistic concurrency control
  oneof expected_version {
    uint64 exact = 4;           // Expect stream at this position
    bool stream_exists = 5;     // Expect stream to exist
    bool no_stream = 6;         // Expect stream NOT to exist
    bool any = 7;               // No concurrency check
  }
}

message NewEvent {
  string event_id = 1;          // Client-generated UUID (idempotency)
  string event_type = 2;
  bytes data = 3;
  bytes metadata = 4;
  string content_type = 5;
}

message AppendResponse {
  uint64 next_expected_version = 1;
  repeated uint64 global_positions = 2;  // Position of each appended event
  int64 commit_timestamp = 3;
}

message ReadStreamRequest {
  string stream_id = 1;
  uint64 from_position = 2;     // Start reading from
  uint32 max_count = 3;         // Batch size
  Direction direction = 4;      // FORWARD or BACKWARD
  bool resolve_links = 5;       // Follow event links
}

message SubscribeRequest {
  oneof start_from {
    uint64 global_position = 1;  // Catch-up from position
    bool live_only = 2;          // Only new events
    bool from_beginning = 3;     // Replay everything
  }
  SubscriptionFilter filter = 4;  // Filter by stream prefix, event type
  string subscription_group = 5;  // For competing consumers
}

message SubscriptionFilter {
  oneof filter {
    StreamPrefixFilter stream_prefix = 1;   // "order-*"
    EventTypeFilter event_type = 2;          // ["OrderPlaced", "OrderShipped"]
  }
}
```

### Aggregate Implementation Pattern
```python
class Aggregate:
    """Base class for event-sourced aggregates."""
    
    def __init__(self):
        self._id = None
        self._version = -1  # No events applied yet
        self._pending_events = []
    
    @classmethod
    async def load(cls, stream_id: str, event_store, snapshot_store=None):
        """Load aggregate from event store."""
        aggregate = cls()
        aggregate._id = stream_id
        
        # Try loading from snapshot first
        start_position = 0
        if snapshot_store:
            snapshot = await snapshot_store.load(stream_id)
            if snapshot:
                aggregate._restore_from_snapshot(snapshot.state)
                start_position = snapshot.stream_position + 1
                aggregate._version = snapshot.stream_position
        
        # Apply events since snapshot
        events = await event_store.read_stream(
            stream_id=stream_id,
            from_position=start_position
        )
        for event in events:
            aggregate._apply(event)
            aggregate._version = event.stream_position
        
        return aggregate
    
    def _apply(self, event):
        """Apply event to update state (no side effects)."""
        handler = getattr(self, f'_on_{event.event_type}', None)
        if handler:
            handler(event.data)
    
    def _raise_event(self, event_type: str, data: dict):
        """Record new event (during command handling)."""
        event = NewEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            data=json.dumps(data).encode()
        )
        self._pending_events.append(event)
        self._apply(StoredEvent(event_type=event_type, data=data))
        self._version += 1
    
    async def save(self, event_store):
        """Persist pending events with optimistic concurrency."""
        if not self._pending_events:
            return
            
        response = await event_store.append_to_stream(
            stream_id=self._id,
            events=self._pending_events,
            expected_version=self._version - len(self._pending_events)
        )
        self._pending_events.clear()
        return response


class OrderAggregate(Aggregate):
    """Example: Order as event-sourced aggregate."""
    
    def __init__(self):
        super().__init__()
        self.status = None
        self.items = []
        self.total = 0
        self.customer_id = None
    
    # Command handlers (business logic)
    def place_order(self, customer_id: str, items: list):
        if self.status is not None:
            raise DomainError("Order already exists")
        if not items:
            raise DomainError("Order must have at least one item")
        
        total = sum(i['quantity'] * i['price'] for i in items)
        self._raise_event('OrderPlaced', {
            'customer_id': customer_id,
            'items': items,
            'total': total
        })
    
    def add_item(self, product_id: str, quantity: int, price: float):
        if self.status != 'placed':
            raise DomainError("Cannot modify order in current state")
        self._raise_event('OrderItemAdded', {
            'product_id': product_id,
            'quantity': quantity,
            'price': price
        })
    
    def ship(self, tracking_number: str, carrier: str):
        if self.status != 'paid':
            raise DomainError("Cannot ship unpaid order")
        self._raise_event('OrderShipped', {
            'tracking_number': tracking_number,
            'carrier': carrier
        })
    
    def cancel(self, reason: str):
        if self.status in ('shipped', 'delivered', 'cancelled'):
            raise DomainError(f"Cannot cancel order in state: {self.status}")
        self._raise_event('OrderCancelled', {'reason': reason})
    
    # Event handlers (state transitions - no logic, just apply)
    def _on_OrderPlaced(self, data):
        self.status = 'placed'
        self.customer_id = data['customer_id']
        self.items = data['items']
        self.total = data['total']
    
    def _on_OrderItemAdded(self, data):
        self.items.append(data)
        self.total += data['quantity'] * data['price']
    
    def _on_OrderShipped(self, data):
        self.status = 'shipped'
    
    def _on_OrderCancelled(self, data):
        self.status = 'cancelled'
```

### Command Handler
```python
class CommandHandler:
    """Handles commands by loading aggregate, executing, and saving."""
    
    def __init__(self, event_store, snapshot_store, retry_policy):
        self.event_store = event_store
        self.snapshot_store = snapshot_store
        self.retry_policy = retry_policy
    
    async def handle(self, command):
        """Execute command with optimistic concurrency retry."""
        for attempt in range(self.retry_policy.max_retries):
            try:
                # Load aggregate
                aggregate = await OrderAggregate.load(
                    stream_id=command.order_id,
                    event_store=self.event_store,
                    snapshot_store=self.snapshot_store
                )
                
                # Execute command (may raise domain errors)
                getattr(aggregate, command.method)(**command.params)
                
                # Save (may raise ConcurrencyError)
                result = await aggregate.save(self.event_store)
                
                # Maybe take snapshot
                if aggregate._version % 100 == 0:
                    await self.snapshot_store.save(Snapshot(
                        stream_id=aggregate._id,
                        stream_position=aggregate._version,
                        state=aggregate._serialize_state()
                    ))
                
                return result
                
            except OptimisticConcurrencyError:
                if attempt == self.retry_policy.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_policy.backoff(attempt))
```

---

## 7. Deep Dives

### Deep Dive 1: Event Store Internals

#### Append-Only Log with Optimistic Concurrency
```python
class EventStorePartition:
    """Single partition of the event store."""
    
    def __init__(self, partition_id: int, wal, stream_index, global_seq):
        self.partition_id = partition_id
        self.wal = wal                    # Write-ahead log (append-only file)
        self.stream_index = stream_index  # B-tree: stream_id → [positions]
        self.global_seq = global_seq      # Atomic global sequence generator
        self.lock = asyncio.Lock()        # Per-partition write lock
    
    async def append(self, stream_id: str, events: list, 
                     expected_version: int) -> list:
        """Append events with optimistic concurrency."""
        async with self.lock:
            # Check expected version
            current_version = await self.stream_index.get_latest_position(stream_id)
            
            if expected_version >= 0 and current_version != expected_version:
                raise OptimisticConcurrencyError(
                    f"Stream {stream_id}: expected {expected_version}, "
                    f"actual {current_version}")
            
            # Assign positions
            stored_events = []
            for i, event in enumerate(events):
                stream_position = (current_version + 1 + i) if current_version >= 0 else i
                global_position = self.global_seq.next()
                
                stored = StoredEvent(
                    event_id=event.event_id,
                    stream_id=stream_id,
                    stream_position=stream_position,
                    global_position=global_position,
                    event_type=event.event_type,
                    data=event.data,
                    timestamp=hlc_now()
                )
                stored_events.append(stored)
            
            # Write to WAL (fsync for durability)
            wal_offset = await self.wal.append_batch(stored_events, fsync=True)
            
            # Update stream index
            for event in stored_events:
                await self.stream_index.add(
                    stream_id, event.stream_position, wal_offset)
            
            # Notify subscribers
            await self.notify_subscribers(stored_events)
            
            return stored_events
```

#### Global Ordering with Hybrid Logical Clock
```
Challenge: Events across partitions need global ordering for subscriptions

Solution: Epoch-based global sequencer

┌─────────────────────────────────────────────────────────┐
│  GLOBAL SEQUENCER (Paxos-replicated)                    │
│                                                         │
│  Allocates ranges to partitions in batches:             │
│    Partition 0: [1, 10000]                             │
│    Partition 1: [10001, 20000]                         │
│    Partition 2: [20001, 30000]                         │
│                                                         │
│  When partition exhausts range → request new batch      │
│  Batch size adaptive: high throughput → larger batches  │
│                                                         │
│  Ordering guarantee:                                    │
│    - WITHIN stream: strict sequential (per-partition)   │
│    - ACROSS streams: causal (HLC-based)                │
│    - GLOBAL: monotonic within partition, approximate    │
│              across partitions (bounded by batch size)  │
│                                                         │
│  For exact global ordering: use commit timestamp        │
│  Readers poll all partitions, merge by timestamp        │
└─────────────────────────────────────────────────────────┘
```

#### Compaction via Snapshots
```python
class SnapshotCompactor:
    """Background compaction to manage storage growth."""
    
    async def compact_stream(self, stream_id: str):
        """Create snapshot and mark old events as archivable."""
        # Load full aggregate state
        aggregate = await self.load_aggregate(stream_id)
        
        # Save snapshot at current position
        snapshot = Snapshot(
            stream_id=stream_id,
            stream_position=aggregate._version,
            state=aggregate._serialize_state(),
            timestamp=time.time()
        )
        await self.snapshot_store.save(snapshot)
        
        # Mark events before snapshot as archivable
        # (NOT deleted - just moved to cold storage)
        await self.event_store.mark_archivable(
            stream_id=stream_id,
            up_to_position=aggregate._version
        )
    
    async def archive_old_events(self):
        """Move archivable events to cold storage (S3/GCS)."""
        archivable = await self.event_store.get_archivable_segments()
        for segment in archivable:
            # Upload to object storage
            await self.cold_storage.upload(
                key=f"events/{segment.partition}/{segment.start}-{segment.end}",
                data=segment.data
            )
            # Remove from hot storage (keep index for replay)
            await self.event_store.remove_segment(segment)
```

### Deep Dive 2: Projection Engine

#### Projection Builder
```python
class ProjectionEngine:
    """Manages lifecycle of all projections."""
    
    def __init__(self, event_store, checkpoint_store):
        self.event_store = event_store
        self.checkpoint_store = checkpoint_store
        self.projections = {}
    
    def register(self, projection: 'Projection'):
        self.projections[projection.name] = projection
    
    async def run_projection(self, projection_name: str):
        """Main loop for a projection."""
        projection = self.projections[projection_name]
        checkpoint = await self.checkpoint_store.load(projection_name)
        position = checkpoint.last_global_position if checkpoint else 0
        
        while True:
            # Catch-up: read batch of events
            events = await self.event_store.read_all(
                from_position=position + 1,
                max_count=1000,
                filter=projection.event_filter
            )
            
            if not events:
                # Caught up - switch to live subscription
                await self.subscribe_live(projection, position)
                return
            
            # Process batch
            for event in events:
                try:
                    await projection.handle(event)
                    position = event.global_position
                except Exception as e:
                    await self.handle_projection_error(
                        projection, event, e)
            
            # Checkpoint after batch
            await self.checkpoint_store.save(
                projection_name, position)
    
    async def rebuild_projection(self, projection_name: str):
        """Rebuild projection from scratch."""
        projection = self.projections[projection_name]
        
        # Reset state
        await projection.reset()
        await self.checkpoint_store.delete(projection_name)
        
        # Set status
        await self.checkpoint_store.save(
            projection_name, 0, status='rebuilding')
        
        # Replay all events
        await self.run_projection(projection_name)
        
        # Mark complete
        await self.checkpoint_store.update_status(
            projection_name, 'running')


class OrderListProjection:
    """Example projection: order list for customer queries."""
    
    name = "order-list"
    event_filter = EventTypeFilter(["OrderPlaced", "OrderShipped", 
                                    "OrderCancelled", "OrderDelivered"])
    
    def __init__(self, db):
        self.db = db  # Postgres connection
    
    async def handle(self, event: StoredEvent):
        """Handle single event - update read model."""
        handlers = {
            'OrderPlaced': self._on_order_placed,
            'OrderShipped': self._on_order_shipped,
            'OrderCancelled': self._on_order_cancelled,
        }
        handler = handlers.get(event.event_type)
        if handler:
            await handler(event.stream_id, json.loads(event.data))
    
    async def _on_order_placed(self, order_id: str, data: dict):
        await self.db.execute("""
            INSERT INTO order_list_view 
            (order_id, customer_id, status, total, item_count, placed_at)
            VALUES ($1, $2, 'placed', $3, $4, $5)
            ON CONFLICT (order_id) DO UPDATE SET status = 'placed'
        """, order_id, data['customer_id'], data['total'],
             len(data['items']), data.get('placed_at'))
    
    async def _on_order_shipped(self, order_id: str, data: dict):
        await self.db.execute("""
            UPDATE order_list_view 
            SET status = 'shipped', 
                tracking_number = $2,
                shipped_at = NOW()
            WHERE order_id = $1
        """, order_id, data['tracking_number'])
    
    async def _on_order_cancelled(self, order_id: str, data: dict):
        await self.db.execute("""
            UPDATE order_list_view 
            SET status = 'cancelled', reason = $2
            WHERE order_id = $1
        """, order_id, data['reason'])
    
    async def reset(self):
        await self.db.execute("TRUNCATE order_list_view")
```

#### Exactly-Once Processing with Checkpointing
```python
class ExactlyOnceProjection:
    """Projection with transactional checkpoint for exactly-once."""
    
    async def process_batch(self, events: list, checkpoint_position: int):
        """Process events and checkpoint in same transaction."""
        async with self.db.transaction() as tx:
            for event in events:
                # Check if already processed (idempotency key)
                processed = await tx.fetchval(
                    "SELECT 1 FROM processed_events WHERE event_id = $1",
                    event.event_id)
                if processed:
                    continue
                
                # Apply projection logic
                await self.handle(event, tx)
                
                # Record processed event
                await tx.execute(
                    "INSERT INTO processed_events (event_id) VALUES ($1)",
                    event.event_id)
            
            # Update checkpoint in same transaction
            await tx.execute(
                """UPDATE projection_checkpoints 
                   SET last_global_position = $1, 
                       last_processed_at = NOW()
                   WHERE projection_name = $2""",
                checkpoint_position, self.name)
        
        # Transaction committed → exactly-once guaranteed
        # If crash before commit → retry from last checkpoint
```

### Deep Dive 3: Saga / Process Manager

#### Saga State Machine
```python
class SagaDefinition:
    """Define a saga as a state machine with compensation."""
    
    def __init__(self, saga_type: str):
        self.saga_type = saga_type
        self.states = {}
        self.transitions = {}
        self.compensations = {}
        self.timeout_handlers = {}
    
    def state(self, name, on_enter=None):
        self.states[name] = {'on_enter': on_enter}
        return self
    
    def transition(self, from_state, event_type, to_state, action=None):
        key = (from_state, event_type)
        self.transitions[key] = {'to_state': to_state, 'action': action}
        return self
    
    def compensation(self, state, compensate_action):
        self.compensations[state] = compensate_action
        return self


class OrderFulfillmentSaga:
    """Example: Order fulfillment as a saga."""
    
    @staticmethod
    def define() -> SagaDefinition:
        saga = SagaDefinition('OrderFulfillment')
        
        # States
        saga.state('started')
        saga.state('payment_pending')
        saga.state('payment_confirmed')
        saga.state('inventory_reserved')
        saga.state('shipping_scheduled')
        saga.state('completed')
        saga.state('compensating')
        saga.state('failed')
        
        # Happy path transitions
        saga.transition('started', 'OrderPlaced', 'payment_pending',
                       action='request_payment')
        saga.transition('payment_pending', 'PaymentConfirmed', 'payment_confirmed',
                       action='reserve_inventory')
        saga.transition('payment_confirmed', 'InventoryReserved', 'inventory_reserved',
                       action='schedule_shipping')
        saga.transition('inventory_reserved', 'ShippingScheduled', 'shipping_scheduled',
                       action='confirm_order')
        saga.transition('shipping_scheduled', 'OrderConfirmed', 'completed',
                       action=None)
        
        # Failure transitions
        saga.transition('payment_pending', 'PaymentFailed', 'failed',
                       action='notify_customer_payment_failed')
        saga.transition('payment_confirmed', 'InventoryUnavailable', 'compensating',
                       action='compensate_payment')
        saga.transition('inventory_reserved', 'ShippingFailed', 'compensating',
                       action='compensate_inventory')
        
        # Compensations (reverse order)
        saga.compensation('inventory_reserved', 'release_inventory')
        saga.compensation('payment_confirmed', 'refund_payment')
        
        return saga


class SagaEngine:
    """Executes saga state machines."""
    
    def __init__(self, event_store, saga_store, command_bus):
        self.event_store = event_store
        self.saga_store = saga_store
        self.command_bus = command_bus
        self.definitions = {}
    
    def register(self, definition: SagaDefinition):
        self.definitions[definition.saga_type] = definition
    
    async def handle_event(self, event: StoredEvent):
        """Route event to relevant saga instance."""
        # Find saga instance for this event
        saga_instance = await self.saga_store.find_by_correlation(
            event.correlation_id)
        
        if not saga_instance:
            # Check if this event starts a new saga
            if event.event_type == 'OrderPlaced':
                saga_instance = await self.create_saga(
                    'OrderFulfillment', event)
            else:
                return
        
        definition = self.definitions[saga_instance.saga_type]
        
        # Find transition
        key = (saga_instance.current_state, event.event_type)
        transition = definition.transitions.get(key)
        
        if not transition:
            # No transition for this event in current state - ignore or log
            return
        
        # Execute transition
        old_state = saga_instance.current_state
        saga_instance.current_state = transition['to_state']
        saga_instance.last_transition_at = datetime.utcnow()
        saga_instance.completed_steps.append({
            'from': old_state,
            'to': transition['to_state'],
            'event': event.event_type,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Execute action
        if transition['action']:
            command = await self.build_command(
                transition['action'], saga_instance, event)
            saga_instance.pending_commands.append(command)
            await self.command_bus.send(command)
        
        # Save saga state (with optimistic concurrency)
        await self.saga_store.save(saga_instance)
    
    async def handle_timeout(self, saga_id: str):
        """Handle saga timeout - trigger compensation."""
        saga = await self.saga_store.load(saga_id)
        if saga.status != 'active':
            return
        
        saga.status = 'compensating'
        definition = self.definitions[saga.saga_type]
        
        # Execute compensations in reverse order
        for step in reversed(saga.completed_steps):
            compensation = definition.compensations.get(step['to'])
            if compensation:
                command = await self.build_compensation_command(
                    compensation, saga)
                await self.command_bus.send(command)
                saga.compensation_log.append({
                    'action': compensation,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        saga.status = 'failed'
        await self.saga_store.save(saga)
```

#### Event Versioning with Upcasters
```python
class EventUpcaster:
    """Transform old event versions to current version."""
    
    def __init__(self, schema_registry):
        self.registry = schema_registry
        self.upcasters = {}
    
    def register(self, event_type: str, from_version: int, 
                 to_version: int, transform_fn):
        key = (event_type, from_version, to_version)
        self.upcasters[key] = transform_fn
    
    def upcast(self, event: StoredEvent) -> StoredEvent:
        """Upcast event to latest schema version."""
        current_version = event.schema_version
        latest_version = self.registry.get_latest_version(event.event_type)
        
        if current_version == latest_version:
            return event
        
        data = json.loads(event.data)
        
        # Chain upcasters: v1 → v2 → v3 → ... → latest
        for v in range(current_version, latest_version):
            key = (event.event_type, v, v + 1)
            upcaster = self.upcasters.get(key)
            if not upcaster:
                raise MissingUpcasterError(
                    f"No upcaster for {event.event_type} v{v} → v{v+1}")
            data = upcaster(data)
        
        return StoredEvent(
            **{**event.__dict__, 
               'data': json.dumps(data).encode(),
               'schema_version': latest_version}
        )

# Example upcasters
upcaster = EventUpcaster(schema_registry)

# OrderPlaced v1 → v2: added 'currency' field
upcaster.register('OrderPlaced', 1, 2, lambda data: {
    **data,
    'currency': 'USD'  # Default for old events without currency
})

# OrderPlaced v2 → v3: renamed 'total' to 'total_amount', added 'tax'
upcaster.register('OrderPlaced', 2, 3, lambda data: {
    **{k: v for k, v in data.items() if k != 'total'},
    'total_amount': data['total'],
    'tax': data['total'] * 0.08  # Estimate tax for old events
})

# OrderShipped v1 → v2: split 'address' into structured fields
upcaster.register('OrderShipped', 1, 2, lambda data: {
    **data,
    'tracking_url': f"https://track.example.com/{data['tracking_number']}",
    'estimated_delivery': None  # Not available for old events
})
```

---

## 8. Component Optimization

### Write Path Optimization
```
Techniques for <5ms write latency at 1M events/sec:

1. Batch writes within partition
   - Buffer events for 1ms, flush as batch
   - Single fsync per batch (amortized)
   - Trade-off: 1ms added latency for 10x throughput

2. Memory-mapped WAL
   - mmap for sequential writes
   - OS handles page cache efficiently
   - Explicit fsync at batch boundaries

3. Pre-allocated log segments
   - Pre-create 1GB segment files
   - No filesystem allocation during write path
   - Rotate when segment full

4. Lock-free stream index updates
   - Copy-on-write B-tree for stream index
   - Readers never blocked by writers
   - Background compaction of index

5. Connection pooling for replication
   - Persistent gRPC streams between replicas
   - Pipeline replication (don't wait for ACK per event)
   - Quorum write: 2 of 3 replicas ACK → committed

Measured latency breakdown:
  Serialize event:     0.1ms
  Acquire lock:        0.05ms (per-partition, low contention)
  Version check:       0.2ms (in-memory index lookup)
  WAL append:          0.5ms (batch + fsync)
  Index update:        0.1ms
  Replication ACK:     2ms (network + remote fsync)
  Notify subscribers:  0.1ms (async, non-blocking)
  Total:              ~3ms p99
```

### Projection Lag Optimization
```
Target: <100ms from event write to projection update

Pipeline:
  Event written (0ms)
    → Replication ACK (2ms)
    → Subscription notification (5ms) [push-based, not polling]
    → Event delivered to projection worker (10ms)
    → Projection handler executes (20ms)
    → Read model updated (40ms) [batched writes]
    → Checkpoint saved (10ms) [async, periodic]
  Total: ~87ms p99

Optimization techniques:
  - Push-based subscriptions (not polling)
  - In-memory event buffer for subscribers
  - Batch projection writes (accumulate 10ms, flush)
  - Separate hot/cold projections (critical ones get priority)
  - Parallel projection handlers (independent projections)
  - Skip unnecessary events early (filter at subscription level)
```

---

## 9. Observability

### Key Metrics
```yaml
event_store_metrics:
  - name: events_appended_total
    type: counter
    labels: [stream_type, partition]
    
  - name: event_append_latency_ms
    type: histogram
    labels: [stream_type]
    buckets: [1, 2, 5, 10, 25, 50, 100]
    
  - name: concurrency_conflicts_total
    type: counter
    labels: [stream_type]
    
  - name: streams_total
    type: gauge
    
  - name: global_position_head
    type: gauge
    labels: [partition]

projection_metrics:
  - name: projection_lag_ms
    type: gauge
    labels: [projection_name]
    alert: "> 1000ms for 5 minutes"
    
  - name: projection_events_processed_total
    type: counter
    labels: [projection_name, event_type]
    
  - name: projection_errors_total
    type: counter
    labels: [projection_name, error_type]
    
  - name: projection_rebuild_duration_seconds
    type: histogram
    labels: [projection_name]

saga_metrics:
  - name: saga_instances_active
    type: gauge
    labels: [saga_type, current_state]
    
  - name: saga_completed_total
    type: counter
    labels: [saga_type, outcome]  # success, compensated, timed_out
    
  - name: saga_duration_seconds
    type: histogram
    labels: [saga_type]
    
  - name: saga_compensation_triggered_total
    type: counter
    labels: [saga_type, trigger_reason]
```

### Health Checks
```python
async def health_check():
    return {
        "event_store": {
            "status": "healthy",
            "global_position": 1_234_567_890,
            "write_latency_p99_ms": 4.2,
            "partitions_healthy": "100/100"
        },
        "projections": {
            "order-list": {"lag_ms": 45, "status": "running"},
            "analytics": {"lag_ms": 120, "status": "running"},
            "search-index": {"lag_ms": 89, "status": "running"}
        },
        "sagas": {
            "active": 1234,
            "timed_out_last_hour": 2,
            "compensating": 0
        },
        "schema_registry": {
            "event_types": 156,
            "latest_registration": "2024-01-15T10:30:00Z"
        }
    }
```

---

## 10. Failure Scenarios & Mitigations

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| Event store partition leader failure | Writes to that partition stall | Raft leader election (<5s), clients retry |
| Projection falls behind | Stale read model | Alert, scale workers, prioritize critical projections |
| Projection bug (bad handler) | Corrupted read model | Dead letter queue, fix bug, rebuild from events |
| Saga timeout | Incomplete business process | Compensation actions, alert, manual intervention |
| Schema incompatibility | Events can't be deserialized | Schema registry validation on write, upcasters for reads |
| Event store disk full | Writes rejected | Monitoring, auto-archive old segments, alert |
| Duplicate event (idempotency failure) | Double processing | Event ID deduplication at store and projection level |
| Snapshot corruption | Slow aggregate loading | Fall back to full replay, rebuild snapshot |
| Global sequence gap | Projections see gap, stall | Bounded wait + timeout, mark gap as acceptable |

---

## 11. Considerations & Trade-offs

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Event store vs Kafka | Custom event store | Need per-stream ordering + optimistic concurrency (Kafka lacks) |
| Serialization | JSON with schema registry | Human-readable, schema evolution with upcasters |
| Projection consistency | Eventual (async) | Acceptable lag for most reads, strong via read-your-writes |
| Snapshot strategy | Every 100 events | Balance between load time and snapshot overhead |
| Saga persistence | Event-sourced sagas | Saga state changes are events too - full audit trail |
| Global ordering | Approximate (partitioned) | Exact global requires single writer (bottleneck) |

### When to Use Event Sourcing
- Audit requirements (full history)
- Complex domain logic (event-driven state machines)
- Multiple read models from same data
- Temporal queries ("what was state at time T?")
- Event-driven architecture (natural fit)

### When NOT to Use
- Simple CRUD applications
- Low-value data (logs, metrics)
- When eventual consistency is unacceptable everywhere
- Small team without ES/CQRS experience (steep learning curve)
